import time
import datetime
import sys

print("--- Simple Loop Script Starting ---", flush=True)
count = 0
while True:
    timestamp = datetime.datetime.now().isoformat()
    print(f"{timestamp}: Simple loop running - Count: {count}", flush=True)
    count += 1
    time.sleep(5) 