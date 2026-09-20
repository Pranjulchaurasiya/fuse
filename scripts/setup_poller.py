#!/usr/bin/env python3
"""setup_poller.py — Sets up the Poller Lambda and EventBridge 1-minute schedule.

This creates / configures:
1. IAM Role `guardrail-poller-role` with policies for CloudWatch GetMetricData,
   DynamoDB Deployments read, and basic Lambda logging.
2. Lambda function `guardrail-poller` (Python 3.12) packaging `lambdas/poller/handler.py`.
3. EventBridge rule `guardrail-poller-schedule` firing at `rate(1 minute)`.
4. EventBridge target and invoke permission on the Lambda function.
5. Verifies deployment with a live invocation.
"""

import io
import json
import os
import sys
import time
import zipfile
import boto3
from botocore.exceptions import ClientError

REGION_NAME = (
    os.environ.get("AWS_REGION")
    or os.environ.get("AWS_DEFAULT_REGION")
    or "ap-south-1"
)
ROLE_NAME = "guardrail-poller-role"
FUNCTION_NAME = "guardrail-poller"
RULE_NAME = "guardrail-poller-schedule"
SCHEDULE_EXPRESSION = "rate(1 minute)"


def get_lambda_zip() -> bytes:
    """Packages lambdas/poller/handler.py into an in-memory zip."""
    handler_path = os.path.join(
        os.path.dirname(__file__), "..", "lambdas", "poller", "handler.py"
    )
    with open(handler_path, "r", encoding="utf-8") as f:
        content = f.read()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("handler.py", content)
    buffer.seek(0)
    return buffer.read()


def ensure_poller_role(iam_client, sts_client) -> str:
    """Creates or updates the IAM role for the Poller Lambda."""
    account_id = sts_client.get_caller_identity()["Account"]
    assume_role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    try:
        resp = iam_client.get_role(RoleName=ROLE_NAME)
        role_arn = resp["Role"]["Arn"]
        print(f"[-] IAM Role '{ROLE_NAME}' already exists: {role_arn}")
    except iam_client.exceptions.NoSuchEntityException:
        print(f"[+] Creating IAM Role '{ROLE_NAME}'...")
        resp = iam_client.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(assume_role_policy),
            Description="Execution role for guardrail-poller Lambda",
        )
        role_arn = resp["Role"]["Arn"]
        print(f"[+] Created role: {role_arn}")
        # Wait for IAM role replication
        print("[*] Waiting 10s for IAM role replication...")
        time.sleep(10)

    # Attach basic execution role policy
    iam_client.attach_role_policy(
        RoleName=ROLE_NAME,
        PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    )

    # Read inline policy from poller-role.json
    policy_path = os.path.join(
        os.path.dirname(__file__), "..", "infra", "iam-policies", "poller-role.json"
    )
    with open(policy_path, "r", encoding="utf-8") as f:
        policy_doc = f.read()

    iam_client.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName="guardrail-poller-permissions",
        PolicyDocument=policy_doc,
    )
    print(f"[+] Attached inline policy 'guardrail-poller-permissions' to '{ROLE_NAME}'.")
    return role_arn


def ensure_poller_lambda(lambda_client, role_arn: str, zip_bytes: bytes) -> str:
    """Creates or updates the guardrail-poller Lambda function."""
    env_vars = {
        "Variables": {
            "API_NAME": "guardrail-demo-api",
            "STAGE_NAME": "prod",
            "DEPLOYMENTS_TABLE": "Deployments",
            "WINDOW_MINUTES": "15",
            "AWS_REGION_NAME": REGION_NAME,
        }
    }

    try:
        resp = lambda_client.get_function(FunctionName=FUNCTION_NAME)
        function_arn = resp["Configuration"]["FunctionArn"]
        print(f"[-] Lambda '{FUNCTION_NAME}' exists. Updating code and configuration...")
        lambda_client.update_function_code(
            FunctionName=FUNCTION_NAME,
            ZipFile=zip_bytes,
        )
        # Wait until update completes
        waiter = lambda_client.get_waiter("function_updated")
        waiter.wait(FunctionName=FUNCTION_NAME)

        lambda_client.update_function_configuration(
            FunctionName=FUNCTION_NAME,
            Role=role_arn,
            Handler="handler.lambda_handler",
            Runtime="python3.12",
            Timeout=15,
            MemorySize=128,
            Environment=env_vars,
        )
        waiter.wait(FunctionName=FUNCTION_NAME)
        print(f"[+] Lambda '{FUNCTION_NAME}' updated successfully.")
        return function_arn
    except lambda_client.exceptions.ResourceNotFoundException:
        print(f"[+] Creating Lambda '{FUNCTION_NAME}'...")
        # Handle possible delay in newly created role replication
        for attempt in range(5):
            try:
                resp = lambda_client.create_function(
                    FunctionName=FUNCTION_NAME,
                    Runtime="python3.12",
                    Role=role_arn,
                    Handler="handler.lambda_handler",
                    Code={"ZipFile": zip_bytes},
                    Description="Guardrail metrics poller Lambda",
                    Timeout=15,
                    MemorySize=128,
                    Environment=env_vars,
                )
                function_arn = resp["FunctionArn"]
                print(f"[+] Lambda '{FUNCTION_NAME}' created: {function_arn}")
                waiter = lambda_client.get_waiter("function_active_v2")
                waiter.wait(FunctionName=FUNCTION_NAME)
                return function_arn
            except ClientError as err:
                if "InvalidParameterValueException" in str(err) and attempt < 4:
                    print(f"[*] Role replication in progress, waiting 5s (attempt {attempt+1}/5)...")
                    time.sleep(5)
                else:
                    raise


def ensure_eventbridge_schedule(events_client, lambda_client, function_arn: str, account_id: str):
    """Creates the EventBridge 1-minute schedule rule and wires it to the Lambda."""
    print(f"[+] Creating / updating EventBridge rule '{RULE_NAME}' with '{SCHEDULE_EXPRESSION}'...")
    rule_resp = events_client.put_rule(
        Name=RULE_NAME,
        ScheduleExpression=SCHEDULE_EXPRESSION,
        State="ENABLED",
        Description="Fires guardrail-poller Lambda every 1 minute to check metrics",
    )
    rule_arn = rule_resp["RuleArn"]
    print(f"[+] Rule ARN: {rule_arn}")

    # Add permission for EventBridge to invoke Lambda
    statement_id = "eventbridge-guardrail-poller-schedule"
    try:
        lambda_client.add_permission(
            FunctionName=FUNCTION_NAME,
            StatementId=statement_id,
            Action="lambda:InvokeFunction",
            Principal="events.amazonaws.com",
            SourceArn=rule_arn,
        )
        print(f"[+] Granted EventBridge invocation permission to '{FUNCTION_NAME}'.")
    except ClientError as e:
        if "ResourceConflictException" in str(e):
            print(f"[-] Invocation permission '{statement_id}' already exists.")
        else:
            raise

    # Add Lambda as target
    events_client.put_targets(
        Rule=RULE_NAME,
        Targets=[
            {
                "Id": "1",
                "Arn": function_arn,
            }
        ],
    )
    print(f"[+] Wired '{FUNCTION_NAME}' as target 1 for rule '{RULE_NAME}'.")


def test_invoke_poller(lambda_client):
    """Performs a test invocation of the Poller Lambda."""
    print("[*] Performing test invocation of 'guardrail-poller'...")
    resp = lambda_client.invoke(
        FunctionName=FUNCTION_NAME,
        InvocationType="RequestResponse",
    )
    status_code = resp.get("StatusCode")
    payload = json.loads(resp["Payload"].read().decode("utf-8"))
    print(f"[+] Invocation StatusCode: {status_code}")
    print(f"[+] Payload: {json.dumps(payload, indent=2)}")


def main():
    print("=" * 60)
    print(" AWS Cost Guardrail — Setup Poller Lambda & EventBridge")
    print(f" Region: {REGION_NAME}")
    print("=" * 60)

    sts_client = boto3.client("sts", region_name=REGION_NAME)
    account_id = sts_client.get_caller_identity()["Account"]
    print(f"[-] AWS Account ID: {account_id}")

    iam_client = boto3.client("iam", region_name=REGION_NAME)
    lambda_client = boto3.client("lambda", region_name=REGION_NAME)
    events_client = boto3.client("events", region_name=REGION_NAME)

    role_arn = ensure_poller_role(iam_client, sts_client)
    zip_bytes = get_lambda_zip()
    function_arn = ensure_poller_lambda(lambda_client, role_arn, zip_bytes)
    ensure_eventbridge_schedule(events_client, lambda_client, function_arn, account_id)

    test_invoke_poller(lambda_client)

    print("\n[OK] Day 1 Poller & EventBridge setup completed successfully.")


if __name__ == "__main__":
    main()
