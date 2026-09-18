#!/usr/bin/env python3
"""test_reasoner.py — Tests the Reasoner Lambda with Bedrock Converse API.

Performs two tests:
1. Normal High-Spike Anomaly Test:
   Sends a fabricated runaway loop payload (650 req/min, 1 caller, stuck retries, no deploy).
   Verifies and prints the exact Bedrock structured JSON response.
   Verifies the incident record in DynamoDB Incidents table.
2. Deliberate Failure Fallback Test:
   Forces an invalid model invocation to trigger an exception.
   Confirms the fail-closed fallback safely writes a RUNAWAY record to DynamoDB Incidents.
"""

import json
import time
import boto3

REGION_NAME = "ap-south-1"
FUNCTION_NAME = "guardrail-reasoner"
INCIDENTS_TABLE = "Incidents"

lambda_client = boto3.client("lambda", region_name=REGION_NAME)
dynamodb_resource = boto3.resource("dynamodb", region_name=REGION_NAME)
table = dynamodb_resource.Table(INCIDENTS_TABLE)


def test_fabricated_high_spike():
    print("=" * 70)
    print(" TEST 1: Fabricated High-Spike Anomaly (Bedrock Converse toolConfig)")
    print("=" * 70)

    payload = {
        "resource": "guardrail-demo-api",
        "stage": "prod",
        "current_count_per_min": 650,
        "baseline_count_per_min": 12.0,
        "delta": 638.0,
        "unique_caller_count": 1,
        "total_requests_in_window": 1950,
        "recent_deploy": False,
        "deploy_note": None,
        "sample_payloads": [
            '{"action":"retry_fetch","id":"x92"}',
            '{"action":"retry_fetch","id":"x92"}',
            '{"action":"retry_fetch","id":"x92"}',
        ],
    }

    print("[*] Invoking 'guardrail-reasoner' with high-spike payload:")
    print(json.dumps(payload, indent=2))

    resp = lambda_client.invoke(
        FunctionName=FUNCTION_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload),
    )

    result = json.loads(resp["Payload"].read().decode("utf-8"))
    status_code = result.get("statusCode")
    body = result.get("body", {})

    print(f"\n[+] Lambda StatusCode: {status_code}")
    print("\n--- ACTUAL BEDROCK RESPONSE JSON ---")
    print(json.dumps(body.get("raw_bedrock_response"), indent=2))
    print("------------------------------------")
    print(f"[+] Parsed Classification: {body.get('classification')}")
    print(f"[+] Confidence:            {body.get('confidence')}")
    print(f"[+] Explanation:           {body.get('explanation')}")
    print(f"[+] Fallback Triggered?    {body.get('is_fallback')}")

    # Verify in DynamoDB Incidents table
    incident_id = body.get("incident_id")
    print(f"\n[*] Querying DynamoDB '{INCIDENTS_TABLE}' for incident_id: {incident_id}...")
    db_resp = table.get_item(Key={"incident_id": incident_id})
    item = db_resp.get("Item")
    if item:
        print("[+] DynamoDB record confirmed:")
        print(json.dumps(item, indent=2, default=str))
    else:
        print("[-] FAILED: Item not found in DynamoDB Incidents table!")

    return incident_id


def test_deliberate_bedrock_failure():
    print("\n" + "=" * 70)
    print(" TEST 2: Deliberate Bedrock Failure (Testing Fail-Closed Fallback)")
    print("=" * 70)

    # Pass deliberate invalid model ID to trigger Bedrock exception
    payload = {
        "resource": "guardrail-demo-api",
        "stage": "prod",
        "current_count_per_min": 800,
        "baseline_count_per_min": 15.0,
        "delta": 785.0,
        "unique_caller_count": 1,
        "total_requests_in_window": 2400,
        "recent_deploy": False,
        "model_id": "invalid.non-existent.bedrock-model-id:0",
    }

    print("[*] Invoking 'guardrail-reasoner' with INVALID model_id to trigger failure:")
    print(f"    model_id: {payload['model_id']}")

    resp = lambda_client.invoke(
        FunctionName=FUNCTION_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload),
    )

    result = json.loads(resp["Payload"].read().decode("utf-8"))
    body = result.get("body", {})

    print(f"\n[+] Lambda StatusCode: {result.get('statusCode')}")
    print(f"[+] Fallback Triggered?    {body.get('is_fallback')} (EXPECTED: True)")
    print(f"[+] Classification:        {body.get('classification')} (EXPECTED: RUNAWAY)")
    print(f"[+] Confidence:            {body.get('confidence')}")
    print(f"[+] Explanation:           {body.get('explanation')}")

    # Verify in DynamoDB Incidents table
    incident_id = body.get("incident_id")
    print(f"\n[*] Querying DynamoDB '{INCIDENTS_TABLE}' for incident_id: {incident_id}...")
    db_resp = table.get_item(Key={"incident_id": incident_id})
    item = db_resp.get("Item")
    if item and item.get("classification") == "RUNAWAY" and item.get("is_fallback") is True:
        print("[+] SUCCESS: Fallback record safely written to DynamoDB Incidents table!")
        print(json.dumps(item, indent=2, default=str))
    else:
        print(f"[-] FAILED: Item not saved as expected: {item}")


def main():
    test_fabricated_high_spike()
    test_deliberate_bedrock_failure()
    print("\n" + "=" * 70)
    print(" [OK] Day 2 Reasoner & Fallback Verification Completed.")
    print("=" * 70)


if __name__ == "__main__":
    main()
