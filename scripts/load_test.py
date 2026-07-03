#!/usr/bin/env python3
"""
Load test script. Hammers the API concurrently to trigger auto-scaling.
Usage: python3 scripts/load_test.py [duration_seconds]
Watch the orchestrator output for CPU readings and scaling events.
"""

import requests
import threading
import time
import sys

BASE_URL  = "http://localhost:8080"
THREADS   = 50
DURATION  = int(sys.argv[1]) if len(sys.argv) > 1 else 60

stop_event = threading.Event()


def hammer():
    while not stop_event.is_set():
        try:
            requests.get(f"{BASE_URL}/api/users", timeout=5)
            requests.get(f"{BASE_URL}/api/data",  timeout=5)
        except Exception:
            pass


threads = [threading.Thread(target=hammer, daemon=True) for _ in range(THREADS)]

print(f"Starting load test: {THREADS} threads for {DURATION}s against {BASE_URL}")
print("Watch orchestrator output for CPU readings and scaling events.")
print("-" * 50)

for t in threads:
    t.start()

time.sleep(DURATION)
stop_event.set()

for t in threads:
    t.join()

print("Load test complete.")
