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
    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key",
}


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

    # 3. Lookup item in ApprovalQueue or Incidents to get resource and stage
    resource = "guardrail-demo-api"
    stage = "prod"
    try:
        q_item = approval_table.get_item(Key={"approval_id": incident_id}).get("Item")
        if q_item:
            resource = q_item.get("resource", resource)
            stage = q_item.get("stage", stage)
    except Exception as e:
        logger.warning(f"Could not fetch ApprovalQueue item for {incident_id}: {e}")

    throttled = False

    if decision == "APPROVED":
        # 4. Trigger Remediator Lambda to throttle stage
        logger.info(f"Decision APPROVED: Invoking Remediator for {resource} [{stage}]...")
        try:
            rem_resp = lambda_client.invoke(
                FunctionName=REMEDIATOR_FUNCTION_NAME,
                InvocationType="RequestResponse",
                Payload=json.dumps({
                    "incident_id": incident_id,
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
            UpdateExpression="SET #st = :status, resolved_by = :by, resolved_at = :at",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":status": "APPROVED",
                ":by": resolved_by,
                ":at": now_epoch,
            },
        )

        # Update Incidents table
        try:
            incidents_table.update_item(
                Key={"incident_id": incident_id},
                UpdateExpression="SET action_taken = :act",
                ExpressionAttributeValues={":act": "APPROVED_AND_THROTTLED"},
            )
        except Exception as e:
            logger.warning(f"Failed to update Incidents table for {incident_id}: {e}")

    elif decision == "REJECTED":
        logger.info(f"Decision REJECTED for incident {incident_id}. Skipping throttling.")
        approval_table.update_item(
            Key={"approval_id": incident_id},
            UpdateExpression="SET #st = :status, resolved_by = :by, resolved_at = :at",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":status": "REJECTED",
                ":by": resolved_by,
                ":at": now_epoch,
            },
        )
        try:
            incidents_table.update_item(
                Key={"incident_id": incident_id},
                UpdateExpression="SET action_taken = :act",
                ExpressionAttributeValues={":act": "REJECTED"},
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

    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": json.dumps(response_payload),
    }
