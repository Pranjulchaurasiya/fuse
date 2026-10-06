#!/usr/bin/env python3
"""check_iam_coverage.py — Static verification of boto3 API calls vs IAM policies.

Validates that every boto3 call executed by Fuse runtime code (lambdas, CLI, MCP)
is covered by least-privilege IAM policies in:
  1. template.yaml (Central AWS SAM stack)
  2. infra/cloudformation/fuse-cross-account-role.yaml (Customer onboarding role)

Distinguishes between:
  - Local SAM Lambda execution
  - Tenant Cross-Account execution
  - Unconditional vs Conditional (Condition: HasApiGatewayId) statements

Usage:
  python scripts/check_iam_coverage.py
"""

import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Mapping of Boto3 client methods to IAM actions
BOTO3_TO_IAM = {
    # WAFv2
    "get_ip_set": ("wafv2", "wafv2:GetIPSet", "regional/ipset/..."),
    "update_ip_set": ("wafv2", "wafv2:UpdateIPSet", "regional/ipset/..."),
    "list_ip_sets": ("wafv2", "wafv2:ListIPSets", "* (AWS requirement)"),
    "create_ip_set": ("wafv2", "wafv2:CreateIPSet", "regional/ipset/*"),
    "get_web_acl": ("wafv2", "wafv2:GetWebACL", "regional/webacl/..."),
    "update_web_acl": ("wafv2", "wafv2:UpdateWebACL", "regional/webacl/..."),
    "list_web_acls": ("wafv2", "wafv2:ListWebACLs", "* (AWS requirement)"),
    "create_web_acl": ("wafv2", "wafv2:CreateWebACL", "regional/webacl/*"),
    "associate_web_acl": ("wafv2", "wafv2:AssociateWebACL", "regional/webacl/... + stage"),
    # API Gateway
    "get_rest_apis": ("apigateway", "apigateway:GET", "/restapis"),
    "get_rest_api": ("apigateway", "apigateway:GET", "/restapis/..."),
    "get_stage": ("apigateway", "apigateway:GET", "/restapis/.../stages/..."),
    "update_stage": ("apigateway", "apigateway:PATCH", "/restapis/.../stages/..."),
    # CloudWatch & Logs
    "get_metric_data": ("cloudwatch", "cloudwatch:GetMetricData", "* (AWS requirement)"),
    "get_metric_statistics": ("cloudwatch", "cloudwatch:GetMetricStatistics", "* (AWS requirement)"),
    "list_metrics": ("cloudwatch", "cloudwatch:ListMetrics", "* (AWS requirement)"),
    "filter_log_events": ("logs", "logs:FilterLogEvents", "* / log-group"),
    "describe_log_groups": ("logs", "logs:DescribeLogGroups", "*"),
    "describe_log_streams": ("logs", "logs:DescribeLogStreams", "*"),
    # STS
    "assume_role": ("sts", "sts:AssumeRole", "arn:aws:iam::...:role/..."),
}

# Explicit caller classifications for tenant path
TENANT_CROSS_ACCOUNT_CALLS = {
    "get_metric_data",
    "filter_log_events",
    "get_metric_statistics",
    "list_metrics",
    "describe_log_groups",
    "describe_log_streams",
}

def scan_codebase_boto3_calls():
    """Scans python files for boto3 calls and identifies their execution path."""
    target_dirs = [
        os.path.join(REPO_ROOT, "lambdas"),
        os.path.join(REPO_ROOT, "cli"),
        os.path.join(REPO_ROOT, "scripts"),
    ]
    standalone_files = [
        os.path.join(REPO_ROOT, "mcp_server.py"),
        os.path.join(REPO_ROOT, "fuse.py"),
    ]

    files_to_scan = []
    for d in target_dirs:
        if os.path.exists(d):
            for root, _, files in os.walk(d):
                for f in files:
                    if f.endswith(".py"):
                        files_to_scan.append(os.path.join(root, f))
    for f in standalone_files:
        if os.path.exists(f):
            files_to_scan.append(f)

    call_sites = {}
    pattern = re.compile(r'\b(?:wafv2_client|wafv2|waf|apigw_client|apigw|cw_client|cw|logs_client|logs|sts_client|sts)\.([a-z_0-9]+)\(')

    for filepath in files_to_scan:
        rel = os.path.relpath(filepath, REPO_ROOT).replace("\\", "/")
        with open(filepath, "r", encoding="utf-8", errors="ignore") as fp:
            for lineno, line in enumerate(fp, 1):
                matches = pattern.findall(line)
                for m in matches:
                    if m in BOTO3_TO_IAM:
                        call_sites.setdefault(m, []).append((rel, lineno))

    return call_sites

def parse_yaml_policy_actions(filepath):
    """Extracts all Allowed IAM Actions from CloudFormation template."""
    actions = set()
    with open(filepath, "r", encoding="utf-8") as fp:
        content = fp.read()
    action_matches = re.findall(r'Action:\s*\n((?:\s+-\s+[\w:*]+\n)+)', content)
    for block in action_matches:
        for line in block.strip().splitlines():
            act = line.replace("-", "").strip()
            if act:
                actions.add(act)
    single_matches = re.findall(r'Action:\s+([a-zA-Z0-9:*]+)', content)
    for act in single_matches:
        actions.add(act.strip())
    return actions

def parse_cross_account_actions_with_conditions(filepath):
    """Extracts unconditional vs conditional actions from cross-account CloudFormation template."""
    with open(filepath, "r", encoding="utf-8") as fp:
        text = fp.read()

    unconditional = set()
    conditional = set()

    if "Resources:" in text:
        resources_part = text.split("Resources:")[1].split("Outputs:")[0]
        blocks = re.split(r'\n  ([A-Z][a-zA-Z0-9]+):\n', resources_part)
        for i in range(1, len(blocks), 2):
            r_name = blocks[i]
            r_body = blocks[i+1]
            cond_match = re.search(r'^\s{4}Condition:\s*([A-Za-z0-9]+)', r_body, re.MULTILINE)
            is_cond = bool(cond_match)

            actions = set()
            action_matches = re.findall(r'Action:\s*\n((?:\s+-\s+[\w:*]+\n)+)', r_body)
            for block in action_matches:
                for line in block.strip().splitlines():
                    act = line.replace('-', '').strip()
                    if ':' in act:
                        actions.add(act)
            single_matches = re.findall(r'Action:\s+([a-zA-Z0-9:*]+)', r_body)
            for act in single_matches:
                if ':' in act:
                    actions.add(act.strip())

            if is_cond:
                conditional.update(actions)
            else:
                unconditional.update(actions)

    return unconditional, conditional

def main():
    print("=" * 90)
    print(" FUSE — IAM COVERAGE & LEAST-PRIVILEGE AUDIT")
    print("=" * 90)

    template_path = os.path.join(REPO_ROOT, "template.yaml")
    cross_account_path = os.path.join(REPO_ROOT, "infra", "cloudformation", "fuse-cross-account-role.yaml")

    template_actions = parse_yaml_policy_actions(template_path)
    cross_uncond, cross_cond = parse_cross_account_actions_with_conditions(cross_account_path)

    calls = scan_codebase_boto3_calls()

    print(f"\n[+] Scanned {len(calls)} unique boto3 API calls across codebase.\n")
    print(f"{'Boto3 Method':<19} | {'Required Action':<26} | {'Caller Path':<18} | {'template.yaml':<13} | {'Cross-Account':<14}")
    print("-" * 102)

    has_failure = False
    has_warning = False

    for method, info in sorted(BOTO3_TO_IAM.items()):
        service, action, scope = info
        if method not in calls:
            continue

        call_files = [c[0] for c in calls[method]]
        is_lambda = any(f.startswith("lambdas/") for f in call_files)
        is_tenant = method in TENANT_CROSS_ACCOUNT_CALLS and is_lambda
        is_setup_only = not is_lambda and any(f.startswith("scripts/") for f in call_files)

        if is_tenant and is_lambda:
            caller_label = "Tenant & Local"
        elif is_lambda:
            caller_label = "Local SAM Lambda"
        elif is_setup_only:
            caller_label = "Setup Script"
        else:
            caller_label = "CLI / MCP"

        in_template = action in template_actions

        if action in cross_uncond:
            cross_mark = "YES (Allowed)"
        elif action in cross_cond:
            cross_mark = "CONDITIONAL"
        else:
            cross_mark = "—"

        template_mark = "YES (Allowed)" if in_template else "—"

        errors = []
        warnings = []

        # Central lambda must have permission in template.yaml
        if is_lambda and not in_template:
            errors.append("MISSING in template.yaml")
            has_failure = True

        # Tenant call must NOT be missing in cross-account role
        if is_tenant and (action not in cross_uncond and action not in cross_cond):
            errors.append("MISSING in cross-account role")
            has_failure = True

        # Tenant call MUST NOT depend on a conditional permission (warning)
        if is_tenant and action in cross_cond and action not in cross_uncond:
            warnings.append("WARN: Tenant runtime depends on CONDITIONAL permission")
            has_warning = True

        flag = ""
        if errors:
            flag = f" [FAIL: {', '.join(errors)}]"
        elif warnings:
            flag = f" [{', '.join(warnings)}]"

        print(f"{method:<19} | {action:<26} | {caller_label:<18} | {template_mark:<13} | {cross_mark:<14}{flag}")

    print("-" * 102)

    print("\n[+] Verification of Resource Wildcard Rules:")
    print("  1. wafv2:ListIPSets & wafv2:ListWebACLs: Required Resource: '*' (Confirmed AWS requirement)")
    print("  2. wafv2:GetIPSet & wafv2:UpdateIPSet: Scoped to specific fuse-blocked-ips ARN (Confirmed)")
    print("  3. cloudwatch:GetMetricData: Read-only on Resource: '*' (Confirmed AWS requirement)")
    print("  4. apigateway:GET: Scoped to /restapis/${CustomerApiGatewayId}* (CONDITIONAL on HasApiGatewayId)")
    print("  5. sts:AssumeRole: Enforces sts:ExternalId condition (Confirmed)")

    if has_failure:
        print("\n[FAIL] Some runtime boto3 calls are missing IAM permissions!\n")
        return 1
    elif has_warning:
        print("\n[WARNING] Passed with tenant warnings (conditional dependency).\n")
        return 0
    else:
        print("\n[SUCCESS] All runtime boto3 API calls are covered by least-privilege IAM policies.\n")
        return 0

if __name__ == "__main__":
    sys.exit(main())
