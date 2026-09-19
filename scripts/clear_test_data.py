#!/usr/bin/env python3
"""clear_test_data.py — Resets demo environment cleanly for demo recording.

Actions:
1. Wipes all items from DynamoDB 'Incidents' table.
2. Wipes all items from DynamoDB 'ApprovalQueue' table.
3. Resets 'guardrail-demo-api' stage 'prod' and 'dev' throttles to baseline (Rate: 1000, Burst: 2000).
4. Seeds a clean initial deployment heartbeat into 'Deployments' table so poller has valid baseline context.
"""

import boto3
import time

REGION_NAME = "ap-south-1"
DEMO_API_NAME = "guardrail-demo-api"

dynamodb = boto3.resource("dynamodb", region_name=REGION_NAME)
apigw = boto3.client("apigateway", region_name=REGION_NAME)

incidents_table = dynamodb.Table("Incidents")
approval_table = dynamodb.Table("ApprovalQueue")
deployments_table = dynamodb.Table("Deployments")


def wipe_table(table, key_name):
    """Scans and deletes all items from the specified DynamoDB table."""
    deleted_count = 0
    scan = table.scan(ProjectionExpression=key_name)
    items = scan.get("Items", [])
    while True:
        with table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={key_name: item[key_name]})
                deleted_count += 1
        if "LastEvaluatedKey" in scan:
            scan = table.scan(
                ProjectionExpression=key_name,
                ExclusiveStartKey=scan["LastEvaluatedKey"],
            )
            items = scan.get("Items", [])
        else:
            break
    print(f"[+] Wiped {deleted_count} items from '{table.name}'.")


def reset_api_throttles():
    """Resets throttling on prod and dev stages of demo API to 1000/2000."""
    apis = apigw.get_rest_apis().get("items", [])
    demo_id = None
    for a in apis:
        if a["name"] == DEMO_API_NAME:
            demo_id = a["id"]
            break

    if not demo_id:
        print(f"[-] Could not find REST API named {DEMO_API_NAME}")
        return

    patch_ops = [
        {"op": "replace", "path": "/*/*/throttling/rateLimit", "value": "1000"},
        {"op": "replace", "path": "/*/*/throttling/burstLimit", "value": "2000"},
    ]

    for stage_name in ["prod", "dev"]:
        try:
            apigw.update_stage(
                restApiId=demo_id,
                stageName=stage_name,
                patchOperations=patch_ops,
            )
            print(f"[+] Reset API '{demo_id}' [{stage_name}] throttle to baseline (Rate: 1000, Burst: 2000).")
        except Exception as e:
            print(f"[-] Note for stage '{stage_name}': {e}")


def seed_clean_deployment():
    """Seeds a fresh baseline deployment heartbeat."""
    import uuid

    now = int(time.time())
    item = {
        "deployment_id": str(uuid.uuid4()),
        "resource": DEMO_API_NAME,
        "timestamp": now - 3600,  # 1 hour ago
        "note": "Clean baseline deployment for demo recording",
    }
    deployments_table.put_item(Item=item)
    print(f"[+] Seeded clean deployment heartbeat for '{DEMO_API_NAME}'.")


def main():
    print("=" * 70)
    print(" RESETTING AWS COST GUARDRAIL DEMO ENVIRONMENT TO CLEAN SLATE")
    print("=" * 70)

    print("[*] Wiping DynamoDB Incidents...")
    wipe_table(incidents_table, "incident_id")

    print("[*] Wiping DynamoDB ApprovalQueue...")
    wipe_table(approval_table, "approval_id")

    print("[*] Restoring API Gateway throttles...")
    reset_api_throttles()

    print("[*] Seeding clean deployment heartbeat...")
    seed_clean_deployment()

    print("=" * 70)
    print(" [CLEAN SLATE READY] All test clutter wiped, ready for demo recording.")
    print("=" * 70)


if __name__ == "__main__":
    main()
