# kafka_producer.py

import pandas as pd
import json
import time
from kafka import KafkaProducer
from datetime import datetime

# Constants as defined in requirements
TOPIC = "mock_l1_stream"
CSV_PATH = "l1_day.csv"
TIME_FORMAT = "%H:%M:%S"
START_TIME = "13:36:32"
END_TIME = "13:45:14"

# Setting up the Kafka Producer
# Using localhost 9092 as it is recommended for local testing
producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Loading CSV using Pandas
print("Loading CSV...")
df = pd.read_csv(CSV_PATH)

# Filter by time window (For each second)
df['ts_event'] = pd.to_datetime(df['ts_event']).dt.strftime(TIME_FORMAT)
df = df[(df['ts_event'] >= START_TIME) & (df['ts_event'] <= END_TIME)]

# Grouping by timestamp as messages produced to the stream needs to be grouped as snapshots
grouped = df.groupby('ts_event')

# Stream each group 
print("Starting to stream data...")
timestamps = list(grouped.groups.keys())
for i, ts in enumerate(timestamps):
    batch = grouped.get_group(ts)
    print(f"Streaming timestamp: {ts} with {len(batch)} rows")

    for _, row in batch.iterrows():
        message = {
            "timestamp": ts,
            "publisher_id": row["publisher_id"],
            "ask_px_00": row["ask_px_00"],
            "ask_sz_00": row["ask_sz_00"]
        }
        producer.send(TOPIC, message)
        print(f"Sent: {message}")

    # Sleep based on delta value of each second (For instance if group x is 13:37:31 and group x+1 is 13:37:32 then delta = 1) and code pauses for a second to simulate real world streaming 
    if i < len(timestamps) - 1:
        curr = datetime.strptime(ts, TIME_FORMAT)
        nxt = datetime.strptime(timestamps[i+1], TIME_FORMAT)
        delta = (nxt - curr).total_seconds()
        time.sleep(min(delta, 1.0))

print("Done streaming.")
producer.flush()
producer.close()
