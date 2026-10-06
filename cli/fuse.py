#!/usr/bin/env python3
"""
Fuse CLI — Command Line Interface for Autonomous AWS Cost Guardrail & WAF Circuit Breaker.

Usage:
  fuse status                                 Show live guardrail status, WAF blocks, and API health
  fuse incidents [--limit N] [--json]         Inspect recent anomaly detection events and AI reasoning
  fuse block <ip> [--reason REASON]           Surgically block an offending caller IP at the AWS WAF edge
  fuse unblock <ip>                           Remove an IP from the WAF blocked set
  fuse heartbeat [--id ID] [--note NOTE]      Log deployment heartbeat to suppress false positive alarms
  fuse test [--scenario runaway|legit]        Run live traffic test against the target API Gateway
  fuse config                                 Show CLI configuration and endpoints
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
import uuid
from datetime import datetime, timezone

# Ensure UTF-8 output on all shells (including Windows PowerShell cp1252)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

# Default Production Configuration
DEFAULT_REGION = os.environ.get("AWS_REGION", "ap-south-1")
DEFAULT_CONTROL_API = os.environ.get(
    "FUSE_CONTROL_API",
    "https://agcki2mnvi.execute-api.ap-south-1.amazonaws.com/prod"
)
DEFAULT_TARGET_API = os.environ.get(
    "FUSE_TARGET_API",
    "https://poim5xmgs2.execute-api.ap-south-1.amazonaws.com/prod/items"
)
WAF_IP_SET_NAME = os.environ.get("WAF_IP_SET_NAME", "fuse-blocked-ips")
WAF_IP_SET_ID = os.environ.get("WAF_IP_SET_ID", "007b7281-00d8-4e83-9675-c3a2cae62158")
REMEDIATOR_LAMBDA = os.environ.get("REMEDIATOR_LAMBDA", "guardrail-remediator")
DEPLOYMENTS_TABLE = os.environ.get("DEPLOYMENTS_TABLE", "Deployments")

# ANSI Color Tokens
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    BLUE = "\033[38;5;39m"
    GREEN = "\033[38;5;42m"
    YELLOW = "\033[38;5;214m"
    RED = "\033[38;5;196m"
    CYAN = "\033[38;5;51m"
    SLATE = "\033[38;5;244m"
    ORANGE = "\033[38;5;208m"

# Header Banner
BANNER = f"""{C.BOLD}{C.BLUE}
  ███████╗██╗   ██╗███████╗███████╗
  ██╔════╝██║   ██║██╔════╝██╔════╝
  █████╗  ██║   ██║███████╗█████╗  
  ██╔══╝  ██║   ██║╚════██║██╔══╝  
  ██║     ╚██████╔╝███████║███████╗
  ╚═╝      ╚═════╝ ╚══════╝╚══════╝{C.RESET}
  {C.DIM}Autonomous Cloud Cost Guardrail & WAF Circuit Breaker{C.RESET}
"""

def print_header():
    print(BANNER)

def api_get(endpoint: str) -> dict:
    url = f"{DEFAULT_CONTROL_API.rstrip('/')}/{endpoint.lstrip('/')}"
    req = urllib.request.Request(url, headers={"User-Agent": "Fuse-CLI/1.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}

def api_post(endpoint: str, data: dict) -> dict:
    url = f"{DEFAULT_CONTROL_API.rstrip('/')}/{endpoint.lstrip('/')}"
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "Fuse-CLI/1.0", "Accept": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}

# -------------------------------------------------------------------------
# Command: STATUS
# -------------------------------------------------------------------------
def cmd_status(args):
    print_header()
    print(f"{C.BOLD}► SYSTEM HEALTH & GUARDRAIL TELEMETRY{C.RESET}")
    print(f"  {C.SLATE}Region:{C.RESET} {DEFAULT_REGION}  {C.SLATE}│  Control Base:{C.RESET} {DEFAULT_CONTROL_API}")
    print()

    # 1. Target API Health
    target_ok = False
    try:
        req = urllib.request.Request(DEFAULT_TARGET_API, headers={"User-Agent": "Fuse-CLI/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            target_status = f"{C.GREEN}ONLINE (HTTP {r.status}){C.RESET}"
            target_ok = True
    except urllib.error.HTTPError as e:
        if e.code == 403:
            target_status = f"{C.RED}BLOCKED (HTTP 403 WAF){C.RESET}"
        else:
            target_status = f"{C.YELLOW}HTTP {e.code}{C.RESET}"
    except Exception as e:
        target_status = f"{C.RED}UNREACHABLE ({e}){C.RESET}"

    # 2. Control API Health & Incidents Count
    incidents_data = api_get("/incidents")
    if "error" in incidents_data:
        control_status = f"{C.RED}FAILED ({incidents_data['error']}){C.RESET}"
        incidents = []
    else:
        control_status = f"{C.GREEN}HEALTHY{C.RESET}"
        incidents = incidents_data.get("incidents", [])

    # 3. WAF IP Set Check
    blocked_ips = []
    waf_status = f"{C.SLATE}Boto3 not configured{C.RESET}"
    if BOTO3_AVAILABLE:
        try:
            waf = boto3.client("wafv2", region_name=DEFAULT_REGION)
            ip_set = waf.get_ip_set(Scope="REGIONAL", Name=WAF_IP_SET_NAME, Id=WAF_IP_SET_ID)
            addresses = ip_set.get("IPSet", {}).get("Addresses", [])
            blocked_ips = addresses
            waf_status = f"{C.GREEN}ACTIVE{C.RESET} ({len(addresses)} IPs blocked)"
        except Exception as e:
            waf_status = f"{C.YELLOW}AWS access limited ({e}){C.RESET}"

    # Status Cards Grid
    print(f"  ┌─ {C.BOLD}API Gateway Status{C.RESET}")
    print(f"  │  Target REST Endpoint:   {DEFAULT_TARGET_API}")
    print(f"  │  Gateway Connectivity:   {target_status}")
    print(f"  │  Control Plane Health:   {control_status}")
    print(f"  │")
    print(f"  ├─ {C.BOLD}WAF Edge Circuit Breaker{C.RESET}")
    print(f"  │  WAF IP Set:             {WAF_IP_SET_NAME} ({WAF_IP_SET_ID[:8]}...)")
    print(f"  │  Circuit State:          {waf_status}")
    if blocked_ips:
        for ip in blocked_ips:
            print(f"  │   └── {C.RED}⛔ {ip}{C.RESET}")
    else:
        print(f"  │   └── {C.GREEN}✓ No active IP blocks (100% traffic flowing){C.RESET}")
    print(f"  │")
    print(f"  └─ {C.BOLD}Telemetry Summary{C.RESET}")
    runaway_count = sum(1 for i in incidents if i.get("classification") == "RUNAWAY")
    normal_count = sum(1 for i in incidents if i.get("classification") == "NORMAL")
    print(f"     Total Detected Events:  {len(incidents)}")
    print(f"     Runaway Anomalies:      {C.RED}{runaway_count}{C.RESET}")
    print(f"     Normal Traffic Passes:  {C.GREEN}{normal_count}{C.RESET}")
    print()

# -------------------------------------------------------------------------
# Command: INCIDENTS
# -------------------------------------------------------------------------
def cmd_incidents(args):
    data = api_get("/incidents")
    if "error" in data:
        print(f"{C.RED}[ERROR] Failed to fetch incidents:{C.RESET} {data['error']}", file=sys.stderr)
        sys.exit(1)

    incidents = data.get("incidents", [])
    if args.limit:
        incidents = incidents[:args.limit]

    if args.json:
        print(json.dumps(incidents, indent=2))
        return

    print_header()
    print(f"{C.BOLD}► RECENT INCIDENTS & ANOMALY EVALUATIONS (Showing {len(incidents)}){C.RESET}\n")

    if not incidents:
        print(f"  {C.GREEN}No recent incidents recorded in DynamoDB.{C.RESET}\n")
        return

    header_fmt = f"  {C.BOLD}{'TIME (UTC)':<18} {'INCIDENT ID':<16} {'CLASSIFICATION':<14} {'ACTION':<18} {'CONF':<6} {'EXPLANATION'}{C.RESET}"
    print(header_fmt)
    print("  " + "─" * 100)

    for item in incidents:
        ts = item.get("timestamp", 0)
        dt_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M") if ts else "N/A"
        inc_id = item.get("incident_id", "unknown")[:14] + ".."
        classification = item.get("classification", "UNKNOWN")
        action = item.get("action_taken", "NONE")
        confidence = f"{float(item.get('confidence', 0.0)):.2f}" if item.get('confidence') else "1.00"
        expl = item.get("bedrock_explanation", "Deterministic rule evaluation")
        expl_short = (expl[:42] + "...") if len(expl) > 42 else expl

        # Color badges
        if classification == "RUNAWAY":
            c_tag = f"{C.RED}[RUNAWAY]{C.RESET}"
        elif classification == "NORMAL":
            c_tag = f"{C.GREEN}[NORMAL]{C.RESET} "
        else:
            c_tag = f"{C.YELLOW}[{classification}]{C.RESET}"

        if "BLOCK" in action:
            act_tag = f"{C.RED}{action[:16]}{C.RESET}"
        elif "APPROVAL" in action:
            act_tag = f"{C.YELLOW}{action[:16]}{C.RESET}"
        else:
            act_tag = f"{C.SLATE}{action[:16]}{C.RESET}"

        print(f"  {dt_str:<18} {inc_id:<16} {c_tag:<23} {act_tag:<27} {confidence:<6} {expl_short}")

    print()

# -------------------------------------------------------------------------
# Command: BLOCK (Surgical IP Block)
# -------------------------------------------------------------------------
def cmd_block(args):
    ip = args.ip.strip()
    if "/" in ip:
        ip = ip.split("/")[0]

    cidr = f"{ip}/32"
    reason = args.reason or "Surgical block initiated via Fuse CLI"

    print(f"[*] Initiating surgical WAF block for {C.BOLD}{cidr}{C.RESET}...")

    if not BOTO3_AVAILABLE:
        print(f"{C.RED}[ERROR] Boto3 is required for direct WAF modification.{C.RESET}", file=sys.stderr)
        sys.exit(1)

    try:
        waf = boto3.client("wafv2", region_name=DEFAULT_REGION)
        ip_set = waf.get_ip_set(Scope="REGIONAL", Name=WAF_IP_SET_NAME, Id=WAF_IP_SET_ID)
        lock_token = ip_set["LockToken"]
        addresses = set(ip_set.get("IPSet", {}).get("Addresses", []))

        if cidr in addresses:
            print(f"{C.YELLOW}[!] {cidr} is already in WAF IP Set '{WAF_IP_SET_NAME}'.{C.RESET}")
            return

        addresses.add(cidr)
        waf.update_ip_set(
            Scope="REGIONAL",
            Name=WAF_IP_SET_NAME,
            Id=WAF_IP_SET_ID,
            Addresses=list(addresses),
            LockToken=lock_token
        )

        # Log to DynamoDB Incidents
        ddb = boto3.resource("dynamodb", region_name=DEFAULT_REGION)
        incidents_table = ddb.Table("Incidents")
        now_epoch = int(time.time())
        incidents_table.put_item(Item={
            "incident_id": f"cli-block-{now_epoch}",
            "timestamp": now_epoch,
            "resource": "guardrail-demo-api",
            "environment": "prod",
            "classification": "RUNAWAY",
            "action_taken": "IP_BLOCKED",
            "blocked_ips": [ip],
            "bedrock_explanation": reason,
            "confidence": 1,
        })

        print(f"{C.GREEN}✓ [SUCCESS] Blocked {cidr} in WAF IP Set '{WAF_IP_SET_NAME}'.{C.RESET}")
        print(f"  Incident audit record created: cli-block-{now_epoch}")
        print(f"  Offending caller will now receive HTTP 403 at the AWS edge.")
    except Exception as e:
        print(f"{C.RED}[ERROR] Failed to update WAF IP Set:{C.RESET} {e}", file=sys.stderr)
        sys.exit(1)

# -------------------------------------------------------------------------
# Command: UNBLOCK
# -------------------------------------------------------------------------
def cmd_unblock(args):
    ip = args.ip.strip()
    if "/" in ip:
        ip = ip.split("/")[0]

    cidr = f"{ip}/32"
    print(f"[*] Releasing {C.BOLD}{cidr}{C.RESET} from WAF block...")

    if not BOTO3_AVAILABLE:
        print(f"{C.RED}[ERROR] Boto3 is required for direct WAF modification.{C.RESET}", file=sys.stderr)
        sys.exit(1)

    try:
        waf = boto3.client("wafv2", region_name=DEFAULT_REGION)
        ip_set = waf.get_ip_set(Scope="REGIONAL", Name=WAF_IP_SET_NAME, Id=WAF_IP_SET_ID)
        lock_token = ip_set["LockToken"]
        addresses = set(ip_set.get("IPSet", {}).get("Addresses", []))

        if cidr not in addresses:
            print(f"{C.YELLOW}[!] {cidr} was not found in WAF IP Set.{C.RESET}")
            return

        addresses.remove(cidr)
        waf.update_ip_set(
            Scope="REGIONAL",
            Name=WAF_IP_SET_NAME,
            Id=WAF_IP_SET_ID,
            Addresses=list(addresses),
            LockToken=lock_token
        )

        print(f"{C.GREEN}✓ [SUCCESS] Unblocked {cidr}. Traffic restored for this caller.{C.RESET}")
    except Exception as e:
        print(f"{C.RED}[ERROR] Failed to unblock {cidr}:{C.RESET} {e}", file=sys.stderr)
        sys.exit(1)

# -------------------------------------------------------------------------
# Command: DEPLOY-HEARTBEAT
# -------------------------------------------------------------------------
def cmd_heartbeat(args):
    deploy_id = args.id or str(uuid.uuid4())[:8]
    note = args.note or f"Deploy heartbeat via Fuse CLI by {os.environ.get('USER', 'developer')}"
    resource = args.resource or "guardrail-demo-api"

    print(f"[*] Logging deployment heartbeat for resource '{resource}'...")

    if not BOTO3_AVAILABLE:
        print(f"{C.RED}[ERROR] Boto3 required to write to DynamoDB Deployments table.{C.RESET}", file=sys.stderr)
        sys.exit(1)

    try:
        ddb = boto3.resource("dynamodb", region_name=DEFAULT_REGION)
        table = ddb.Table(DEPLOYMENTS_TABLE)
        now_epoch = int(time.time())

        table.put_item(Item={
            "deployment_id": deploy_id,
            "timestamp": now_epoch,
            "resource": resource,
            "note": note,
        })

        print(f"{C.GREEN}✓ [SUCCESS] Heartbeat logged to '{DEPLOYMENTS_TABLE}' table ({DEFAULT_REGION}).{C.RESET}")
        print(f"  Deploy ID:    {deploy_id}")
        print(f"  Note:         {note}")
        print(f"  Suppression:  15-minute window active (false alarm protection enabled).")
    except Exception as e:
        print(f"{C.RED}[ERROR] Failed to record heartbeat:{C.RESET} {e}", file=sys.stderr)
        sys.exit(1)

# -------------------------------------------------------------------------
# Command: TEST (Traffic Probe)
# -------------------------------------------------------------------------
def cmd_test(args):
    scenario = args.scenario.lower()
    total_reqs = args.requests or (15 if scenario == "runaway" else 10)

    print_header()
    print(f"{C.BOLD}► SIMULATING {scenario.upper()} TRAFFIC PATTERN{C.RESET}")
    print(f"  Target: {DEFAULT_TARGET_API}")
    print(f"  Sending {total_reqs} requests...\n")

    if scenario == "runaway":
        # Single rogue caller hammering endpoint
        spoofed_ip = "198.51.100.99"
        print(f"  Pattern: Single caller ({spoofed_ip}) rapid burst")
        for i in range(1, total_reqs + 1):
            req = urllib.request.Request(
                DEFAULT_TARGET_API,
                headers={"X-Forwarded-For": spoofed_ip, "User-Agent": "Fuse-Runaway-Agent/1.0"}
            )
            try:
                t0 = time.time()
                with urllib.request.urlopen(req, timeout=4) as resp:
                    latency_ms = int((time.time() - t0) * 1000)
                    print(f"  [{i:02d}/{total_reqs:02d}] {C.GREEN}200 OK{C.RESET} from {spoofed_ip} ({latency_ms}ms)")
            except urllib.error.HTTPError as e:
                latency_ms = int((time.time() - t0) * 1000)
                if e.code == 403:
                    print(f"  [{i:02d}/{total_reqs:02d}] {C.RED}403 FORBIDDEN (WAF DROPPED){C.RESET} from {spoofed_ip} ({latency_ms}ms)")
                else:
                    print(f"  [{i:02d}/{total_reqs:02d}] {C.YELLOW}HTTP {e.code}{C.RESET} ({latency_ms}ms)")
            time.sleep(0.08)
    else:
        # Legitimate distributed buyers
        print(f"  Pattern: High-diversity organic callers")
        for i in range(1, total_reqs + 1):
            ip = f"203.0.113.{10 + i}"
            req = urllib.request.Request(
                DEFAULT_TARGET_API,
                headers={"X-Forwarded-For": ip, "User-Agent": "Mozilla/5.0"}
            )
            try:
                t0 = time.time()
                with urllib.request.urlopen(req, timeout=4) as resp:
                    latency_ms = int((time.time() - t0) * 1000)
                    print(f"  [{i:02d}/{total_reqs:02d}] {C.GREEN}200 OK{C.RESET} from {ip} ({latency_ms}ms)")
            except urllib.error.HTTPError as e:
                latency_ms = int((time.time() - t0) * 1000)
                print(f"  [{i:02d}/{total_reqs:02d}] {C.YELLOW}HTTP {e.code}{C.RESET} ({latency_ms}ms)")
            time.sleep(0.08)

    print(f"\n{C.GREEN}✓ Probe complete.{C.RESET}\n")

# -------------------------------------------------------------------------
# Command: CONFIG
# -------------------------------------------------------------------------
def cmd_config(args):
    print_header()
    print(f"{C.BOLD}► FUSE CLI CONFIGURATION{C.RESET}\n")
    print(f"  AWS Region:          {DEFAULT_REGION}")
    print(f"  Control API Base:    {DEFAULT_CONTROL_API}")
    print(f"  Target API URL:      {DEFAULT_TARGET_API}")
    print(f"  WAF IP Set:          {WAF_IP_SET_NAME} (ID: {WAF_IP_SET_ID})")
    print(f"  Deployments Table:   {DEPLOYMENTS_TABLE}")
    print(f"  Remediator Lambda:   {REMEDIATOR_LAMBDA}")
    print(f"  Boto3 Driver:        {'Available' if BOTO3_AVAILABLE else 'Not Installed'}")
    print()

# -------------------------------------------------------------------------
# Main Argument Dispatcher
# -------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        prog="fuse",
        description="Fuse CLI — Autonomous AWS Cost Guardrail & Surgical WAF Circuit Breaker"
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # status
    p_status = subparsers.add_parser("status", help="Show live guardrail status, WAF blocks, and API health")

    # incidents
    p_incidents = subparsers.add_parser("incidents", help="List recent detected anomalies and AI reasoning")
    p_incidents.add_argument("--limit", "-n", type=int, default=10, help="Maximum incidents to display")
    p_incidents.add_argument("--json", action="store_true", help="Output raw JSON for scripting")

    # block
    p_block = subparsers.add_parser("block", help="Surgically block an IP at the AWS WAF edge")
    p_block.add_argument("ip", help="IPv4 address to block (e.g. 198.51.100.99)")
    p_block.add_argument("--reason", "-r", help="Reason for blocking")

    # unblock
    p_unblock = subparsers.add_parser("unblock", help="Remove an IP from the WAF blocked set")
    p_unblock.add_argument("ip", help="IPv4 address to unblock")

    # heartbeat
    p_heartbeat = subparsers.add_parser("heartbeat", help="Log deployment heartbeat to suppress false alarms")
    p_heartbeat.add_argument("--id", help="Deployment identifier (commit hash, tag)")
    p_heartbeat.add_argument("--note", help="Deploy notes or commit message")
    p_heartbeat.add_argument("--resource", help="Target API Gateway resource name")

    # test
    p_test = subparsers.add_parser("test", help="Simulate live traffic probe")
    p_test.add_argument("--scenario", "-s", choices=["runaway", "legit"], default="runaway", help="Traffic pattern")
    p_test.add_argument("--requests", "-r", type=int, help="Number of test requests")

    # config
    p_config = subparsers.add_parser("config", help="Show active endpoints and configuration")

    args = parser.parse_args()

    if not args.subcommand or args.subcommand == "status":
        cmd_status(args)
    elif args.subcommand == "incidents":
        cmd_incidents(args)
    elif args.subcommand == "block":
        cmd_block(args)
    elif args.subcommand == "unblock":
        cmd_unblock(args)
    elif args.subcommand == "heartbeat":
        cmd_heartbeat(args)
    elif args.subcommand == "test":
        cmd_test(args)
    elif args.subcommand == "config":
        cmd_config(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
