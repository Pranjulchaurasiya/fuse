"""Reasoner Lambda: Enrichment service that evaluates traffic anomaly snapshots
using Amazon Bedrock Converse API with toolConfig for structured JSON output.

This Lambda is invoked ASYNCHRONOUSLY by the Poller as an optional enrichment step.
It does NOT invoke the Remediator — remediation decisions are made deterministically
by the Poller based on statistical analysis.

Persists every evaluation to DynamoDB `Incidents` table as enrichment data.
Implements strict fail-closed fallback: any Bedrock failure defaults to RUNAWAY classification.
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

bedrock_client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
dynamodb_resource = boto3.resource("dynamodb", region_name=AWS_REGION)
incidents_table = dynamodb_resource.Table(INCIDENTS_TABLE_NAME)

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
                            "is_fallback": {
                                "type": "boolean",
                                "description": "True if decision was made via stochastic fail-closed fallback.",
                            },
                            "metrics_synthesis": {
                                "type": "object",
                                "properties": {
                                    "caller_diversity_score": {
                                        "type": "number",
                                        "description": "Calculated unique callers divided by total requests.",
                                    },
                                    "deployment_correlation": {
                                        "type": "boolean",
                                        "description": "True if an active release heartbeat was registered in the T-20min window.",
                                    },
                                },
                                "required": ["caller_diversity_score", "deployment_correlation"],
                            },
                            "explanation": {
                                "type": "string",
                                "description": "A concise, 2-sentence empirical summary of analytical rationale.",
                            },
                        },
                        "required": ["classification", "confidence", "is_fallback", "metrics_synthesis", "explanation"],
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
            "You are the primary cognitive reasoning node for 'Fuse: The Cognitive Circuit Breaker,' "
            "an enterprise-grade cloud financial guardrail. Your specific directive is to evaluate infrastructure "
            "telemetry data to differentiate between high-value legitimate business activity spikes and catastrophic "
            "cloud billing liabilities (such as runaway application loops, recursive LLM token loops, or single-caller application flood attacks).\n\n"
            "OPERATIONAL BRANCHING:\n"
            "- NORMAL: Legitimate user behavior, scheduled flash sales, or distributed volumetric surges. Maintain availability.\n"
            "- RUNAWAY: High caller concentration, infinite code loops, broken retry logic, or single-source scraper spam. Trip circuit.\n\n"
            "CONTEXTUAL FILTERS:\n"
            "A. Caller Diversity: Ratio of unique callers to total requests. Healthy (> 0.05) -> NORMAL. Concentrated (single caller dominating) -> RUNAWAY.\n"
            "B. Deployments: Recent deploy in T-20min window + concentration spike -> strongly indicates code bug loop -> RUNAWAY.\n"
            "C. Scheduled Events: If Active_Event_Window is true, tolerate higher variance provided diversity is healthy.\n\n"
            "STRICT STOCHASTIC FAIL-SAFE:\n"
            "If telemetry is corrupted, incomplete, or missing, default immediately to fail-closed posture: RUNAWAY, is_fallback=true.\n\n"
            "You MUST output your analysis exclusively by executing the tool call to 'classify_anomaly'."
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
                "is_fallback": bool(tool_input.get("is_fallback", False)),
                "metrics_synthesis": tool_input.get("metrics_synthesis", {}),
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
    metrics_synthesis: dict = None,
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

    if metrics_synthesis:
        item["metrics_synthesis"] = {
            "caller_diversity_score": Decimal(str(round(float(metrics_synthesis.get("caller_diversity_score", 0.0)), 4))),
            "deployment_correlation": bool(metrics_synthesis.get("deployment_correlation", False)),
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
        metrics_synthesis = result.get("metrics_synthesis", {})
        raw_bedrock_response = result["raw_tool_input"]
        logger.info(f"Bedrock reasoning result: classification={classification}, confidence={confidence}")
    except Exception as e:
        logger.error(f"Bedrock invocation failed, triggering fail-closed fallback: {e}", exc_info=True)
        is_fallback = True
        classification = "RUNAWAY"
        confidence = 0.0
        metrics_synthesis = {"caller_diversity_score": 0.0, "deployment_correlation": False}
        explanation = f"FAIL-CLOSED FALLBACK: Bedrock reasoning failed ({type(e).__name__}: {str(e)}). Defaulted to RUNAWAY for cost safety."
        raw_bedrock_response = {"fallback_error": str(e), "error_type": type(e).__name__}

    # Enrichment-only: no remediation action taken by Reasoner.
    # Remediation is handled deterministically by the Poller.
    # The Reasoner only provides Bedrock classification for dashboard display.
    action_taken = "ENRICHMENT_ONLY"
    
    # If this was invoked for an existing incident, enrich it in-place
    existing_incident_id = payload.get("incident_id")
    if existing_incident_id:
        incident_id = existing_incident_id
        try:
            update_expr = "SET bedrock_explanation = :expl, confidence = :conf, bedrock_model_used = :model, is_fallback = :fb, enriched_at = :eat, classification = :cls"
            expr_vals = {
                ":expl": explanation,
                ":conf": Decimal(str(round(confidence, 2))),
                ":model": model_id,
                ":fb": is_fallback,
                ":eat": now_epoch,
                ":cls": classification,
            }
            if metrics_synthesis:
                update_expr += ", metrics_synthesis = :ms"
                expr_vals[":ms"] = {
                    "caller_diversity_score": Decimal(str(round(float(metrics_synthesis.get("caller_diversity_score", 0.0)), 4))),
                    "deployment_correlation": bool(metrics_synthesis.get("deployment_correlation", False)),
                }
            incidents_table.update_item(
                Key={"incident_id": incident_id},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_vals,
            )
            action_taken = "ENRICHMENT_APPLIED"
            logger.info(f"Enriched existing incident {incident_id} with Bedrock classification.")
        except Exception as enrich_err:
            logger.warning(f"Failed to enrich incident {incident_id}: {enrich_err}")
            action_taken = "ENRICHMENT_FAILED"
    else:
        # Persist new incident record to Incidents table
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
            metrics_synthesis=metrics_synthesis,
        )

    response_body = {
        "incident_id": incident_id,
        "timestamp": now_epoch,
        "resource": resource,
        "environment": environment,
        "classification": classification,
        "confidence": confidence,
        "explanation": explanation,
        "metrics_synthesis": metrics_synthesis,
        "action_taken": action_taken,
        "is_fallback": is_fallback,
        "bedrock_model_used": model_id,
        "raw_bedrock_response": raw_bedrock_response,
    }

    return {
        "statusCode": 200,
        "body": response_body,
    }
