#!/usr/bin/env python3
"""load_test_legit.py — Simulates legitimate user traffic with many unique callers and varied payloads.

Performs:
1. Sends 35 distinct HTTP POST requests to the demo API Gateway endpoint.
2. For each request:
   - Sets distinct `X-Caller-ID` and `X-Forwarded-For` headers to simulate distinct client IPs/users.
   - Sets distinct `User-Agent`.
   - Sends diverse, non-repeating JSON payloads (search queries, catalog views, item additions).
3. Verifies that all requests receive 200 OK.
"""

import json
import time
import urllib.request

API_URL = "https://poim5xmgs2.execute-api.ap-south-1.amazonaws.com/prod/items"
NUM_REQUESTS = 35


def main():
    print("=" * 70)
    print(f" Simulating Legitimate Traffic ({NUM_REQUESTS} distinct callers & diverse payloads)")
    print(f" Target: {API_URL}")
    print("=" * 70)

    success_count = 0
    categories = ["laptops", "phones", "audio", "displays", "accessories", "keyboards"]
    actions = ["view_item", "search_catalog", "add_to_cart", "read_reviews", "filter_brand"]

    for i in range(1, NUM_REQUESTS + 1):
        caller_id = f"client-node-{i:03d}"
        simulated_ip = f"198.51.100.{i}"
        action = actions[i % len(actions)]
        category = categories[i % len(categories)]

        payload_obj = {
            "action": action,
            "category": category,
            "item_id": 5000 + i,
            "session_id": f"sess-{i:04d}",
            "caller": caller_id,
            "timestamp": int(time.time()),
        }
        payload_bytes = json.dumps(payload_obj).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "X-Caller-ID": caller_id,
            "X-Forwarded-For": simulated_ip,
            "User-Agent": f"Mozilla/5.0 (Client {i}; Synthetic Legitimate User)",
        }

        req = urllib.request.Request(API_URL, data=payload_bytes, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    success_count += 1
                    if i % 5 == 0 or i == NUM_REQUESTS:
                        print(f"  [+] Sent {i}/{NUM_REQUESTS} requests... (caller={caller_id}, ip={simulated_ip})")
        except Exception as e:
            print(f"  [-] Request {i} failed: {e}")

        # Small delay between user clicks
        time.sleep(0.04)

    print("\n" + "=" * 70)
    print(f" Completed! Sent {success_count}/{NUM_REQUESTS} successful requests to demo API.")
    print(" Next: Wait for EventBridge to trigger guardrail-poller on its 1-minute schedule.")
    print("=" * 70)


if __name__ == "__main__":
    main()
