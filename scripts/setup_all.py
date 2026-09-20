#!/usr/bin/env python3
"""setup_all.py — Master orchestration script for AWS Cost Guardrail (Fuse).

Executes all infrastructure setup scripts in strict dependency order:
1. setup_dynamodb.py   -> Creates Deployments, Incidents, ApprovalQueue tables
2. setup_demo_api.py   -> Deploys demo target API Gateway & backing Lambda
3. setup_poller.py     -> Deploys Poller Lambda & EventBridge 1-min schedule
4. setup_reasoner.py   -> Deploys Reasoner Lambda with Bedrock Converse API
5. setup_day3.py       -> Deploys Remediator, Control API, & Approval Gate Lambdas
6. deploy_dashboard.py -> Deploys operator console static assets to S3

Each step must succeed before the next step runs.
If any step fails, execution halts immediately with an error report.
"""

import os
import sys
import subprocess
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)

STEPS = [
    {
        "step_num": 1,
        "name": "DynamoDB State Tables",
        "script": "setup_dynamodb.py",
        "desc": "Create Deployments, Incidents, and ApprovalQueue on-demand tables",
    },
    {
        "step_num": 2,
        "name": "Protected Demo API & Target Lambda",
        "script": "setup_demo_api.py",
        "desc": "Deploy guardrail-demo-api REST API Gateway and guardrail-demo-target Lambda",
    },
    {
        "step_num": 3,
        "name": "Metrics Poller & EventBridge Cadence",
        "script": "setup_poller.py",
        "desc": "Deploy guardrail-poller Lambda and 1-minute EventBridge schedule rule",
    },
    {
        "step_num": 4,
        "name": "Bedrock Sentinel Reasoner",
        "script": "setup_reasoner.py",
        "desc": "Deploy guardrail-reasoner Lambda with Bedrock Converse structured tool calling",
    },
    {
        "step_num": 5,
        "name": "Circuit Remediator & Control Plane API",
        "script": "setup_day3.py",
        "desc": "Deploy guardrail-remediator, approve-action, get-incidents, and guardrail-control-api",
    },
    {
        "step_num": 6,
        "name": "Operator Dashboard Console",
        "script": "deploy_dashboard.py",
        "desc": "Provision S3 static hosting bucket and upload console assets (index.html, styles.css, app.js)",
    },
]


def print_banner(text: str, char: str = "="):
    line = char * 74
    print(f"\n{line}")
    print(f" {text}")
    print(f"{line}\n")


def run_step(step_info: dict) -> bool:
    step_num = step_info["step_num"]
    name = step_info["name"]
    script_name = step_info["script"]
    desc = step_info["desc"]
    script_path = os.path.join(SCRIPT_DIR, script_name)

    print(f"[*] ----------------------------------------------------------------------")
    print(f"[*] STEP {step_num}/6: {name}")
    print(f"[*] Script:      scripts/{script_name}")
    print(f"[*] Description: {desc}")
    print(f"[*] ----------------------------------------------------------------------")

    if not os.path.exists(script_path):
        print(f"\n[!] ERROR: Script file '{script_path}' does not exist.")
        return False

    start_time = time.time()
    try:
        # Run child script directly inheriting stdout/stderr and environment
        result = subprocess.run(
            [sys.executable, "-u", script_path],
            cwd=REPO_ROOT,
            env=os.environ,
            check=False,
        )
    except Exception as e:
        print(f"\n[!] ERROR: Failed to execute '{script_name}': {e}")
        return False

    elapsed = time.time() - start_time
    if result.returncode != 0:
        print(f"\n[FAILED] Step {step_num} ({script_name}) failed with exit code {result.returncode} ({elapsed:.1f}s).")
        return False

    print(f"\n[SUCCESS] Step {step_num}/6 ({name}) completed successfully ({elapsed:.1f}s).")
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Master orchestration script for AWS Cost Guardrail")
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "ap-south-1"), help="Target AWS region")
    args = parser.parse_args()

    region = args.region
    os.environ["AWS_REGION"] = region
    os.environ["AWS_DEFAULT_REGION"] = region

    print_banner("FUSE — FULL INFRASTRUCTURE SETUP ORCHESTRATOR", "=")
    print("This script will provision the complete AWS Cost Guardrail system in sequence.")
    print(f"Repository Root:   {REPO_ROOT}")
    print(f"Target AWS Region: {region}")
    print(f"Python Runtime:    {sys.executable}\n")

    total_start = time.time()

    for step in STEPS:
        success = run_step(step)
        if not success:
            print_banner("SETUP HALTED: DEPLOYMENT FAILED", "!")
            print(f"Failed on Step {step['step_num']}: {step['name']} ({step['script']})")
            print("Orchestration stopped immediately. No subsequent steps were executed.")
            print(f"Resolve the error above and rerun 'python scripts/setup_all.py --region {region}'.\n")
            sys.exit(1)

    total_elapsed = time.time() - total_start
    print_banner("ALL 6 STEPS COMPLETED SUCCESSFULLY", "=")
    print(f"Total Provisioning Time: {total_elapsed:.1f} seconds")
    print("\nVerified Components:")
    print("  [OK] DynamoDB State Tables: Deployments, Incidents, ApprovalQueue")
    print("  [OK] Target Workload:       guardrail-demo-api (stage: prod, dev)")
    print("  [OK] Metrics Telemetry:     guardrail-poller (1-min EventBridge cadence)")
    print("  [OK] Anomaly Reasoning:     guardrail-reasoner (Bedrock Converse API)")
    print("  [OK] Control Plane & Gate:  guardrail-control-api (/incidents, /approve)")
    print("  [OK] Operator Console:      S3 Static Website / Amplify Hosting")
    print("\nNext step: Run test traffic or reset test clutter with:")
    print("  python scripts/clear_test_data.py\n")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    main()

