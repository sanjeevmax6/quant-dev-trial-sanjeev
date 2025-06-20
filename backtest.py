from kafka import KafkaConsumer
import json
from collections import namedtuple
import time
from allocator import allocate, compute_cost
from greedy_allocator import greedy_allocate

# Configuration for Kafka stream
TOPIC = "mock_l1_stream"
ORDER_SIZE = 5000
BOOTSTRAP_SERVERS = 'localhost:9092'

# Cont-Kukanov allocator parameters
LAMBDA_OVER = 0.4
LAMBDA_UNDER = 0.6
THETA_QUEUE = 0.3

# Venue structure: ask price, ask size, fee, rebate
Venue = namedtuple("Venue", ["ask", "ask_size", "fee", "rebate"])

# Kafka consumer
consumer = KafkaConsumer(
    TOPIC,
    bootstrap_servers=BOOTSTRAP_SERVERS,
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

print("Consuming messages from Kafka...")

# Execution state
remaining = ORDER_SIZE
total_cash = 0
total_filled = 0

# Streaming logic
previous_ts = None
current_batch = []

for message in consumer:
    data = message.value
    ts = data['timestamp']
    venue = Venue(
        ask=data['ask_px_00'],
        ask_size=data['ask_sz_00'],
        fee=0.001,
        rebate=0.0005
    )

    # Reading messages until timestamp is same as previous (So that we can use the algorithm to figure out how many shares can be bought at one timestamp)
    # If we exceed 5000 shares before consuming all messages, we directly exit the loop and stop streaming as that is the condition
    if previous_ts is None:
        previous_ts = ts

    if previous_ts is not None and ts != previous_ts:
        print(f"Processing {previous_ts} with {len(current_batch)} venues")

        # Passing a copy to allocator for safety of Python's passing by reference
        print(f"Running allocate() on {len(current_batch)} venues, remaining = {remaining}")
        # alloc, _ = allocate(remaining, current_batch.copy(),
        #                     LAMBDA_OVER, LAMBDA_UNDER, THETA_QUEUE)
        alloc, _ = greedy_allocate(remaining, current_batch.copy(),
                            LAMBDA_OVER, LAMBDA_UNDER, THETA_QUEUE)

        for i, v in enumerate(current_batch):
            want = alloc[i]
            fill = min(want, v.ask_size)
            total_cash += fill * (v.ask + v.fee)
            total_cash -= max(want - fill, 0) * v.rebate
            total_filled += fill
            remaining -= fill

        print(f" Filled {total_filled}/{ORDER_SIZE} so far")
        if remaining <= 0:
            break

        current_batch.clear()

    previous_ts = ts
    current_batch.append(venue)

# Final stats
avg_fill_px = total_cash / total_filled if total_filled > 0 else 0.0
result = {
    "optimized": {
        "total_cash": round(total_cash, 2),
        "avg_fill_px": round(avg_fill_px, 4)
    }
}

print("\n Final Execution Result:")
print(json.dumps(result, indent=2))