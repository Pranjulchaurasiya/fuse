"""Approve Action Lambda: Handles human approval for prod runaway incidents.

Contract (API.md):
POST /incidents/{incident_id}/approve
Request body: { "resolved_by": "Pranjul", "decision": "APPROVED" | "REJECTED" }
Response 200: { "approval_id": "string", "status": "APPROVED", "throttled": true }
"""

import json
import logging
import os
import time
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION_NAME = os.environ.get("AWS_REGION", "ap-south-1")
APPROVAL_QUEUE_TABLE = os.environ.get("APPROVAL_QUEUE_TABLE", "ApprovalQueue")
INCIDENTS_TABLE = os.environ.get("INCIDENTS_TABLE", "Incidents")
REMEDIATOR_FUNCTION_NAME = os.environ.get("REMEDIATOR_FUNCTION_NAME", "guardrail-remediator")

dynamodb_resource = boto3.resource("dynamodb", region_name=REGION_NAME)
lambda_client = boto3.client("lambda", region_name=REGION_NAME)
approval_table = dynamodb_resource.Table(APPROVAL_QUEUE_TABLE)
incidents_table = dynamodb_resource.Table(INCIDENTS_TABLE)

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,x-api-key",
}


def emit_emf_metric(metric_name, value, unit="Count", dimensions=None):
    """Emits high-cardinality CloudWatch Embedded Metric Format (EMF) logs for SIEM & CloudWatch Metrics."""
    try:
        dims = dimensions or {}
        now_ms = int(time.time() * 1000)
        dim_keys = list(dims.keys())
        payload = {
            "_aws": {
                "Timestamp": now_ms,
                "CloudWatchMetrics": [
                    {
                        "Namespace": "Fuse/Guardrail",
                        "Dimensions": [dim_keys] if dim_keys else [],
                        "Metrics": [{"Name": metric_name, "Unit": unit}]
                    }
                ]
            },
            metric_name: value,
            **dims
        }
        print(json.dumps(payload))
    except Exception as e:
        logger.warning(f"Failed to emit EMF metric {metric_name}: {e}")


def lambda_handler(event, context):
    logger.info(f"Approve action received event: {json.dumps(event)}")

    # 1. Handle HTTP OPTIONS for CORS pre-flight
    if event.get("httpMethod") == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps({"status": "ok"}),
        }

    # 2. Extract incident_id from path parameters or body
    path_params = event.get("pathParameters") or {}
    incident_id = path_params.get("incident_id")

    body_raw = event.get("body") or {}
    if isinstance(body_raw, str):
        try:
            body = json.loads(body_raw)
        except Exception:
            body = {}
    else:
        body = body_raw

    if not incident_id:
        incident_id = body.get("incident_id")

    if not incident_id:
        return {
            "statusCode": 400,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": "Missing incident_id in path or body."}),
        }

    resolved_by = body.get("resolved_by", "Unknown Reviewer")
    decision = str(body.get("decision", "APPROVED")).upper()
    now_epoch = int(time.time())

    # Extract caller identity from Cognito Authorizer or request context
    auth_claims = (event.get("requestContext") or {}).get("authorizer", {}).get("claims", {})
    actor_email = auth_claims.get("email") or resolved_by
    actor_sub = auth_claims.get("sub", "unauthenticated")
    caller_tenant_id = auth_claims.get("custom:tenant_id")
    client_ip = (event.get("requestContext") or {}).get("identity", {}).get("sourceIp", "unknown")

    # 3. Lookup item in ApprovalQueue or Incidents to get resource, stage, and source_ips
    resource = "guardrail-demo-api"
    stage = "prod"
    source_ips = body.get("source_ips", [])
    try:
        q_item = approval_table.get_item(Key={"approval_id": incident_id}).get("Item")
        if q_item:
            resource = q_item.get("resource", resource)
            stage = q_item.get("stage", stage)
            if not source_ips and q_item.get("source_ips"):
                source_ips = q_item.get("source_ips")
    except Exception as e:
        logger.warning(f"Could not fetch ApprovalQueue item for {incident_id}: {e}")

    inc_item = None
    try:
        inc_item = incidents_table.get_item(Key={"incident_id": incident_id}).get("Item")
        if inc_item and not source_ips:
            if inc_item.get("source_ips"):
                source_ips = inc_item.get("source_ips")
            elif inc_item.get("blocked_ips"):
                source_ips = inc_item.get("blocked_ips")
    except Exception as e:
        logger.warning(f"Could not fetch Incidents item for {incident_id}: {e}")

    # Enforce multi-tenant isolation (T-2.3):
    if inc_item:
        item_tenant = inc_item.get("tenant_id")
        if item_tenant and item_tenant != "default":
            if not caller_tenant_id or (caller_tenant_id != "admin" and item_tenant != caller_tenant_id):
                logger.warning(f"Tenant isolation breach attempt: Caller tenant {caller_tenant_id} on item tenant {item_tenant}")
                return {
                    "statusCode": 403,
                    "headers": CORS_HEADERS,
                    "body": json.dumps({"error": "Forbidden", "message": "Incident belongs to another tenant"}),
                }

    audit_entry = {
        "action": f"APPROVAL_{decision}",
        "actor_identity": actor_email,
        "actor_sub": actor_sub,
        "client_ip": client_ip,
        "timestamp_utc": now_epoch,
        "decision": decision,
    }

    throttled = False

    if decision == "APPROVED":
        # 4. Trigger Remediator Lambda to block offending IPs via WAF
        logger.info(f"Decision APPROVED: Invoking Remediator for {resource} [{stage}], IPs: {source_ips}...")
        try:
            rem_resp = lambda_client.invoke(
                FunctionName=REMEDIATOR_FUNCTION_NAME,
                InvocationType="RequestResponse",
                Payload=json.dumps({
                    "action": "BLOCK",
                    "incident_id": incident_id,
                    "source_ips": source_ips,
                    "resource": resource,
                    "stage": stage,
                    "trigger_source": "human_approval",
                }),
            )
            rem_body = json.loads(rem_resp["Payload"].read().decode("utf-8"))
            logger.info(f"Remediator result: {rem_body}")
            throttled = True
        except Exception as rem_err:
            logger.error(f"Failed to invoke Remediator: {rem_err}", exc_info=True)

        # Update ApprovalQueue
        approval_table.update_item(
            Key={"approval_id": incident_id},
            UpdateExpression="SET #st = :status, resolved_by = :by, resolved_at = :at, actor_sub = :sub",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":status": "APPROVED",
                ":by": actor_email,
                ":at": now_epoch,
                ":sub": actor_sub,
            },
        )

        # Update Incidents table with structured audit trail
        try:
            incidents_table.update_item(
                Key={"incident_id": incident_id},
                UpdateExpression="SET action_taken = :act, audit_trail = list_append(if_not_exists(audit_trail, :empty_list), :audit_entry)",
                ExpressionAttributeValues={
                    ":act": "APPROVED_AND_BLOCKED",
                    ":empty_list": [],
                    ":audit_entry": [audit_entry],
                },
            )
        except Exception as e:
            logger.warning(f"Failed to update Incidents table for {incident_id}: {e}")

    elif decision == "REJECTED":
        logger.info(f"Decision REJECTED for incident {incident_id}. Skipping throttling.")
        approval_table.update_item(
            Key={"approval_id": incident_id},
            UpdateExpression="SET #st = :status, resolved_by = :by, resolved_at = :at, actor_sub = :sub",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":status": "REJECTED",
                ":by": actor_email,
                ":at": now_epoch,
                ":sub": actor_sub,
            },
        )
        try:
            incidents_table.update_item(
                Key={"incident_id": incident_id},
                UpdateExpression="SET action_taken = :act, audit_trail = list_append(if_not_exists(audit_trail, :empty_list), :audit_entry)",
                ExpressionAttributeValues={
                    ":act": "REJECTED",
                    ":empty_list": [],
                    ":audit_entry": [audit_entry],
                },
            )
        except Exception as e:
            logger.warning(f"Failed to update Incidents table for {incident_id}: {e}")
    else:
        return {
            "statusCode": 400,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": f"Invalid decision '{decision}'. Expected APPROVED or REJECTED."}),
        }

    response_payload = {
        "approval_id": incident_id,
        "status": decision,
        "throttled": throttled,
    }

    # Emit CloudWatch EMF Metric for SIEM & CloudWatch Dashboards
    emit_emf_metric(
        "OperatorApprovalDecision",
        1,
        unit="Count",
        dimensions={
            "Decision": decision,
            "Resource": resource,
            "Stage": stage,
        }
    )

    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": json.dumps(response_payload),
    }
