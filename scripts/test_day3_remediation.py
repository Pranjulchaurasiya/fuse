#!/usr/bin/env python3
"""test_day3_remediation.py — Full live test of Day 3 remediation & approval pipeline.

Executes and verifies:
1. Triggers Reasoner with a RUNAWAY loop scenario in 'prod' stage.
2. Confirms 'prod' path correctly WITHHOLDS action:
   - Sets action_taken: 'PENDING_APPROVAL'
   - Writes a PENDING record to DynamoDB 'ApprovalQueue' table.
   - Demo API Gateway is still UNTHROTTLED (curl returns 200).
3. Queries GET /incidents via the live Control API Gateway to verify dashboard contract.
4. Approves the incident via live POST /incidents/{incident_id}/approve:
   - Flips ApprovalQueue record to 'APPROVED'.
   - Triggers Remediator Lambda to throttle demo API Gateway stage to 0 rps.
5. Verifies Throttling Live:
   - Sends real HTTP request to the demo API -> receives 429 Too Many Requests!
6. Verifies Idempotency:
   - Invokes Remediator a 2nd time on the same incident -> confirms ALREADY_THROTTLED output without error.
7. Restores demo API stage throttle back to baseline (RateLimit=1000, BurstLimit=2000).
"""

import json
import time
import urllib.error
import urllib.request
import boto3

REGION_NAME = "ap-south-1"
DEMO_API_URL = "https://poim5xmgs2.execute-api.ap-south-1.amazonaws.com/prod/items"
DEMO_API_ID = "poim5xmgs2"
STAGE_NAME = "prod"

lambda_client = boto3.client("lambda", region_name=REGION_NAME)
apigw_client = boto3.client("apigateway", region_name=REGION_NAME)
dynamodb = boto3.resource("dynamodb", region_name=REGION_NAME)
approval_table = dynamodb.Table("ApprovalQueue")
incidents_table = dynamodb.Table("Incidents")


def get_control_api_url() -> str:
    apis = apigw_client.get_rest_apis().get("items", [])
    for a in apis:
        if a["name"] == "guardrail-control-api":
            return f"https://{a['id']}.execute-api.{REGION_NAME}.amazonaws.com/prod"
    raise RuntimeError("guardrail-control-api not found! Run setup_day3.py first.")


def reset_stage_throttle_to_baseline():
    """Resets the demo API prod stage throttling to normal high values (1000/2000)."""
    patch_ops = [
        {"op": "replace", "path": "/*/*/throttling/rateLimit", "value": "1000"},
        {"op": "replace", "path": "/*/*/throttling/burstLimit", "value": "2000"},
    ]
    apigw_client.update_stage(
        restApiId=DEMO_API_ID,
        stageName=STAGE_NAME,
        patchOperations=patch_ops,
    )
    print(f"[*] Reset '{DEMO_API_ID}' [{STAGE_NAME}] throttle to baseline (Rate: 1000, Burst: 2000).")
    # Wait for edge cache to reflect unthrottled status
    for attempt in range(1, 16):
        time.sleep(2)
        code, _ = http_get(DEMO_API_URL)
        if code == 200:
            print(f"[*] Baseline restored: Demo API returned 200 OK after {attempt * 2}s.")
            return 200
        print(f"[*] Waiting for unthrottle propagation... attempt {attempt} status = {code}")
    return code


def http_get(url: str):
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def http_post(url: str, payload_obj: dict):
    data = json.dumps(payload_obj).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def test_full_remediation_pipeline():
    print("=" * 70)
    print(" DAY 3 REMEDIATION & APPROVAL GATE — LIVE VERIFICATION")
    print("=" * 70)

    control_api_url = get_control_api_url()
    print(f"[-] Control API: {control_api_url}")
    print(f"[-] Demo API:    {DEMO_API_URL}")

    # Ensure clean baseline
    reset_stage_throttle_to_baseline()

    # Step 1: Confirm Demo API responds 200 initially
    print("\n" + "-" * 70)
    print(" STEP 1: Confirm Demo API is UNTHROTTLED (200 OK)")
    print("-" * 70)
    code, body = http_get(DEMO_API_URL)
    print(f"[+] Demo API HTTP Status: {code}")
    print(f"[+] Demo API Response:    {body}")
    assert code == 200, f"Expected 200 OK before throttling, got {code}"

    # Step 2: Trigger Reasoner with RUNAWAY scenario in prod
    print("\n" + "-" * 70)
    print(" STEP 2: Trigger Reasoner on 'prod' stage (Expect RUNAWAY + Withheld Action)")
    print("-" * 70)
    runaway_payload = {
        "resource": "guardrail-demo-api",
        "stage": "prod",
        "current_count_per_min": 750,
        "baseline_count_per_min": 10.0,
        "delta": 740.0,
        "unique_caller_count": 1,
        "total_requests_in_window": 2250,
        "recent_deploy": False,
        "deploy_note": None,
        "sample_payloads": [
            '{"action":"runaway_loop","attempt":991}',
            '{"action":"runaway_loop","attempt":992}',
        ],
    }

    reasoner_resp = lambda_client.invoke(
        FunctionName="guardrail-reasoner",
        InvocationType="RequestResponse",
        Payload=json.dumps(runaway_payload),
    )
    res_body = json.loads(reasoner_resp["Payload"].read().decode("utf-8")).get("body", {})
    incident_id = res_body["incident_id"]

    print(f"[+] Incident ID:    {incident_id}")
    print(f"[+] Classification: {res_body.get('classification')} (Expected: RUNAWAY)")
    print(f"[+] Action Taken:   {res_body.get('action_taken')} (Expected: PENDING_APPROVAL)")
    print(f"[+] Explanation:    {res_body.get('explanation')}")

    assert res_body.get("classification") == "RUNAWAY"
    assert res_body.get("action_taken") == "PENDING_APPROVAL"

    # Step 3: Verify DynamoDB ApprovalQueue has PENDING record
    print("\n" + "-" * 70)
    print(" STEP 3: Verify DynamoDB 'ApprovalQueue' record (PENDING)")
    print("-" * 70)
    q_item = approval_table.get_item(Key={"approval_id": incident_id}).get("Item")
    print(f"[+] ApprovalQueue Record for {incident_id}:")
    print(json.dumps(q_item, indent=2, default=str))
    assert q_item is not None
    assert q_item.get("status") == "PENDING"

    # Step 4: Verify Demo API is STILL UNTHROTTLED (human gate holds action)
    print("\n" + "-" * 70)
    print(" STEP 4: Verify Demo API is STILL UNTHROTTLED (Prod action was withheld)")
    print("-" * 70)
    code, body = http_get(DEMO_API_URL)
    print(f"[+] Demo API HTTP Status: {code} (Expected: 200 OK)")
    assert code == 200

    # Step 5: Test GET /incidents on live Control API
    print("\n" + "-" * 70)
    print(f" STEP 5: Call GET {control_api_url}/incidents via Control API")
    print("-" * 70)
    inc_code, inc_body = http_get(f"{control_api_url}/incidents")
    print(f"[+] GET /incidents Status: {inc_code}")
    incidents_list = inc_body.get("incidents", [])
    print(f"[+] Total incidents returned: {len(incidents_list)}")
    matched = [inc for inc in incidents_list if inc.get("incident_id") == incident_id]
    assert len(matched) > 0, "Current incident not found in GET /incidents response!"
    print(f"[+] Verified current incident {incident_id} is present in incident log.")

    # Step 6: Call POST /incidents/{incident_id}/approve via live Control API
    print("\n" + "-" * 70)
    print(f" STEP 6: Call POST {control_api_url}/incidents/{incident_id}/approve (Human Approval)")
    print("-" * 70)
    approve_url = f"{control_api_url}/incidents/{incident_id}/approve"
    app_code, app_body = http_post(approve_url, {"resolved_by": "Pranjul", "decision": "APPROVED"})
    print(f"[+] POST /approve Status: {app_code}")
    print(f"[+] POST /approve Body:   {json.dumps(app_body, indent=2)}")
    assert app_code == 200
    assert app_body.get("status") == "APPROVED"
    assert app_body.get("throttled") is True

    # Step 7: Verify ApprovalQueue and Incidents tables updated
    print("\n" + "-" * 70)
    print(" STEP 7: Verify DynamoDB state updated to APPROVED")
    print("-" * 70)
    q_updated = approval_table.get_item(Key={"approval_id": incident_id}).get("Item")
    inc_updated = incidents_table.get_item(Key={"incident_id": incident_id}).get("Item")
    print(f"[+] ApprovalQueue status: {q_updated.get('status')} (resolved_by={q_updated.get('resolved_by')})")
    print(f"[+] Incidents action_taken: {inc_updated.get('action_taken')}")
    assert q_updated.get("status") == "APPROVED"
    assert inc_updated.get("action_taken") == "APPROVED_AND_THROTTLED"

    # Step 8: Live Curl Verification — Confirm 429 Too Many Requests
    print("\n" + "-" * 70)
    print(" STEP 8: Live Request Verification — Confirm Demo API is THROTTLED (429/503)")
    print("-" * 70)
    # Allow API Gateway regional edge caches to propagate stage throttle (typically 5-10s)
    t_code = None
    t_body = None
    for attempt in range(1, 11):
        time.sleep(2)
        t_code, t_body = http_get(DEMO_API_URL)
        print(f"[+] Attempt {attempt}: Demo API status = {t_code}")
        if t_code == 429:
            break

    print(f"[+] Demo API Final Request Status after approval: {t_code}")
    print(f"[+] Demo API Response Body: {t_body}")
    assert t_code == 429, f"Expected 429 Too Many Requests, got {t_code}"
    print("[+] SUCCESS: API Gateway stage was throttled to 0 rps. Real request returned 429!")

    # Step 9: Verify Idempotency on Remediator
    print("\n" + "-" * 70)
    print(" STEP 9: Verify Idempotency — Calling Remediator when already throttled")
    print("-" * 70)
    rem_resp2 = lambda_client.invoke(
        FunctionName="guardrail-remediator",
        InvocationType="RequestResponse",
        Payload=json.dumps({"incident_id": incident_id, "resource": "guardrail-demo-api", "stage": "prod"}),
    )
    rem_body2 = json.loads(rem_resp2["Payload"].read().decode("utf-8")).get("body", {})
    print(f"[+] Remediator 2nd invocation result: {json.dumps(rem_body2, indent=2)}")
    assert rem_body2.get("status") == "ALREADY_THROTTLED"
    print("[+] SUCCESS: Remediator confirmed idempotent (returned ALREADY_THROTTLED without error).")

    # Step 10: Clean up — restore baseline throttle so demo API is ready for future tests
    print("\n" + "-" * 70)
    print(" STEP 10: Restoring Demo API Stage Throttle to Baseline")
    print("-" * 70)
    c_final = reset_stage_throttle_to_baseline()
    print(f"[+] Demo API restored status: {c_final} (Expected: 200 OK)")
    assert c_final == 200

    print("\n" + "=" * 70)
    print(" [ALL TESTS PASSED] DAY 3 REMEDIATION & APPROVAL GATE VERIFIED LIVE!")
    print("=" * 70)


if __name__ == "__main__":
    test_full_remediation_pipeline()
