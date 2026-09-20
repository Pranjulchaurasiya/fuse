#!/usr/bin/env python3
"""setup_reasoner.py — Deploys the Reasoner Lambda function.

Creates:
1. IAM Role `guardrail-reasoner-role` with Bedrock invoke and DynamoDB Incidents/Deployments permissions.
2. Lambda function `guardrail-reasoner` packaging `lambdas/reasoner/handler.py`.
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
ROLE_NAME = "guardrail-reasoner-role"
FUNCTION_NAME = "guardrail-reasoner"
BEDROCK_MODEL_ID = (
    os.environ.get("BEDROCK_MODEL_ID")
    or ("apac.amazon.nova-micro-v1:0" if REGION_NAME == "ap-south-1" else "us.amazon.nova-micro-v1:0")
)


def get_lambda_zip() -> bytes:
    """Packages lambdas/reasoner/handler.py into an in-memory zip."""
    handler_path = os.path.join(
        os.path.dirname(__file__), "..", "lambdas", "reasoner", "handler.py"
    )
    with open(handler_path, "r", encoding="utf-8") as f:
        content = f.read()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("handler.py", content)
    buffer.seek(0)
    return buffer.read()


def ensure_reasoner_role(iam_client, sts_client) -> str:
    """Creates or updates the IAM role for the Reasoner Lambda."""
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
            Description="Execution role for guardrail-reasoner Lambda",
        )
        role_arn = resp["Role"]["Arn"]
        print(f"[+] Created role: {role_arn}")
        print("[*] Waiting 10s for IAM role replication...")
        time.sleep(10)

    # Attach basic execution role policy
    iam_client.attach_role_policy(
        RoleName=ROLE_NAME,
        PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    )

    # Read inline policy from reasoner-role.json
    policy_path = os.path.join(
        os.path.dirname(__file__), "..", "infra", "iam-policies", "reasoner-role.json"
    )
    with open(policy_path, "r", encoding="utf-8") as f:
        policy_doc = f.read()

    iam_client.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName="guardrail-reasoner-permissions",
        PolicyDocument=policy_doc,
    )
    print(f"[+] Attached inline policy 'guardrail-reasoner-permissions' to '{ROLE_NAME}'.")
    return role_arn


def ensure_reasoner_lambda(lambda_client, role_arn: str, zip_bytes: bytes) -> str:
    """Creates or updates the guardrail-reasoner Lambda function."""
    env_vars = {
        "Variables": {
            "BEDROCK_REGION": REGION_NAME,
            "BEDROCK_MODEL_ID": BEDROCK_MODEL_ID,
            "INCIDENTS_TABLE": "Incidents",
            "DEPLOYMENTS_TABLE": "Deployments",
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
        waiter = lambda_client.get_waiter("function_updated")
        waiter.wait(FunctionName=FUNCTION_NAME)

        lambda_client.update_function_configuration(
            FunctionName=FUNCTION_NAME,
            Role=role_arn,
            Handler="handler.lambda_handler",
            Runtime="python3.12",
            Timeout=25,
            MemorySize=256,
            Environment=env_vars,
        )
        waiter.wait(FunctionName=FUNCTION_NAME)
        print(f"[+] Lambda '{FUNCTION_NAME}' updated successfully.")
        return function_arn
    except lambda_client.exceptions.ResourceNotFoundException:
        print(f"[+] Creating Lambda '{FUNCTION_NAME}'...")
        for attempt in range(5):
            try:
                resp = lambda_client.create_function(
                    FunctionName=FUNCTION_NAME,
                    Runtime="python3.12",
                    Role=role_arn,
                    Handler="handler.lambda_handler",
                    Code={"ZipFile": zip_bytes},
                    Description="Guardrail Bedrock anomaly reasoner Lambda",
                    Timeout=25,
                    MemorySize=256,
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


def main():
    print("=" * 60)
    print(" AWS Cost Guardrail — Setup Reasoner Lambda")
    print(f" Region: {REGION_NAME} | Model: {BEDROCK_MODEL_ID}")
    print("=" * 60)

    sts_client = boto3.client("sts", region_name=REGION_NAME)
    iam_client = boto3.client("iam", region_name=REGION_NAME)
    lambda_client = boto3.client("lambda", region_name=REGION_NAME)

    role_arn = ensure_reasoner_role(iam_client, sts_client)
    zip_bytes = get_lambda_zip()
    function_arn = ensure_reasoner_lambda(lambda_client, role_arn, zip_bytes)

    print(f"\n[OK] Reasoner Lambda ready: {function_arn}")


if __name__ == "__main__":
    main()
