"""Reasoner Lambda: Evaluates traffic anomaly snapshots using Amazon Bedrock Converse API
with toolConfig for deterministic structured JSON output (classification, confidence, explanation).

Persists every evaluation to DynamoDB `Incidents` table.
Implements strict fail-closed fallback: any Bedrock failure defaults to RUNAWAY.
"""

import json
import logging
import os
import time
import uuid
from decimal import Decimal
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "ap-south-1")
DEFAULT_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "apac.amazon.nova-micro-v1:0")
INCIDENTS_TABLE_NAME = os.environ.get("INCIDENTS_TABLE", "Incidents")
DEPLOYMENTS_TABLE_NAME = os.environ.get("DEPLOYMENTS_TABLE", "Deployments")
APPROVAL_QUEUE_TABLE_NAME = os.environ.get("APPROVAL_QUEUE_TABLE", "ApprovalQueue")
REMEDIATOR_FUNCTION_NAME = os.environ.get("REMEDIATOR_FUNCTION_NAME", "guardrail-remediator")

bedrock_client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
dynamodb_resource = boto3.resource("dynamodb", region_name=AWS_REGION)
lambda_client = boto3.client("lambda", region_name=AWS_REGION)
incidents_table = dynamodb_resource.Table(INCIDENTS_TABLE_NAME)
approval_queue_table = dynamodb_resource.Table(APPROVAL_QUEUE_TABLE_NAME)

CLASSIFY_TOOL_SPEC = {
    "tools": [
        {
            "toolSpec": {
                "name": "classify_anomaly",
                "description": "Classifies whether an observed API traffic spike is NORMAL or RUNAWAY.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "classification": {
                                "type": "string",
                                "enum": ["NORMAL", "RUNAWAY"],
                                "description": (
                                    "NORMAL for organic traffic surges (many callers, recent deploy/event). "
                                    "RUNAWAY for loops, buggy clients, stuck retries, repeated payloads."
                                ),
                            },
                            "confidence": {
                                "type": "number",
                                "description": "Confidence score from 0.0 to 1.0.",
                            },
                            "explanation": {
                                "type": "string",
                                "description": "One concise paragraph explaining the technical reasoning for this classification.",
                            },
                        },
                        "required": ["classification", "confidence", "explanation"],
                    }
                },
            }
        }
    ],
    "toolChoice": {"tool": {"name": "classify_anomaly"}},
}

SYSTEM_PROMPT = [
    {
        "text": (
            "You are a cloud cost-anomaly classifier protecting serverless workloads.\n"
            "You will be given metrics and context about a spike in API request volume.\n\n"
            "Decision guidelines:\n"
            "- NORMAL: legitimate traffic growth (e.g., many unique callers, high ratio of unique callers to total requests, diverse request payloads, or matches a recent deploy/marketing event). When unique_caller_count is high and request payloads are varied, classify as NORMAL.\n"
            "- RUNAWAY: a malfunctioning process or agent loop (e.g., single caller or very few callers repeating an identical request/payload at high frequency, no corresponding deploy or traffic-driving event).\n\n"
            "You MUST call the classify_anomaly tool with classification, confidence, and explanation."
        )
    }
]


def invoke_bedrock_classifier(context_payload: dict, model_id: str):
    """Invokes Bedrock Converse API with toolConfig enforcing structured JSON classification."""
    user_message = [
        {
            "role": "user",
            "content": [
                {
                    "text": f"Evaluate this API traffic snapshot for cost anomalies:\n{json.dumps(context_payload, indent=2)}"
                }
            ],
        }
    ]

    response = bedrock_client.converse(
        modelId=model_id,
        system=SYSTEM_PROMPT,
        messages=user_message,
        toolConfig=CLASSIFY_TOOL_SPEC,
    )

    content_list = response.get("output", {}).get("message", {}).get("content", [])
    for content in content_list:
        if "toolUse" in content:
            tool_input = content["toolUse"].get("input", {})
            return {
                "classification": tool_input.get("classification", "RUNAWAY"),
                "confidence": float(tool_input.get("confidence", 0.8)),
                "explanation": tool_input.get("explanation", "Structured tool classification returned without explanation."),
                "raw_tool_input": tool_input,
                "stop_reason": response.get("stopReason"),
            }

    raise ValueError(f"Bedrock responded without toolUse content block: {response}")


def write_incident_record(
    incident_id: str,
    timestamp: int,
    resource: str,
    environment: str,
    metric_snapshot: dict,
    deploy_context: dict,
    classification: str,
    confidence: float,
    explanation: str,
    action_taken: str,
    is_fallback: bool,
    model_used: str,
):
    """Writes evaluation record to DynamoDB Incidents table."""
    clean_snapshot = {
        "count": int(metric_snapshot.get("current_count_per_min", 0)),
        "baseline": Decimal(str(metric_snapshot.get("baseline_count_per_min", 0.0))),
        "delta": Decimal(str(metric_snapshot.get("delta", 0.0))),
        "unique_callers": int(metric_snapshot.get("unique_caller_count", 1)),
        "total_requests": int(metric_snapshot.get("total_requests_in_window", 0)),
    }

    clean_deploy = {
        "recent_deploy": bool(deploy_context.get("recent_deploy", False)),
        "note": str(deploy_context.get("deploy_note") or "None"),
    }

    item = {
        "incident_id": incident_id,
        "timestamp": timestamp,
        "resource": resource,
        "environment": environment,
        "metric_snapshot": clean_snapshot,
        "deploy_context": clean_deploy,
        "classification": classification,
        "confidence": Decimal(str(round(confidence, 2))),
        "bedrock_explanation": explanation,
        "action_taken": action_taken,
        "is_fallback": is_fallback,
        "bedrock_model_used": model_used,
    }

    incidents_table.put_item(Item=item)
    logger.info(f"Successfully recorded incident {incident_id} with action_taken='{action_taken}'.")


def lambda_handler(event, context):
    """Entry point for Reasoner Lambda."""
    now_epoch = int(time.time())
    incident_id = str(uuid.uuid4())

    # Handle event payload directly or unwrapped from Poller body
    payload = event.get("body", event) if isinstance(event.get("body"), dict) else event
    resource = payload.get("resource", "guardrail-demo-api")
    environment = payload.get("stage", payload.get("environment", "prod"))
    model_id = payload.get("model_id") or DEFAULT_MODEL_ID
    force_fail = payload.get("force_fail", False)

    logger.info(f"Reasoner execution started for {resource} [{environment}], model: {model_id}, incident_id: {incident_id}")

    metric_snapshot = {
        "current_count_per_min": payload.get("current_count_per_min", 0),
        "baseline_count_per_min": payload.get("baseline_count_per_min", 0.0),
        "delta": payload.get("delta", 0.0),
        "unique_caller_count": payload.get("unique_caller_count", 1),
        "total_requests_in_window": payload.get("total_requests_in_window", 0),
    }

    deploy_context = {
        "recent_deploy": payload.get("recent_deploy", False),
        "deploy_note": payload.get("deploy_note"),
    }

    context_for_bedrock = {
        **metric_snapshot,
        **deploy_context,
        "sample_payloads": payload.get("sample_payloads", []),
    }

    is_fallback = False
    raw_bedrock_response = None

    try:
        if force_fail:
            raise RuntimeError("Deliberate failure triggered for fallback testing.")

        result = invoke_bedrock_classifier(context_for_bedrock, model_id)
        classification = result["classification"]
        confidence = result["confidence"]
        explanation = result["explanation"]
        raw_bedrock_response = result["raw_tool_input"]
        logger.info(f"Bedrock reasoning result: classification={classification}, confidence={confidence}")
    except Exception as e:
        logger.error(f"Bedrock invocation failed, triggering fail-closed fallback: {e}", exc_info=True)
        is_fallback = True
        classification = "RUNAWAY"
        confidence = 0.0
        explanation = f"FAIL-CLOSED FALLBACK: Bedrock reasoning failed ({type(e).__name__}: {str(e)}). Defaulted to RUNAWAY for cost safety."
        raw_bedrock_response = {"fallback_error": str(e), "error_type": type(e).__name__}

    # Day 3 Remediation Logic:
    # 1. If RUNAWAY:
    #    - dev/staging: auto-throttle via Remediator Lambda
    #    - prod: write to ApprovalQueue, withhold auto-throttle (PENDING_APPROVAL)
    # 2. If NORMAL:
    #    - no remediation action taken (NONE)
    action_taken = "NONE"
    remediation_result = None

    if classification == "RUNAWAY":
        if str(environment).lower() in ["dev", "staging"]:
            logger.info(f"Environment '{environment}' is dev/staging: invoking Remediator directly...")
            try:
                rem_resp = lambda_client.invoke(
                    FunctionName=REMEDIATOR_FUNCTION_NAME,
                    InvocationType="RequestResponse",
                    Payload=json.dumps({
                        "incident_id": incident_id,
                        "resource": resource,
                        "stage": environment,
                        "trigger_source": "dev_auto",
                    }),
                )
                remediation_result = json.loads(rem_resp["Payload"].read().decode("utf-8"))
                action_taken = "AUTO_THROTTLED"
                logger.info(f"Auto-remediation successful: {remediation_result}")
            except Exception as rem_err:
                logger.error(f"Auto-remediation invocation failed: {rem_err}", exc_info=True)
                action_taken = "AUTO_THROTTLE_FAILED"
        else:
            # Prod path: write to ApprovalQueue, withhold action
            logger.info(f"Environment '{environment}' is prod: writing to ApprovalQueue and withholding auto-throttle...")
            try:
                approval_queue_table.put_item(
                    Item={
                        "approval_id": incident_id,
                        "incident_id": incident_id,
                        "status": "PENDING",
                        "created_at": now_epoch,
                        "resolved_at": None,
                        "resolved_by": None,
                        "resource": resource,
                        "stage": environment,
                        "classification": classification,
                        "explanation": explanation,
                    }
                )
                action_taken = "PENDING_APPROVAL"
                logger.info(f"Created PENDING approval entry in ApprovalQueue for {incident_id}.")
            except Exception as q_err:
                logger.error(f"Failed to write to ApprovalQueue: {q_err}", exc_info=True)
                action_taken = "APPROVAL_QUEUE_WRITE_FAILED"

    # Persist every evaluation to Incidents table
    write_incident_record(
        incident_id=incident_id,
        timestamp=now_epoch,
        resource=resource,
        environment=environment,
        metric_snapshot=metric_snapshot,
        deploy_context=deploy_context,
        classification=classification,
        confidence=confidence,
        explanation=explanation,
        action_taken=action_taken,
        is_fallback=is_fallback,
        model_used=model_id,
    )

    response_body = {
        "incident_id": incident_id,
        "timestamp": now_epoch,
        "resource": resource,
        "environment": environment,
        "classification": classification,
        "confidence": confidence,
        "explanation": explanation,
        "action_taken": action_taken,
        "remediation_result": remediation_result,
        "is_fallback": is_fallback,
        "bedrock_model_used": model_id,
        "raw_bedrock_response": raw_bedrock_response,
    }

    return {
        "statusCode": 200,
        "body": response_body,
    }
