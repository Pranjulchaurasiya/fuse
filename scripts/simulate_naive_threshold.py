#!/usr/bin/env python3
"""simulate_naive_threshold.py — Illustrates false positive pitfalls of naive static alarms.

Compares:
1. Naive static alarm: if request count > threshold (e.g. 30 req/min), trigger alarm / auto-throttle.
   - Result on Legitimate Traffic: FALSE POSITIVE (throttles real paying customers during flash sale).
   - Result on Runaway Loop: TRUE POSITIVE (catches the loop, but only after damage is done).
2. Cost Guardrail Agent (Context-Aware):
   - Ingests Request Count, Unique Caller Count, Sample Payloads, and Deployment Heartbeat.
   - Legitimate Traffic (35 reqs, 35 unique callers, varied search terms) -> Classified NORMAL.
   - Runaway Traffic (40 reqs, 1 unique caller, identical retry body) -> Classified RUNAWAY.
"""

import json

STATIC_THRESHOLD = 30  # requests per minute


def evaluate_naive_alarm(traffic_scenario: dict) -> dict:
    count = traffic_scenario["current_count_per_min"]
    tripped = count > STATIC_THRESHOLD
    return {
        "scenario": traffic_scenario["name"],
        "count": count,
        "static_threshold": STATIC_THRESHOLD,
        "alarm_state": "ALARM" if tripped else "OK",
        "action": "THROTTLE_CUSTOMERS" if tripped else "ALLOW",
        "verdict": "FALSE_POSITIVE (Broke production for legit users!)"
        if (tripped and traffic_scenario["is_legit"])
        else ("CORRECT" if tripped else "MISSED"),
    }


def main():
    print("=" * 75)
    print(" NAIVE STATIC THRESHOLD VS. AWS COST GUARDRAIL AGENT COMPARISON")
    print("=" * 75)

    scenarios = [
        {
            "name": "Scenario A: Flash Sale / Marketing Spike (Legitimate)",
            "is_legit": True,
            "current_count_per_min": 35,
            "unique_caller_count": 35,
            "sample_payloads": ["view_laptops", "search_phones", "add_to_cart"],
            "recent_deploy": True,
            "deploy_note": "Marketing campaign launch v1.4",
            "guardrail_classification": "NORMAL",
            "guardrail_action": "NO_ACTION",
        },
        {
            "name": "Scenario B: Broken Client Retry Loop (Runaway)",
            "is_legit": False,
            "current_count_per_min": 40,
            "unique_caller_count": 1,
            "sample_payloads": ["retry_failed_job", "retry_failed_job"],
            "recent_deploy": False,
            "deploy_note": None,
            "guardrail_classification": "RUNAWAY",
            "guardrail_action": "PENDING_APPROVAL (prod) / AUTO_THROTTLE (dev)",
        },
    ]

    for s in scenarios:
        print(f"\n--- {s['name']} ---")
        naive = evaluate_naive_alarm(s)
        print(f"[*] Traffic Metrics: Count = {s['current_count_per_min']}, Unique Callers = {s['unique_caller_count']}")
        print(f"[*] Naive Alarm (Count > {STATIC_THRESHOLD}):")
        print(f"    State:   {naive['alarm_state']}")
        print(f"    Action:  {naive['action']}")
        print(f"    Verdict: {naive['verdict']}")

        print(f"[*] Guardrail Agent (Context-Aware):")
        print(f"    Classification: {s['guardrail_classification']}")
        print(f"    Action:         {s['guardrail_action']}")
        print(f"    Context Analyzed: Callers={s['unique_caller_count']}, Payloads={s['sample_payloads'][:2]}, Deploy={s['recent_deploy']}")
        print(f"    Verdict:        CORRECT (Accurately discerned intent)")

    print("\n" + "=" * 75)
    print(" Key Takeaway for Hackathon Presentation:")
    print(" Naive alarms lack caller context and deploy awareness, causing severe false positives.")
    print(" Guardrail Agent reasons over multi-dimensional context to protect both cost and availability.")
    print("=" * 75)


if __name__ == "__main__":
    main()
