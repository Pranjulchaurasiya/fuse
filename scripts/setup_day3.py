#!/usr/bin/env python3
"""setup_day3.py — Deploys Day 3 Remediator, Control API, and approval gate.

This script creates/updates:
1. IAM Role `guardrail-remediator-role` (with API Gateway throttle & DynamoDB permissions)
2. IAM Role `guardrail-control-role` (with ApprovalQueue, Incidents, and invoke permissions)
3. Lambda `guardrail-remediator` from lambdas/remediator/handler.py
4. Lambda `guardrail-approve-action` from lambdas/approve_action/handler.py
5. Lambda `guardrail-get-incidents` from lambdas/get_incidents/handler.py
6. Updates Lambda `guardrail-reasoner` with Day 3 code & role permissions
7. REST API Gateway `guardrail-control-api` fronting:
   - GET /incidents -> guardrail-get-incidents
   - POST /incidents/{incident_id}/approve -> guardrail-approve-action
   - Deploys to stage 'prod'
"""

import io
import json
import os
import sys
import time
import zipfile
import boto3
from botocore.exceptions import ClientError

REGION_NAME = "ap-south-1"
REMEDIATOR_ROLE = "guardrail-remediator-role"
CONTROL_ROLE = "guardrail-control-role"
REASONER_ROLE = "guardrail-reasoner-role"

REMEDIATOR_FN = "guardrail-remediator"
APPROVE_FN = "guardrail-approve-action"
INCIDENTS_FN = "guardrail-get-incidents"
REASONER_FN = "guardrail-reasoner"
CONTROL_API_NAME = "guardrail-control-api"
DEMO_API_NAME = "guardrail-demo-api"


def make_zip(handler_rel_path: str) -> bytes:
    base = os.path.dirname(__file__)
    path = os.path.join(base, "..", handler_rel_path)
    with open(path, "r", encoding="utf-8") as f:
        code = f.read()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("handler.py", code)
    buf.seek(0)
    return buf.read()


def ensure_role(iam_client, role_name: str, policy_file_rel: str) -> str:
    assume_policy = {
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}],
    }

    try:
        resp = iam_client.get_role(RoleName=role_name)
        role_arn = resp["Role"]["Arn"]
        print(f"[-] IAM Role '{role_name}' exists: {role_arn}")
    except iam_client.exceptions.NoSuchEntityException:
        print(f"[+] Creating IAM Role '{role_name}'...")
        resp = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(assume_policy),
            Description=f"Role for {role_name}",
        )
        role_arn = resp["Role"]["Arn"]
        print(f"[+] Created role: {role_arn}")
        time.sleep(10)

    # Attach basic execution
    iam_client.attach_role_policy(
        RoleName=role_name,
        PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    )

    # Put inline policy
    base = os.path.dirname(__file__)
    pol_path = os.path.join(base, "..", policy_file_rel)
    with open(pol_path, "r", encoding="utf-8") as f:
        doc = f.read()

    iam_client.put_role_policy(
        RoleName=role_name,
        PolicyName=f"{role_name}-policy",
        PolicyDocument=doc,
    )
    print(f"[+] Attached inline policy to '{role_name}'.")
    return role_arn


def ensure_lambda(lambda_client, fn_name: str, role_arn: str, zip_bytes: bytes, env_vars: dict, timeout=15, mem=128) -> str:
    env_payload = {"Variables": env_vars}
    try:
        resp = lambda_client.get_function(FunctionName=fn_name)
        arn = resp["Configuration"]["FunctionArn"]
        print(f"[-] Lambda '{fn_name}' exists. Updating code and config...")
        lambda_client.update_function_code(FunctionName=fn_name, ZipFile=zip_bytes)
        waiter = lambda_client.get_waiter("function_updated")
        waiter.wait(FunctionName=fn_name)

        lambda_client.update_function_configuration(
            FunctionName=fn_name,
            Role=role_arn,
            Handler="handler.lambda_handler",
            Runtime="python3.12",
            Timeout=timeout,
            MemorySize=mem,
            Environment=env_payload,
        )
        waiter.wait(FunctionName=fn_name)
        print(f"[+] Lambda '{fn_name}' updated.")
        return arn
    except lambda_client.exceptions.ResourceNotFoundException:
        print(f"[+] Creating Lambda '{fn_name}'...")
        for attempt in range(5):
            try:
                resp = lambda_client.create_function(
                    FunctionName=fn_name,
                    Runtime="python3.12",
                    Role=role_arn,
                    Handler="handler.lambda_handler",
                    Code={"ZipFile": zip_bytes},
                    Timeout=timeout,
                    MemorySize=mem,
                    Environment=env_payload,
                )
                arn = resp["FunctionArn"]
                print(f"[+] Lambda '{fn_name}' created: {arn}")
                waiter = lambda_client.get_waiter("function_active_v2")
                waiter.wait(FunctionName=fn_name)
                return arn
            except ClientError as err:
                if "InvalidParameterValueException" in str(err) and attempt < 4:
                    print(f"[*] Role replication waiting 5s (attempt {attempt+1}/5)...")
                    time.sleep(5)
                else:
                    raise


def ensure_cors_options(apigw_client, api_id: str, resource_id: str, allowed_methods: str):
    """Adds an OPTIONS method with mock integration returning standard CORS headers."""
    try:
        apigw_client.put_method(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod="OPTIONS",
            authorizationType="NONE",
        )
    except ClientError:
        pass

    try:
        apigw_client.put_integration(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod="OPTIONS",
            type="MOCK",
            requestTemplates={"application/json": '{"statusCode": 200}'},
        )
    except ClientError:
        pass

    try:
        apigw_client.put_method_response(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod="OPTIONS",
            statusCode="200",
            responseParameters={
                "method.response.header.Access-Control-Allow-Headers": True,
                "method.response.header.Access-Control-Allow-Methods": True,
                "method.response.header.Access-Control-Allow-Origin": True,
            },
        )
    except ClientError:
        pass

    try:
        apigw_client.put_integration_response(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod="OPTIONS",
            statusCode="200",
            responseParameters={
                "method.response.header.Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key'",
                "method.response.header.Access-Control-Allow-Methods": f"'{allowed_methods}'",
                "method.response.header.Access-Control-Allow-Origin": "'*'",
            },
        )
    except ClientError:
        pass


def setup_control_api(apigw_client, lambda_client, account_id: str, incidents_arn: str, approve_arn: str) -> str:
    """Creates/updates the REST API Gateway for control plane."""
    # 1. Lookup or create REST API
    apis = apigw_client.get_rest_apis().get("items", [])
    api_id = None
    for a in apis:
        if a["name"] == CONTROL_API_NAME:
            api_id = a["id"]
            print(f"[-] REST API '{CONTROL_API_NAME}' exists: {api_id}")
            break

    if not api_id:
        print(f"[+] Creating REST API '{CONTROL_API_NAME}'...")
        r = apigw_client.create_rest_api(
            name=CONTROL_API_NAME,
            description="Control plane for AWS Cost Guardrail (incidents and approvals)",
            endpointConfiguration={"types": ["REGIONAL"]},
        )
        api_id = r["id"]
        print(f"[+] Created REST API: {api_id}")

    # 2. Get Root Resource ID
    resources = apigw_client.get_resources(restApiId=api_id).get("items", [])
    root_id = [item["id"] for item in resources if item["path"] == "/"][0]

    # Helper to get or create resource
    def get_or_create(path_part, parent_id):
        nonlocal resources
        for item in resources:
            if item.get("parentId") == parent_id and item.get("pathPart") == path_part:
                return item["id"]
        r = apigw_client.create_resource(restApiId=api_id, parentId=parent_id, pathPart=path_part)
        resources = apigw_client.get_resources(restApiId=api_id).get("items", [])
        return r["id"]

    # 3. Create /incidents resource
    incidents_res_id = get_or_create("incidents", root_id)

    # PUT GET on /incidents -> guardrail-get-incidents
    apigw_client.put_method(
        restApiId=api_id,
        resourceId=incidents_res_id,
        httpMethod="GET",
        authorizationType="NONE",
    )
    apigw_client.put_integration(
        restApiId=api_id,
        resourceId=incidents_res_id,
        httpMethod="GET",
        type="AWS_PROXY",
        integrationHttpMethod="POST",
        uri=f"arn:aws:apigateway:{REGION_NAME}:lambda:path/2015-03-31/functions/{incidents_arn}/invocations",
    )
    ensure_cors_options(apigw_client, api_id, incidents_res_id, "GET,OPTIONS")

    # 4. Create /incidents/{incident_id} resource
    item_res_id = get_or_create("{incident_id}", incidents_res_id)

    # 5. Create /incidents/{incident_id}/approve resource
    approve_res_id = get_or_create("approve", item_res_id)

    # PUT POST on /incidents/{incident_id}/approve -> guardrail-approve-action
    apigw_client.put_method(
        restApiId=api_id,
        resourceId=approve_res_id,
        httpMethod="POST",
        authorizationType="NONE",
    )
    apigw_client.put_integration(
        restApiId=api_id,
        resourceId=approve_res_id,
        httpMethod="POST",
        type="AWS_PROXY",
        integrationHttpMethod="POST",
        uri=f"arn:aws:apigateway:{REGION_NAME}:lambda:path/2015-03-31/functions/{approve_arn}/invocations",
    )
    ensure_cors_options(apigw_client, api_id, approve_res_id, "POST,OPTIONS")

    # 6. Add Lambda invoke permissions
    def add_perm(fn_name, sid):
        try:
            lambda_client.add_permission(
                FunctionName=fn_name,
                StatementId=sid,
                Action="lambda:InvokeFunction",
                Principal="apigateway.amazonaws.com",
                SourceArn=f"arn:aws:execute-api:{REGION_NAME}:{account_id}:{api_id}/*/*",
            )
        except ClientError as e:
            if "ResourceConflictException" not in str(e):
                raise

    add_perm(INCIDENTS_FN, "apigw-control-get-incidents")
    add_perm(APPROVE_FN, "apigw-control-approve-action")

    # 7. Create Deployment on stage 'prod'
    print("[+] Deploying REST API to stage 'prod'...")
    apigw_client.create_deployment(restApiId=api_id, stageName="prod")

    invoke_url = f"https://{api_id}.execute-api.{REGION_NAME}.amazonaws.com/prod"
    print(f"[+] Control API deployed: {invoke_url}")
    return invoke_url


def main():
    print("=" * 70)
    print(" AWS Cost Guardrail — Setup Day 3 Remediation & Approval Gate")
    print(f" Region: {REGION_NAME}")
    print("=" * 70)

    sts_client = boto3.client("sts", region_name=REGION_NAME)
    account_id = sts_client.get_caller_identity()["Account"]
    iam_client = boto3.client("iam", region_name=REGION_NAME)
    lambda_client = boto3.client("lambda", region_name=REGION_NAME)
    apigw_client = boto3.client("apigateway", region_name=REGION_NAME)

    # 1. Roles
    remediator_role_arn = ensure_role(iam_client, REMEDIATOR_ROLE, "infra/iam-policies/remediator-role.json")
    control_role_arn = ensure_role(iam_client, CONTROL_ROLE, "infra/iam-policies/control-api-role.json")

    # Update reasoner role to allow writing to ApprovalQueue and invoking remediator
    print("[+] Updating Reasoner role with ApprovalQueue and Remediator invoke policy...")
    reasoner_extra_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem"],
                "Resource": f"arn:aws:dynamodb:{REGION_NAME}:{account_id}:table/ApprovalQueue",
            },
            {
                "Effect": "Allow",
                "Action": ["lambda:InvokeFunction"],
                "Resource": f"arn:aws:lambda:{REGION_NAME}:{account_id}:function:{REMEDIATOR_FN}",
            },
        ],
    }
    iam_client.put_role_policy(
        RoleName=REASONER_ROLE,
        PolicyName="guardrail-reasoner-day3-additions",
        PolicyDocument=json.dumps(reasoner_extra_policy),
    )

    # 2. Deploy Remediator
    remediator_zip = make_zip("lambdas/remediator/handler.py")
    remediator_arn = ensure_lambda(
        lambda_client,
        REMEDIATOR_FN,
        remediator_role_arn,
        remediator_zip,
        env_vars={
            "TARGET_API_ID": "poim5xmgs2",
            "TARGET_API_NAME": "guardrail-demo-api",
            "INCIDENTS_TABLE": "Incidents",
        },
        timeout=15,
        mem=128,
    )

    # 3. Deploy Approve Action
    approve_zip = make_zip("lambdas/approve_action/handler.py")
    approve_arn = ensure_lambda(
        lambda_client,
        APPROVE_FN,
        control_role_arn,
        approve_zip,
        env_vars={
            "APPROVAL_QUEUE_TABLE": "ApprovalQueue",
            "INCIDENTS_TABLE": "Incidents",
            "REMEDIATOR_FUNCTION_NAME": REMEDIATOR_FN,
        },
        timeout=15,
        mem=128,
    )

    # 4. Deploy Get Incidents
    incidents_zip = make_zip("lambdas/get_incidents/handler.py")
    incidents_arn = ensure_lambda(
        lambda_client,
        INCIDENTS_FN,
        control_role_arn,
        incidents_zip,
        env_vars={"INCIDENTS_TABLE": "Incidents"},
        timeout=15,
        mem=128,
    )

    # 5. Redeploy Reasoner Lambda with Day 3 code
    reasoner_zip = make_zip("lambdas/reasoner/handler.py")
    ensure_lambda(
        lambda_client,
        REASONER_FN,
        f"arn:aws:iam::{account_id}:role/{REASONER_ROLE}",
        reasoner_zip,
        env_vars={
            "BEDROCK_REGION": REGION_NAME,
            "BEDROCK_MODEL_ID": "apac.amazon.nova-micro-v1:0",
            "INCIDENTS_TABLE": "Incidents",
            "DEPLOYMENTS_TABLE": "Deployments",
            "APPROVAL_QUEUE_TABLE": "ApprovalQueue",
            "REMEDIATOR_FUNCTION_NAME": REMEDIATOR_FN,
        },
        timeout=25,
        mem=256,
    )

    # 6. Setup Control API Gateway
    control_api_url = setup_control_api(apigw_client, lambda_client, account_id, incidents_arn, approve_arn)

    print("\n" + "=" * 70)
    print(" [OK] Day 3 Infrastructure Deployed Successfully!")
    print(f" Control API Base: {control_api_url}")
    print(f" - GET  {control_api_url}/incidents")
    print(f" - POST {control_api_url}/incidents/{{incident_id}}/approve")
    print("=" * 70)


if __name__ == "__main__":
    main()
