#!/usr/bin/env python3
"""setup_demo_api.py — Sets up the demo API Gateway + backing Lambda.

This creates:
1. An IAM role for the demo Lambda (basic execution permissions)
2. A trivial backing Lambda function (`guardrail-demo-target`) from `lambdas/demo_api/handler.py`
3. A regional REST API Gateway (`guardrail-demo-api`)
4. An ANY /{proxy+} proxy method routed to the Lambda via AWS_PROXY integration
5. A deployment to stage `prod` with baseline throttle (1000 rps, 2000 burst)
6. Lambda invocation permission for API Gateway
"""

import io
import json
import os
import sys
import time
import zipfile
import boto3
from botocore.exceptions import ClientError


def get_lambda_zip() -> bytes:
    """Packages lambdas/demo_api/handler.py into an in-memory zip."""
    handler_path = os.path.join(
        os.path.dirname(__file__), "..", "lambdas", "demo_api", "handler.py"
    )
    with open(handler_path, "r", encoding="utf-8") as f:
        content = f.read()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("handler.py", content)
    buffer.seek(0)
    return buffer.read()


def ensure_lambda_role(iam_client, role_name: str) -> str:
    """Creates or fetches the basic execution IAM role for the Lambda."""
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
        resp = iam_client.get_role(RoleName=role_name)
        print(f"[-] IAM Role '{role_name}' exists.")
        return resp["Role"]["Arn"]
    except iam_client.exceptions.NoSuchEntityException:
        print(f"[+] Creating IAM Role '{role_name}'...")
        resp = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(assume_role_policy),
            Description="Execution role for guardrail-demo-target Lambda",
        )
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        )
        print(f"[+] Attached AWSLambdaBasicExecutionRole. Waiting 10s for IAM propagation...")
        time.sleep(10)
        return resp["Role"]["Arn"]


def ensure_demo_lambda(lambda_client, iam_client, function_name: str) -> str:
    """Creates or updates the demo Lambda function."""
    role_name = f"{function_name}-role"
    role_arn = ensure_lambda_role(iam_client, role_name)
    zip_bytes = get_lambda_zip()

    try:
        resp = lambda_client.get_function(FunctionName=function_name)
        print(f"[-] Lambda function '{function_name}' exists. Updating code...")
        lambda_client.update_function_code(
            FunctionName=function_name,
            ZipFile=zip_bytes,
        )
        return resp["Configuration"]["FunctionArn"]
    except lambda_client.exceptions.ResourceNotFoundException:
        print(f"[+] Creating Lambda function '{function_name}'...")
        resp = lambda_client.create_function(
            FunctionName=function_name,
            Runtime="python3.12",
            Role=role_arn,
            Handler="handler.lambda_handler",
            Code={"ZipFile": zip_bytes},
            Description="Trivial backing workload for guardrail-demo-api",
            Timeout=10,
            MemorySize=128,
        )
        return resp["FunctionArn"]


def ensure_demo_api_gateway(apigw_client, lambda_client, function_arn: str, region: str, account_id: str = "") -> tuple[str, str]:
    """Creates REST API, /{proxy+} route, AWS_PROXY integration, deploys to stage 'prod'."""
    api_name = "guardrail-demo-api"

    # Check if API already exists
    apis = apigw_client.get_rest_apis()
    api_id = None
    for item in apis.get("items", []):
        if item.get("name") == api_name:
            api_id = item["id"]
            print(f"[-] REST API '{api_name}' already exists (id: {api_id}).")
            break

    if not api_id:
        print(f"[+] Creating REST API '{api_name}'...")
        api_resp = apigw_client.create_rest_api(
            name=api_name,
            description="Protected demo API for AWS Cost Guardrail",
            endpointConfiguration={"types": ["REGIONAL"]},
        )
        api_id = api_resp["id"]

    # Get root resource id
    resources = apigw_client.get_resources(restApiId=api_id)
    root_id = None
    proxy_resource_id = None
    for r in resources["items"]:
        if r["path"] == "/":
            root_id = r["id"]
        elif r["path"] == "/{proxy+}":
            proxy_resource_id = r["id"]

    # Create /{proxy+} resource if not existing
    if not proxy_resource_id:
        print("[+] Creating /{proxy+} resource...")
        res = apigw_client.create_resource(
            restApiId=api_id,
            parentId=root_id,
            pathPart="{proxy+}",
        )
        proxy_resource_id = res["id"]

    # Setup ANY method on /{proxy+}
    uri = f"arn:aws:apigateway:{region}:lambda:path/2015-03-31/functions/{function_arn}/invocations"
    try:
        apigw_client.get_method(restApiId=api_id, resourceId=proxy_resource_id, httpMethod="ANY")
    except apigw_client.exceptions.NotFoundException:
        print("[+] Creating ANY method on /{proxy+}...")
        apigw_client.put_method(
            restApiId=api_id,
            resourceId=proxy_resource_id,
            httpMethod="ANY",
            authorizationType="NONE",
        )
        apigw_client.put_integration(
            restApiId=api_id,
            resourceId=proxy_resource_id,
            httpMethod="ANY",
            type="AWS_PROXY",
            integrationHttpMethod="POST",
            uri=uri,
        )

    # Setup ANY method on root /
    try:
        apigw_client.get_method(restApiId=api_id, resourceId=root_id, httpMethod="ANY")
    except apigw_client.exceptions.NotFoundException:
        print("[+] Creating ANY method on root /...")
        apigw_client.put_method(
            restApiId=api_id,
            resourceId=root_id,
            httpMethod="ANY",
            authorizationType="NONE",
        )
        apigw_client.put_integration(
            restApiId=api_id,
            resourceId=root_id,
            httpMethod="ANY",
            type="AWS_PROXY",
            integrationHttpMethod="POST",
            uri=uri,
        )

    # Grant Lambda permission for API Gateway
    try:
        source_arn = f"arn:aws:execute-api:{region}:{account_id}:{api_id}/*/*" if account_id else f"arn:aws:execute-api:{region}::{api_id}/*/*"
        lambda_client.add_permission(
            FunctionName=function_arn,
            StatementId="apigateway-demo-invoke",
            Action="lambda:InvokeFunction",
            Principal="apigateway.amazonaws.com",
            SourceArn=source_arn,
        )
        print("[+] Added Lambda invoke permission for API Gateway.")
    except lambda_client.exceptions.ResourceConflictException:
        pass

    # Create Deployment to stage 'prod'
    print("[+] Deploying API to 'prod' stage...")
    apigw_client.create_deployment(
        restApiId=api_id,
        stageName="prod",
        stageDescription="Production stage monitored by Cost Guardrail",
    )

    # Configure baseline throttle (1000 rps, 2000 burst)
    apigw_client.update_stage(
        restApiId=api_id,
        stageName="prod",
        patchOperations=[
            {"op": "replace", "path": "/*/*/throttling/rateLimit", "value": "1000"},
            {"op": "replace", "path": "/*/*/throttling/burstLimit", "value": "2000"},
        ],
    )

    invoke_url = f"https://{api_id}.execute-api.{region}.amazonaws.com/prod"
    return api_id, invoke_url


def main():
    region = (
        os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "ap-south-1"
    )
    print(f"Setting up Demo API Gateway + Backing Lambda in region: {region}")

    session = boto3.Session(region_name=region)
    iam_client = session.client("iam")
    lambda_client = session.client("lambda")
    apigw_client = session.client("apigateway")
    sts_client = session.client("sts")

    try:
        account_id = sts_client.get_caller_identity()["Account"]
        function_arn = ensure_demo_lambda(
            lambda_client, iam_client, "guardrail-demo-target"
        )
        api_id, invoke_url = ensure_demo_api_gateway(
            apigw_client, lambda_client, function_arn, region, account_id
        )
        print("\n" + "=" * 60)
        print(f"[SUCCESS] Demo API Gateway + Lambda is ready!")
        print(f"  API Gateway ID : {api_id}")
        print(f"  Stage          : prod")
        print(f"  Invoke URL     : {invoke_url}")
        print("=" * 60)
    except ClientError as e:
        print(f"\n[ERROR] AWS API call failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
