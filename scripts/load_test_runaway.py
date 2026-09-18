#!/usr/bin/env python3
"""load_test_runaway.py — Simulates a runaway retry loop or buggy client.

Characteristics:
1. Sends 40 requests in rapid succession to the demo API.
2. Single caller identity: X-Caller-ID: runaway-worker-01, fixed IP.
3. Identical payload repeated in an infinite-retry style loop:
   {"action": "retry_failed_job", "job_id": "job-99120", "loop": True}
4. Demonstrates the anomaly signature that Guardrail Agent classifies as RUNAWAY.
"""

import json
import time
import urllib.request

API_URL = "https://poim5xmgs2.execute-api.ap-south-1.amazonaws.com/prod/items"
NUM_REQUESTS = 40


def main():
    print("=" * 70)
    print(f" Simulating Runaway Client Loop ({NUM_REQUESTS} requests, single caller, identical payload)")
    print(f" Target: {API_URL}")
    print("=" * 70)

    success_count = 0
    throttled_count = 0
    caller_id = "runaway-worker-01"
    simulated_ip = "203.0.113.99"

    # Fixed payload representing a recursive client loop
    payload_obj = {
        "action": "retry_failed_job",
        "job_id": "job-runaway-99120",
        "error_code": "RESOURCE_BUSY",
        "retry_loop": True,
    }
    payload_bytes = json.dumps(payload_obj).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "X-Caller-ID": caller_id,
        "X-Forwarded-For": simulated_ip,
        "User-Agent": "BatchWorker/1.0 (BuggyInfiniteRetryLoop)",
    }

    for i in range(1, NUM_REQUESTS + 1):
        req = urllib.request.Request(API_URL, data=payload_bytes, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    success_count += 1
                    if i % 10 == 0 or i == NUM_REQUESTS:
                        print(f"  [+] Fired request {i}/{NUM_REQUESTS} (caller={caller_id}, status=200)")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                throttled_count += 1
                print(f"  [!] Request {i} throttled with HTTP 429!")
            else:
                print(f"  [-] Request {i} failed: {e}")
        except Exception as e:
            print(f"  [-] Request {i} error: {e}")

        # Rapid loop
        time.sleep(0.02)

    print("\n" + "=" * 70)
    print(f" Runaway loop simulation complete.")
    print(f" Successful 200s: {success_count} | Throttled 429s: {throttled_count}")
    print(" Next: In the next 60s cycle, Guardrail Agent will classify this as RUNAWAY.")
    print("=" * 70)


if __name__ == "__main__":
    main()
