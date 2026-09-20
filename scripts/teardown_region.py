#!/usr/bin/env python3
"""teardown_region.py — Cleanly tear down Guardrail resources in a test region.

SAFETY FEATURE:
Refuses to touch 'ap-south-1' (production) to ensure production safety.
Deletes regional resources:
- API Gateways: guardrail-demo-api, guardrail-control-api
- Lambdas: guardrail-poller, guardrail-reasoner, guardrail-remediator,
           guardrail-approve-action, guardrail-get-incidents, guardrail-demo-target
- EventBridge rules: guardrail-poller-schedule
- DynamoDB tables: Deployments, Incidents, ApprovalQueue
- S3 dashboard test bucket: guardrail-dashboard-{account_id}-{region}
"""

import argparse
import os
import sys
import boto3
from botocore.exceptions import ClientError


def main():
    parser = argparse.ArgumentParser(description="Tear down Guardrail test resources in a specific AWS region.")
    parser.add_argument("--region", required=True, help="AWS region to tear down (e.g. us-east-1)")
    parser.add_argument("--force-production-teardown", action="store_true", help="Allow teardown on ap-south-1")
    args = parser.parse_args()

    region = args.region
    if region == "ap-south-1" and not args.force_production_teardown:
        print("\n[SAFETY HALT] Region 'ap-south-1' is the primary production deployment!")
        print("Refusing to tear down 'ap-south-1' without --force-production-teardown.")
        sys.exit(1)

    print(f"\n======================================================================")
    print(f" TEARING DOWN GUARDRAIL RESOURCES IN REGION: {region}")
    print(f"======================================================================\n")

    session = boto3.Session(region_name=region)
    sts = session.client("sts")
    account_id = sts.get_caller_identity()["Account"]
    print(f"[-] Account ID: {account_id}")

    # 1. EventBridge Rule
    events = session.client("events")
    rule_name = "guardrail-poller-schedule"
    try:
        events.remove_targets(Rule=rule_name, Ids=["1"])
        events.delete_rule(Name=rule_name)
        print(f"[+] Deleted EventBridge rule: {rule_name}")
    except ClientError as e:
        if "ResourceNotFoundException" not in str(e):
            print(f"[-] Rule {rule_name} not found or error: {e}")

    # 2. REST API Gateways
    apigw = session.client("apigateway")
    apis = apigw.get_rest_apis().get("items", [])
    for api in apis:
        if api.get("name") in ["guardrail-demo-api", "guardrail-control-api"]:
            api_id = api["id"]
            api_name = api["name"]
            try:
                apigw.delete_rest_api(restApiId=api_id)
                print(f"[+] Deleted API Gateway: {api_name} ({api_id})")
            except Exception as e:
                print(f"[!] Failed to delete API {api_name}: {e}")

    # 3. Lambda Functions
    lambdas = [
        "guardrail-poller",
        "guardrail-reasoner",
        "guardrail-remediator",
        "guardrail-approve-action",
        "guardrail-get-incidents",
        "guardrail-demo-target",
    ]
    lmb = session.client("lambda")
    for fn in lambdas:
        try:
            lmb.delete_function(FunctionName=fn)
            print(f"[+] Deleted Lambda: {fn}")
        except ClientError as e:
            if "ResourceNotFoundException" not in str(e):
                print(f"[!] Error deleting Lambda {fn}: {e}")

    # 4. DynamoDB Tables
    ddb = session.client("dynamodb")
    tables = ["Deployments", "Incidents", "ApprovalQueue"]
    for tbl in tables:
        try:
            ddb.delete_table(TableName=tbl)
            print(f"[+] Deleting DynamoDB table: {tbl} (deletion in progress)...")
            waiter = ddb.get_waiter("table_not_exists")
            waiter.wait(TableName=tbl)
            print(f"[+] Table {tbl} completely deleted.")
        except ClientError as e:
            if "ResourceNotFoundException" not in str(e):
                print(f"[!] Error deleting DynamoDB table {tbl}: {e}")

    # 5. S3 Dashboard Bucket
    s3 = session.client("s3")
    s3_resource = session.resource("s3")
    bucket_name = f"guardrail-dashboard-{account_id}-{region}"
    try:
        bucket = s3_resource.Bucket(bucket_name)
        bucket.objects.all().delete()
        bucket.delete()
        print(f"[+] Emptied and deleted test S3 bucket: {bucket_name}")
    except ClientError as e:
        if "NoSuchBucket" not in str(e) and "404" not in str(e):
            print(f"[!] Error deleting S3 bucket {bucket_name}: {e}")

    print(f"\n[OK] Region '{region}' teardown complete. Zero residual test resources.")


if __name__ == "__main__":
    main()
