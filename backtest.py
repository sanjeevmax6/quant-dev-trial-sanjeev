from kafka import KafkaConsumer
import json
from collections import namedtuple, defaultdict
import time
from allocator import allocate, compute_cost
from greedy_allocator import greedy_allocate

# Configuration for Kafka stream
TOPIC = "mock_l1_stream"
ORDER_SIZE = 5000
BOOTSTRAP_SERVERS = 'localhost:9092'

# Cont-Kukanov allocator parameters
lambda_over_values = [0.2, 0.4, 0.6]
lambda_under_values = [0.2, 0.4, 0.6]
theta_queue_values = [0.1, 0.3, 0.5]

# Venue structure: ask price, ask size, fee, rebate
Venue = namedtuple("Venue", ["ask", "ask_size", "fee", "rebate"])

# Kafka consumer as a function to run each baselines
def load_all_snapshots():
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        auto_offset_reset='earliest',
        enable_auto_commit=False,
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )

    snapshots = defaultdict(list)

    print("Reading all Kafka messages (this may take a few seconds)...")

    # Poll until no more new messages (max_idle_time controls wait)
    max_idle_time = 3  # seconds
    idle_counter = 0

    while True:
        raw_msgs = consumer.poll(timeout_ms=1000)
        if not raw_msgs:
            idle_counter += 1
            if idle_counter >= max_idle_time:
                break  # no more messages, exit loop
            continue

        idle_counter = 0  # reset idle timer on successful poll

        for tp, messages in raw_msgs.items():
            for message in messages:
                data = message.value
                ts = data['timestamp']
                venue = Venue(
                    ask=data['ask_px_00'],
                    ask_size=data['ask_sz_00'],
                    fee=0.001,
                    rebate=0.0005
                )
                snapshots[ts].append(venue)

    consumer.close()
    print(f"Loaded {len(snapshots)} timestamps.")
    return dict(sorted(snapshots.items()))


def calculate_savings(base, opt):
    return round((base - opt) / base * 10000, 2)


print("Consuming messages from Kafka...")

def grid_search(snapshots_by_ts):
    best_config = None
    best_cost = float('inf')
    best_result = {}

    for λ_over in lambda_over_values:
        for λ_under in lambda_under_values:
            for θ_queue in theta_queue_values:
                print(f"Testing λ_over={λ_over}, λ_under={λ_under}, θ_queue={θ_queue}")
                total_cash, total_filled = run_sor(snapshots_by_ts, λ_over, λ_under, θ_queue)

                if total_filled == 0:
                    continue  # skip invalid fills

                avg_fill_px = total_cash / total_filled

                if total_cash < best_cost:
                    best_cost = total_cash
                    best_config = (λ_over, λ_under, θ_queue)
                    best_result = {
                        "total_cash": round(total_cash, 2),
                        "avg_fill_px": round(avg_fill_px, 4)
                    }

    return best_config, best_result

def baseline_best_ask(snapshots_by_ts):
    remaining = ORDER_SIZE
    total_cash = 0
    total_filled = 0
    previous_ts = None
    current_batch = []

    for ts, venue_list in snapshots_by_ts.items():
        if previous_ts is None:
            previous_ts = ts

        if ts != previous_ts:
            current_batch.sort(key=lambda v: v.ask)
            for v in current_batch:
                fill = min(v.ask_size, remaining)
                total_cash += fill * (v.ask + v.fee)
                total_filled += fill
                remaining -= fill
                if remaining <= 0:
                    break
            if remaining <= 0:
                break
            current_batch.clear()

        previous_ts = ts
        current_batch.extend(venue_list)

    avg_price = total_cash / total_filled if total_filled > 0 else 0
    return round(total_cash, 2), round(avg_price, 4)

def baseline_twap(snapshots_by_ts):
    remaining = ORDER_SIZE
    total_cash = 0
    total_filled = 0
    previous_ts = None
    current_batch = []
    snapshots_processed = 0
    max_snapshots = 10  # Spreading evenly across 10 timestamps

    for ts, venue_list in snapshots_by_ts.items():
        if previous_ts is None:
            previous_ts = ts

        if ts != previous_ts:
            snapshots_processed += 1
            slice_size = ORDER_SIZE // max_snapshots
            filled_in_snapshot = 0

            current_batch.sort(key=lambda v: v.ask)  # prioritizing cheaper venues
            for v in current_batch:
                fill = min(v.ask_size, slice_size - filled_in_snapshot)
                total_cash += fill * (v.ask + v.fee)
                total_filled += fill
                remaining -= fill
                filled_in_snapshot += fill
                if filled_in_snapshot >= slice_size:
                    break

            current_batch.clear()
            if snapshots_processed >= max_snapshots or remaining <= 0:
                break

        previous_ts = ts
        current_batch.extend(venue_list)

    avg_price = total_cash / total_filled if total_filled > 0 else 0
    return round(total_cash, 2), round(avg_price, 4)

def baseline_vwap(snapshots_by_ts):
    remaining = ORDER_SIZE
    total_cash = 0
    total_filled = 0
    previous_ts = None
    current_batch = []

    for ts, venue_list in snapshots_by_ts.items():
        if previous_ts is None:
            previous_ts = ts

        if ts != previous_ts:
            total_sz = sum(v.ask_size for v in current_batch)
            if total_sz == 0:
                current_batch.clear()
                previous_ts = ts
                continue

            for v in current_batch:
                share = (v.ask_size / total_sz) * remaining
                fill = min(v.ask_size, int(share))
                total_cash += fill * (v.ask + v.fee)
                total_filled += fill
                remaining -= fill
                if remaining <= 0:
                    break

            current_batch.clear()
            if remaining <= 0:
                break

        previous_ts = ts
        current_batch.extend(venue_list)

    avg_price = total_cash / total_filled if total_filled > 0 else 0
    return round(total_cash, 2), round(avg_price, 4)


def run_sor(snapshots_by_ts, λ_over, λ_under, θ_queue):    
    previous_ts = None
    current_batch = []
    total_cash = 0
    total_filled = 0
    remaining = ORDER_SIZE

    for ts, venue_list in snapshots_by_ts.items():
        if previous_ts is None:
            previous_ts = ts

        if ts != previous_ts:
            print(f"Processing {previous_ts} with {len(current_batch)} venues")

            alloc, _ = greedy_allocate(remaining, current_batch.copy(), λ_over, λ_under, θ_queue)

            for i, v in enumerate(current_batch):
                want = alloc[i]
                fill = min(want, v.ask_size)
                total_cash += fill * (v.ask + v.fee)
                total_cash -= max(want - fill, 0) * v.rebate
                total_filled += fill
                remaining -= fill

            print(f" Filled {total_filled}/{ORDER_SIZE} so far")
            current_batch.clear()

            if total_filled >= ORDER_SIZE:
                break

        previous_ts = ts
        current_batch.extend(venue_list)

    return total_cash, total_filled

def produce_final_json(best_params, optimized, baselines):
    savings = {
        k: calculate_savings(baselines[k]["total_cash"], optimized["total_cash"])
        for k in baselines
    }

    result = {
        "best_parameters": {
            "lambda_over": best_params[0],
            "lambda_under": best_params[1],
            "theta_queue": best_params[2]
        },
        "optimized": optimized,
        "baselines": baselines,
        "savings_vs_baselines_bps": savings
    }

    print(json.dumps(result, indent=2))



if __name__ == "__main__":
    snapshots_by_ts = load_all_snapshots()

    best_params, optimized = grid_search(snapshots_by_ts)

    best_ask_cash, best_ask_avg = baseline_best_ask(snapshots_by_ts)
    twap_cash, twap_avg = baseline_twap(snapshots_by_ts)
    vwap_cash, vwap_avg = baseline_vwap(snapshots_by_ts)

    baselines = {
        "best_ask": {"total_cash": best_ask_cash, "avg_fill_px": best_ask_avg},
        "twap": {"total_cash": twap_cash, "avg_fill_px": twap_avg},
        "vwap": {"total_cash": vwap_cash, "avg_fill_px": vwap_avg}
    }

    produce_final_json(best_params, optimized, baselines)
