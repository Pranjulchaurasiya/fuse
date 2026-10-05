"""Setup WAF resources for Fuse IP-based blocking.

Creates:
- WAF IP Set (fuse-blocked-ips) for storing blocked IPs
- WAF Web ACL (fuse-guardrail-acl) with a block rule referencing the IP Set
- Associates the Web ACL with the target API Gateway stage
- Updates Remediator Lambda env vars and IAM policy

Usage:
    python scripts/setup_waf.py

Prerequisites:
    - AWS credentials configured
    - guardrail-remediator Lambda exists
    - guardrail-demo-api API Gateway exists
"""

import boto3
import json
import sys
import time

REGION = "ap-south-1"
ACCOUNT_ID = "515903395012"
IP_SET_NAME = "fuse-blocked-ips"
WEB_ACL_NAME = "fuse-guardrail-acl"
TARGET_API_NAME = "guardrail-demo-api"
TARGET_STAGE = "prod"
REMEDIATOR_FUNCTION_NAME = "guardrail-remediator"
REMEDIATOR_ROLE_NAME = "guardrail-remediator-role"

wafv2 = boto3.client("wafv2", region_name=REGION)
apigw = boto3.client("apigateway", region_name=REGION)
lambda_client = boto3.client("lambda", region_name=REGION)
iam = boto3.client("iam", region_name=REGION)


def find_api_id(api_name):
    apis = apigw.get_rest_apis().get("items", [])
    for api in apis:
        if api.get("name") == api_name:
            return api["id"]
    return None


def create_ip_set():
    """Create or find existing WAF IP Set."""
    # Check if already exists
    try:
        existing = wafv2.list_ip_sets(Scope="REGIONAL", Limit=100)
        for ip_set in existing.get("IPSets", []):
            if ip_set["Name"] == IP_SET_NAME:
                print(f"  IP Set '{IP_SET_NAME}' already exists: {ip_set['Id']}")
                return ip_set["Id"], ip_set["ARN"]
    except Exception:
        pass

    response = wafv2.create_ip_set(
        Name=IP_SET_NAME,
        Scope="REGIONAL",
        IPAddressVersion="IPV4",
        Addresses=[],  # starts empty
        Description="Fuse Guardrail: IPs blocked by automated runaway detection",
    )
    ip_set_id = response["Summary"]["Id"]
    ip_set_arn = response["Summary"]["ARN"]
    print(f"  Created IP Set '{IP_SET_NAME}': {ip_set_id}")
    return ip_set_id, ip_set_arn


def create_web_acl(ip_set_arn):
    """Create or update WAF Web ACL with IP Set blocking + Emergency Burst Cap."""
    rules = [
        {
            "Name": "fuse-block-runaway-ips",
            "Priority": 0,
            "Statement": {
                "IPSetReferenceStatement": {
                    "ARN": ip_set_arn,
                }
            },
            "Action": {"Block": {}},
            "VisibilityConfig": {
                "SampledRequestsEnabled": True,
                "CloudWatchMetricsEnabled": True,
                "MetricName": "fuse-blocked-ips",
            },
        },
        {
            "Name": "fuse-emergency-burst-cap",
            "Priority": 1,
            "Statement": {
                "RateBasedStatement": {
                    "Limit": 500,  # Catch massive sub-minute floods instantly at edge
                    "AggregateKeyType": "IP",
                    "EvaluationWindowSec": 300,  # 5-minute sliding window
                }
            },
            "Action": {"Block": {}},
            "VisibilityConfig": {
                "SampledRequestsEnabled": True,
                "CloudWatchMetricsEnabled": True,
                "MetricName": "fuse-emergency-burst-cap",
            },
        },
    ]

    # Check if already exists
    try:
        existing = wafv2.list_web_acls(Scope="REGIONAL", Limit=100)
        for acl in existing.get("WebACLs", []):
            if acl["Name"] == WEB_ACL_NAME:
                print(f"  Web ACL '{WEB_ACL_NAME}' exists. Updating rules...")
                detail = wafv2.get_web_acl(Name=WEB_ACL_NAME, Scope="REGIONAL", Id=acl["Id"])
                wafv2.update_web_acl(
                    Name=WEB_ACL_NAME,
                    Scope="REGIONAL",
                    Id=acl["Id"],
                    DefaultAction={"Allow": {}},
                    Description="Fuse Guardrail: Multi-layered IP set + emergency burst cap",
                    Rules=rules,
                    VisibilityConfig={
                        "SampledRequestsEnabled": True,
                        "CloudWatchMetricsEnabled": True,
                        "MetricName": "fuse-guardrail-acl",
                    },
                    LockToken=detail["LockToken"],
                )
                print(f"  Updated Web ACL '{WEB_ACL_NAME}' with Layer-1 emergency burst cap.")
                return acl["Id"], acl["ARN"]
    except Exception as e:
        print(f"  Note during Web ACL check: {e}")

    response = wafv2.create_web_acl(
        Name=WEB_ACL_NAME,
        Scope="REGIONAL",
        DefaultAction={"Allow": {}},
        Description="Fuse Guardrail: Multi-layered IP set + emergency burst cap",
        Rules=rules,
        VisibilityConfig={
            "SampledRequestsEnabled": True,
            "CloudWatchMetricsEnabled": True,
            "MetricName": "fuse-guardrail-acl",
        },
    )
    acl_id = response["Summary"]["Id"]
    acl_arn = response["Summary"]["ARN"]
    print(f"  Created Web ACL '{WEB_ACL_NAME}': {acl_id}")
    return acl_id, acl_arn


def associate_web_acl(web_acl_arn, api_id, stage_name):
    """Associate WAF Web ACL with API Gateway stage."""
    resource_arn = f"arn:aws:apigateway:{REGION}::/restapis/{api_id}/stages/{stage_name}"
    
    try:
        wafv2.associate_web_acl(
            WebACLArn=web_acl_arn,
            ResourceArn=resource_arn,
        )
        print(f"  Associated Web ACL with API Gateway stage: {api_id}/{stage_name}")
    except wafv2.exceptions.WAFInvalidParameterException as e:
        if "already associated" in str(e).lower():
            print(f"  Web ACL already associated with {api_id}/{stage_name}")
        else:
            raise


def update_remediator_env(ip_set_id, ip_set_name, web_acl_id, web_acl_name):
    """Update Remediator Lambda environment variables."""
    try:
        config = lambda_client.get_function_configuration(FunctionName=REMEDIATOR_FUNCTION_NAME)
        env_vars = config.get("Environment", {}).get("Variables", {})
        
        env_vars["WAF_IP_SET_ID"] = ip_set_id
        env_vars["WAF_IP_SET_NAME"] = ip_set_name
        env_vars["WAF_WEB_ACL_ID"] = web_acl_id
        env_vars["WAF_WEB_ACL_NAME"] = web_acl_name
        
        lambda_client.update_function_configuration(
            FunctionName=REMEDIATOR_FUNCTION_NAME,
            Environment={"Variables": env_vars},
        )
        print(f"  Updated {REMEDIATOR_FUNCTION_NAME} env vars with WAF resource IDs")
    except Exception as e:
        print(f"  WARNING: Could not update Lambda env vars: {e}")
        print(f"  Manually set these env vars on {REMEDIATOR_FUNCTION_NAME}:")
        print(f"    WAF_IP_SET_ID={ip_set_id}")
        print(f"    WAF_IP_SET_NAME={ip_set_name}")
        print(f"    WAF_WEB_ACL_ID={web_acl_id}")
        print(f"    WAF_WEB_ACL_NAME={web_acl_name}")


def update_remediator_iam():
    """Add WAF permissions to the Remediator role."""
    waf_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "WAFIPSetManagement",
                "Effect": "Allow",
                "Action": [
                    "wafv2:GetIPSet",
                    "wafv2:UpdateIPSet",
                    "wafv2:ListIPSets",
                ],
                "Resource": f"arn:aws:wafv2:{REGION}:{ACCOUNT_ID}:regional/ipset/{IP_SET_NAME}/*",
            }
        ],
    }
    
    policy_name = "fuse-waf-ip-management"
    try:
        iam.put_role_policy(
            RoleName=REMEDIATOR_ROLE_NAME,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(waf_policy),
        )
        print(f"  Added WAF permissions to role {REMEDIATOR_ROLE_NAME}")
    except Exception as e:
        print(f"  WARNING: Could not update IAM role: {e}")
        print(f"  Manually add this inline policy '{policy_name}' to role '{REMEDIATOR_ROLE_NAME}':")
        print(json.dumps(waf_policy, indent=2))


def update_poller_iam():
    """Add Remediator invoke permission to the Poller role."""
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "RemediatorInvokeAccess",
                "Effect": "Allow",
                "Action": "lambda:InvokeFunction",
                "Resource": f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:{REMEDIATOR_FUNCTION_NAME}",
            },
            {
                "Sid": "IncidentsTableAccess",
                "Effect": "Allow",
                "Action": [
                    "dynamodb:Scan",
                    "dynamodb:UpdateItem",
                ],
                "Resource": f"arn:aws:dynamodb:{REGION}:{ACCOUNT_ID}:table/Incidents",
            }
        ],
    }
    
    try:
        iam.put_role_policy(
            RoleName="guardrail-poller-role",
            PolicyName="fuse-poller-remediation-access",
            PolicyDocument=json.dumps(policy),
        )
        print(f"  Added Remediator invoke + Incidents table permissions to guardrail-poller-role")
    except Exception as e:
        print(f"  WARNING: Could not update Poller IAM role: {e}")


def main():
    print("="*60)
    print("Fuse WAF Setup: IP-Based Surgical Blocking")
    print("="*60)
    
    # 1. Find API Gateway
    print("\n[1/6] Finding target API Gateway...")
    api_id = find_api_id(TARGET_API_NAME)
    if not api_id:
        print(f"  ERROR: Could not find API '{TARGET_API_NAME}'. Aborting.")
        sys.exit(1)
    print(f"  Found API: {api_id}")
    
    # 2. Create IP Set
    print("\n[2/6] Creating WAF IP Set...")
    ip_set_id, ip_set_arn = create_ip_set()
    
    # 3. Create Web ACL
    print("\n[3/6] Creating WAF Web ACL...")
    web_acl_id, web_acl_arn = create_web_acl(ip_set_arn)
    
    # 4. Associate with API Gateway
    print("\n[4/6] Associating Web ACL with API Gateway...")
    associate_web_acl(web_acl_arn, api_id, TARGET_STAGE)
    
    # 5. Update Remediator Lambda
    print("\n[5/6] Updating Remediator Lambda config...")
    update_remediator_env(ip_set_id, IP_SET_NAME, web_acl_id, WEB_ACL_NAME)
    update_remediator_iam()
    
    # 6. Update Poller IAM
    print("\n[6/6] Updating Poller IAM permissions...")
    update_poller_iam()
    
    print("\n" + "="*60)
    print("WAF Setup Complete!")
    print("="*60)
    print(f"\n  IP Set ID:    {ip_set_id}")
    print(f"  IP Set ARN:   {ip_set_arn}")
    print(f"  Web ACL ID:   {web_acl_id}")
    print(f"  Web ACL ARN:  {web_acl_arn}")
    print(f"  API Gateway:  {api_id}/{TARGET_STAGE}")
    print(f"\nNext steps:")
    print(f"  1. Deploy updated Remediator Lambda code")
    print(f"  2. Deploy updated Poller Lambda code")
    print(f"  3. Test with: python scripts/load_test_runaway.py")


if __name__ == "__main__":
    main()
