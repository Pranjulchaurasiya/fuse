#!/usr/bin/env python3
"""
Fuse MCP Server — Model Context Protocol Server for Autonomous AWS Cost Guardrail.

Exposes native tools and resources to AI Agents (Claude Desktop, Cursor, Copilot, Antigravity)
to inspect real-time runaway traffic anomalies, trigger surgical WAF circuit breakers,
and manage canary deployment heartbeats.

Protocol: MCP (Model Context Protocol) over stdio / FastMCP
Run via:
    python mcp_server.py
Or in claude_desktop_config.json:
    {
      "mcpServers": {
        "fuse": {
          "command": "python",
          "args": ["c:/Users/pranj/Documents/Fuse/mcp_server.py"]
        }
      }
    }
"""

import os
import sys
import json
import time
import uuid
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List

# Reconfigure utf-8 on stdio
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

from mcp.server.fastmcp import FastMCP

# Default Config (Overridable via Environment)
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
DEPLOYMENTS_TABLE = os.environ.get("DEPLOYMENTS_TABLE", "Deployments")

# Initialize FastMCP Server
mcp = FastMCP(
    "fuse-cost-guardrail",
    instructions="Fuse is an autonomous AWS Cost Guardrail & WAF Circuit Breaker. "
                 "Use these tools to query real-time traffic anomalies, inspect runaway loop incidents, "
                 "surgically block offending caller IPs at AWS WAFv2 edge, and log deployment heartbeats."
)


# Helper functions
def _api_get(endpoint: str) -> dict:
    url = f"{DEFAULT_CONTROL_API.rstrip('/')}/{endpoint.lstrip('/')}"
    req = urllib.request.Request(url, headers={"User-Agent": "Fuse-MCP/1.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


# -------------------------------------------------------------------------
# Tool: fuse_get_status
# -------------------------------------------------------------------------
@mcp.tool()
def fuse_get_status() -> Dict[str, Any]:
    """
    Get live system health and guardrail telemetry for Fuse.
    Returns:
      - Target API Gateway status and latency
      - AWS WAF circuit breaker status and currently blocked IP addresses
      - Incident statistics (runaway anomalies vs normal traffic evaluations)
    """
    # 1. Target API probe
    target_status = "UNKNOWN"
    try:
        req = urllib.request.Request(DEFAULT_TARGET_API, headers={"User-Agent": "Fuse-MCP/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            target_status = f"ONLINE (HTTP {r.status})"
    except urllib.error.HTTPError as e:
        target_status = f"BLOCKED (HTTP 403 WAF)" if e.code == 403 else f"HTTP {e.code}"
    except Exception as e:
        target_status = f"UNREACHABLE ({str(e)})"

    # 2. Control API & incidents
    incidents_data = _api_get("/incidents")
    incidents = incidents_data.get("incidents", []) if "incidents" in incidents_data else []
    runaway_count = sum(1 for i in incidents if i.get("classification") == "RUNAWAY")
    normal_count = sum(1 for i in incidents if i.get("classification") == "NORMAL")

    # 3. WAF IP Set inspection
    blocked_ips = []
    waf_state = "UNKNOWN"
    if BOTO3_AVAILABLE:
        try:
            waf = boto3.client("wafv2", region_name=DEFAULT_REGION)
            ip_set = waf.get_ip_set(Scope="REGIONAL", Name=WAF_IP_SET_NAME, Id=WAF_IP_SET_ID)
            blocked_ips = ip_set.get("IPSet", {}).get("Addresses", [])
            waf_state = "ACTIVE"
        except Exception as e:
            waf_state = f"ERROR ({str(e)})"
    else:
        waf_state = "BOTO3_UNAVAILABLE"

    return {
        "status": "HEALTHY",
        "region": DEFAULT_REGION,
        "control_plane_api": DEFAULT_CONTROL_API,
        "target_api": {
            "endpoint": DEFAULT_TARGET_API,
            "status": target_status,
        },
        "waf_circuit_breaker": {
            "state": waf_state,
            "ip_set_name": WAF_IP_SET_NAME,
            "ip_set_id": WAF_IP_SET_ID,
            "blocked_count": len(blocked_ips),
            "blocked_ips": blocked_ips,
        },
        "telemetry": {
            "total_incidents": len(incidents),
            "runaway_anomalies": runaway_count,
            "normal_evaluations": normal_count,
        }
    }


# -------------------------------------------------------------------------
# Tool: fuse_list_incidents
# -------------------------------------------------------------------------
@mcp.tool()
def fuse_list_incidents(limit: int = 10, classification_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    List recent detected traffic anomalies, Z-score spikes, and Bedrock/deterministic evaluations.
    Args:
      limit: Number of recent incidents to return (default: 10)
      classification_filter: Optional filter ('RUNAWAY' or 'NORMAL')
    """
    data = _api_get("/incidents")
    if "error" in data:
        return {"success": False, "error": data["error"]}

    incidents = data.get("incidents", [])
    if classification_filter:
        flt = classification_filter.upper()
        incidents = [i for i in incidents if i.get("classification", "").upper() == flt]

    incidents = incidents[:limit]
    return {
        "success": True,
        "count": len(incidents),
        "incidents": incidents
    }


# -------------------------------------------------------------------------
# Tool: fuse_block_ip
# -------------------------------------------------------------------------
@mcp.tool()
def fuse_block_ip(ip_address: str, reason: str = "Surgical block initiated via Fuse MCP") -> Dict[str, Any]:
    """
    Surgically block an abusive caller IP address at the AWS WAF edge.
    Stops runaway recursive loops and bill surges without degrading legitimate user traffic.
    Args:
      ip_address: IPv4 address to block (e.g. '198.51.100.99')
      reason: Human or agent explanation for why this IP is being blocked
    """
    ip = ip_address.strip()
    if "/" in ip:
        ip = ip.split("/")[0]
    cidr = f"{ip}/32"

    if not BOTO3_AVAILABLE:
        return {"success": False, "error": "boto3 library not installed or AWS credentials missing"}

    try:
        waf = boto3.client("wafv2", region_name=DEFAULT_REGION)
        ip_set = waf.get_ip_set(Scope="REGIONAL", Name=WAF_IP_SET_NAME, Id=WAF_IP_SET_ID)
        lock_token = ip_set["LockToken"]
        addresses = set(ip_set.get("IPSet", {}).get("Addresses", []))

        if cidr in addresses:
            return {
                "success": True,
                "status": "ALREADY_BLOCKED",
                "ip": cidr,
                "message": f"{cidr} is already present in WAF IP Set '{WAF_IP_SET_NAME}'"
            }

        addresses.add(cidr)
        waf.update_ip_set(
            Scope="REGIONAL",
            Name=WAF_IP_SET_NAME,
            Id=WAF_IP_SET_ID,
            Addresses=list(addresses),
            LockToken=lock_token
        )

        # Audit write to DynamoDB Incidents
        now_epoch = int(time.time())
        incident_id = f"mcp-block-{now_epoch}"
        try:
            ddb = boto3.resource("dynamodb", region_name=DEFAULT_REGION)
            table = ddb.Table("Incidents")
            table.put_item(Item={
                "incident_id": incident_id,
                "timestamp": now_epoch,
                "resource": "guardrail-demo-api",
                "environment": "prod",
                "classification": "RUNAWAY",
                "action_taken": "IP_BLOCKED",
                "blocked_ips": [ip],
                "bedrock_explanation": reason,
                "confidence": 1,
            })
        except Exception:
            pass

        return {
            "success": True,
            "status": "IP_BLOCKED",
            "ip": cidr,
            "incident_id": incident_id,
            "total_blocked_count": len(addresses),
            "message": f"Successfully added {cidr} to WAF IP Set. Rogue caller will now receive HTTP 403 at edge."
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


# -------------------------------------------------------------------------
# Tool: fuse_unblock_ip
# -------------------------------------------------------------------------
@mcp.tool()
def fuse_unblock_ip(ip_address: str) -> Dict[str, Any]:
    """
    Remove an IP address from the WAF blocked set to restore traffic.
    Args:
      ip_address: IPv4 address to unblock (e.g. '198.51.100.99')
    """
    ip = ip_address.strip()
    if "/" in ip:
        ip = ip.split("/")[0]
    cidr = f"{ip}/32"

    if not BOTO3_AVAILABLE:
        return {"success": False, "error": "boto3 library not installed"}

    try:
        waf = boto3.client("wafv2", region_name=DEFAULT_REGION)
        ip_set = waf.get_ip_set(Scope="REGIONAL", Name=WAF_IP_SET_NAME, Id=WAF_IP_SET_ID)
        lock_token = ip_set["LockToken"]
        addresses = set(ip_set.get("IPSet", {}).get("Addresses", []))

        if cidr not in addresses:
            return {
                "success": True,
                "status": "NOT_FOUND",
                "ip": cidr,
                "message": f"{cidr} was not present in WAF IP Set."
            }

        addresses.remove(cidr)
        waf.update_ip_set(
            Scope="REGIONAL",
            Name=WAF_IP_SET_NAME,
            Id=WAF_IP_SET_ID,
            Addresses=list(addresses),
            LockToken=lock_token
        )

        return {
            "success": True,
            "status": "IP_UNBLOCKED",
            "ip": cidr,
            "total_blocked_count": len(addresses),
            "message": f"Successfully removed {cidr} from WAF IP Set. Traffic restored for caller."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# -------------------------------------------------------------------------
# Tool: fuse_log_heartbeat
# -------------------------------------------------------------------------
@mcp.tool()
def fuse_log_heartbeat(note: str = "Deployment heartbeat via Fuse MCP", resource: str = "guardrail-demo-api") -> Dict[str, Any]:
    """
    Log a deployment heartbeat into DynamoDB Deployments table.
    Activates a 15-minute suppression window to prevent false-alarm circuit breakers during planned CI/CD deployments.
    Args:
      note: Deployment or commit description (e.g. 'Deploying v1.4.2 checkout worker')
      resource: Protected AWS resource identifier
    """
    if not BOTO3_AVAILABLE:
        return {"success": False, "error": "boto3 library not installed"}

    deploy_id = str(uuid.uuid4())[:8]
    now_epoch = int(time.time())

    try:
        ddb = boto3.resource("dynamodb", region_name=DEFAULT_REGION)
        table = ddb.Table(DEPLOYMENTS_TABLE)
        table.put_item(Item={
            "deployment_id": deploy_id,
            "timestamp": now_epoch,
            "resource": resource,
            "note": note,
        })
        return {
            "success": True,
            "deployment_id": deploy_id,
            "timestamp": now_epoch,
            "resource": resource,
            "suppression_window_minutes": 15,
            "message": f"Deployment heartbeat logged. False alarm suppression active for 15 minutes."
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# -------------------------------------------------------------------------
# MCP Resource: fuse://status
# -------------------------------------------------------------------------
@mcp.resource("fuse://status")
def fuse_status_resource() -> str:
    """Read-only JSON resource containing live Fuse system health and circuit breaker state."""
    status_data = fuse_get_status()
    return json.dumps(status_data, indent=2)


if __name__ == "__main__":
    # Runs the stdio MCP server loop
    mcp.run()
