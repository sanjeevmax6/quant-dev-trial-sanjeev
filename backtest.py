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

# Cont-Kukanov allocator parameters - expanded search space
lambda_over_values = [0.1, 0.3, 0.5, 0.7]
lambda_under_values = [0.1, 0.3, 0.5, 0.7]
theta_queue_values = [0.05, 0.1, 0.3, 0.5]

# Venue structure: ask price, ask size, fee, rebate
Venue = namedtuple("Venue", ["ask", "ask_size", "fee", "rebate"])

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
    if base == 0:
        return 0
    return round((base - opt) / base * 10000, 2)


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

    for ts, venue_list in snapshots_by_ts.items():
        if remaining <= 0:
            break
            
        # Sort venues by ask price (cheapest first)
        sorted_venues = sorted(venue_list, key=lambda v: v.ask)
        
        for venue in sorted_venues:
            if remaining <= 0:
                break
                
            fill = min(venue.ask_size, remaining)
            if fill > 0:
                total_cash += fill * (venue.ask + venue.fee)
                total_filled += fill
                remaining -= fill

    avg_price = total_cash / total_filled if total_filled > 0 else 0
    return round(total_cash, 2), round(avg_price, 4)


def baseline_twap(snapshots_by_ts):
    remaining = ORDER_SIZE
    total_cash = 0
    total_filled = 0
    
    timestamps = list(snapshots_by_ts.keys())
    if not timestamps:
        return 0, 0
    
    # Divide order across available timestamps
    shares_per_timestamp = ORDER_SIZE // len(timestamps)
    extra_shares = ORDER_SIZE % len(timestamps)
    
    for i, (ts, venue_list) in enumerate(snapshots_by_ts.items()):
        if remaining <= 0:
            break
            
        # Calculate target shares for this timestamp
        target_shares = shares_per_timestamp
        if i < extra_shares:  # distribute remainder across first few timestamps
            target_shares += 1
            
        target_shares = min(target_shares, remaining)
        
        # Sort venues by price and fill greedily within this timestamp
        sorted_venues = sorted(venue_list, key=lambda v: v.ask)
        timestamp_filled = 0
        
        for venue in sorted_venues:
            if timestamp_filled >= target_shares:
                break
                
            fill = min(venue.ask_size, target_shares - timestamp_filled)
            if fill > 0:
                total_cash += fill * (venue.ask + venue.fee)
                total_filled += fill
                remaining -= fill
                timestamp_filled += fill

    avg_price = total_cash / total_filled if total_filled > 0 else 0
    return round(total_cash, 2), round(avg_price, 4)


def baseline_vwap(snapshots_by_ts):
    remaining = ORDER_SIZE
    total_cash = 0
    total_filled = 0

    for ts, venue_list in snapshots_by_ts.items():
        if remaining <= 0:
            break
            
        # Calculate total available size across all venues
        total_available = sum(v.ask_size for v in venue_list)
        if total_available == 0:
            continue
            
        # Allocate proportionally to available size, but fill at each venue's price
        for venue in venue_list:
            if remaining <= 0:
                break
                
            # Calculate proportional allocation
            proportion = venue.ask_size / total_available
            target_fill = min(int(proportion * remaining), venue.ask_size)
            
            if target_fill > 0:
                total_cash += target_fill * (venue.ask + venue.fee)
                total_filled += target_fill
                remaining -= target_fill

    avg_price = total_cash / total_filled if total_filled > 0 else 0
    return round(total_cash, 2), round(avg_price, 4)


def run_sor(snapshots_by_ts, λ_over, λ_under, θ_queue):
    total_cash = 0
    total_filled = 0
    remaining = ORDER_SIZE

    for ts, venue_list in snapshots_by_ts.items():
        if remaining <= 0:
            break

        # Get optimal allocation for remaining shares
        alloc, expected_cost = allocate(remaining, venue_list, λ_over, λ_under, θ_queue)
        
        # Execute the allocation
        timestamp_filled = 0
        for i, venue in enumerate(venue_list):
            if i >= len(alloc):
                break
                
            want = alloc[i]
            if want <= 0:
                continue
                
            # Fill what we can at this venue
            fill = min(want, venue.ask_size, remaining)
            if fill > 0:
                # Pay for filled shares
                total_cash += fill * (venue.ask + venue.fee)
                total_filled += fill
                remaining -= fill
                timestamp_filled += fill
                
                # Get rebate for unfilled shares (if we posted more than available)
                unfilled_posted = max(want - fill, 0)
                if unfilled_posted > 0:
                    total_cash -= unfilled_posted * venue.rebate

        print(f"Timestamp {ts} — Filled {timestamp_filled} shares, Total: {total_filled}/{ORDER_SIZE}, Remaining: {remaining}")

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

    with open("result.json", "w") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    snapshots_by_ts = load_all_snapshots()
    
    if not snapshots_by_ts:
        print("No data loaded from Kafka. Make sure the producer is running and has sent data.")
        exit(1)

    print(f"Starting grid search with {len(snapshots_by_ts)} timestamps...")
    best_params, optimized = grid_search(snapshots_by_ts)
    
    if best_params is None:
        print("Grid search failed to find valid parameters.")
        exit(1)

    print("Running baseline strategies...")
    best_ask_cash, best_ask_avg = baseline_best_ask(snapshots_by_ts)
    twap_cash, twap_avg = baseline_twap(snapshots_by_ts)
    vwap_cash, vwap_avg = baseline_vwap(snapshots_by_ts)

    baselines = {
        "best_ask": {"total_cash": best_ask_cash, "avg_fill_px": best_ask_avg},
        "twap": {"total_cash": twap_cash, "avg_fill_px": twap_avg},
        "vwap": {"total_cash": vwap_cash, "avg_fill_px": vwap_avg}
    }

    produce_final_json(best_params, optimized, baselines)