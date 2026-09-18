"""Remediator Lambda: Executes API Gateway stage throttle (RateLimit/BurstLimit -> 0).

Adheres strictly to ARCHITECTURE.md and API.md:
- One remediation target only: API Gateway stage throttle.
- Strict idempotency: if already throttled to 0, returns ALREADY_THROTTLED without error.
- Updates the incident record in DynamoDB Incidents table.
"""

import json
import logging
import os
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION_NAME = os.environ.get("AWS_REGION", "ap-south-1")
TARGET_API_ID = os.environ.get("TARGET_API_ID", "poim5xmgs2")
TARGET_API_NAME = os.environ.get("TARGET_API_NAME", "guardrail-demo-api")
INCIDENTS_TABLE = os.environ.get("INCIDENTS_TABLE", "Incidents")

apigw_client = boto3.client("apigateway", region_name=REGION_NAME)
dynamodb_resource = boto3.resource("dynamodb", region_name=REGION_NAME)
incidents_table = dynamodb_resource.Table(INCIDENTS_TABLE)


def resolve_api_id(resource_name: str) -> str:
    """Resolves the REST API ID from environment or by listing APIs."""
    if TARGET_API_ID:
        return TARGET_API_ID

    try:
        apis = apigw_client.get_rest_apis().get("items", [])
        for api in apis:
            if api.get("name") == resource_name:
                return api["id"]
    except Exception as e:
        logger.error(f"Failed to lookup REST API by name '{resource_name}': {e}")

    return TARGET_API_ID


def check_is_already_throttled(api_id: str, stage_name: str) -> bool:
    """Checks if the stage throttling rate and burst are already 0."""
    try:
        stage = apigw_client.get_stage(restApiId=api_id, stageName=stage_name)
        method_settings = stage.get("methodSettings", {})
        root_settings = method_settings.get("*/*", {})

        rate = root_settings.get("throttlingRateLimit")
        burst = root_settings.get("throttlingBurstLimit")

        logger.info(f"Stage '{stage_name}' current throttle settings: rate={rate}, burst={burst}")
        if rate == 0.0 and burst == 0:
            return True
        return False
    except Exception as e:
        logger.warning(f"Could not read stage '{stage_name}' settings: {e}")
        return False


def apply_stage_throttle(api_id: str, stage_name: str, rate_limit: int = 0, burst_limit: int = 0):
    """Updates the stage throttle settings via apigateway.update_stage."""
    patch_operations = [
        {
            "op": "replace",
            "path": "/*/*/throttling/rateLimit",
            "value": str(rate_limit),
        },
        {
            "op": "replace",
            "path": "/*/*/throttling/burstLimit",
            "value": str(burst_limit),
        },
    ]

    response = apigw_client.update_stage(
        restApiId=api_id,
        stageName=stage_name,
        patchOperations=patch_operations,
    )
    logger.info(f"Applied stage throttle patch to '{stage_name}' on API '{api_id}'.")
    return response


def update_incident_action(incident_id: str, action_taken: str):
    """Updates the action_taken field in DynamoDB Incidents table."""
    if not incident_id:
        return

    try:
        incidents_table.update_item(
            Key={"incident_id": incident_id},
            UpdateExpression="SET action_taken = :act",
            ExpressionAttributeValues={":act": action_taken},
        )
        logger.info(f"Updated incident '{incident_id}' with action_taken='{action_taken}'.")
    except Exception as e:
        logger.warning(f"Failed to update Incidents table for incident '{incident_id}': {e}")


def lambda_handler(event, context):
    """Entry point for Remediator Lambda."""
    # Unwrap payload if event is wrapped in body
    payload = event.get("body", event) if isinstance(event.get("body"), dict) else event
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = event

    incident_id = payload.get("incident_id")
    resource = payload.get("resource", TARGET_API_NAME)
    stage = payload.get("stage", "prod")
    trigger_source = payload.get("trigger_source", "manual")  # "dev_auto", "approval_gate", etc.

    logger.info(f"Remediator invoked for resource='{resource}', stage='{stage}', incident_id='{incident_id}'")

    api_id = resolve_api_id(resource)
    if not api_id:
        err_msg = f"Unable to resolve API ID for resource '{resource}'"
        logger.error(err_msg)
        return {"statusCode": 500, "body": {"error": err_msg}}

    # Idempotency check: if already 0, do not error or re-apply
    if check_is_already_throttled(api_id, stage):
        logger.info(f"Resource '{resource}' stage '{stage}' is ALREADY throttled to 0.")
        update_incident_action(incident_id, "ALREADY_THROTTLED")
        return {
            "statusCode": 200,
            "body": {
                "incident_id": incident_id,
                "resource": resource,
                "stage": stage,
                "status": "ALREADY_THROTTLED",
                "throttled": True,
                "rateLimit": 0,
                "burstLimit": 0,
            },
        }

    # Apply throttle to 0
    apply_stage_throttle(api_id, stage, rate_limit=0, burst_limit=0)

    action_label = "AUTO_THROTTLED" if trigger_source == "dev_auto" else "APPROVED_AND_THROTTLED"
    update_incident_action(incident_id, action_label)

    return {
        "statusCode": 200,
        "body": {
            "incident_id": incident_id,
            "resource": resource,
            "stage": stage,
            "status": "THROTTLED",
            "action_taken": action_label,
            "throttled": True,
            "rateLimit": 0,
            "burstLimit": 0,
        },
    }
