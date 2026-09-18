"""Get Incidents Lambda: Serves incident log JSON for the dashboard.

Contract (API.md):
GET /incidents
Response 200:
{
  "incidents": [
    {
      "incident_id": "string",
      "timestamp": 1758100000,
      "resource": "guardrail-demo-api",
      "classification": "RUNAWAY",
      "bedrock_explanation": "string",
      "action_taken": "PENDING_APPROVAL",
      "environment": "prod"
    }
  ]
}
"""

import json
import logging
import os
from decimal import Decimal
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION_NAME = os.environ.get("AWS_REGION", "ap-south-1")
INCIDENTS_TABLE = os.environ.get("INCIDENTS_TABLE", "Incidents")

dynamodb_resource = boto3.resource("dynamodb", region_name=REGION_NAME)
table = dynamodb_resource.Table(INCIDENTS_TABLE)

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key",
}


def serialize_item(obj):
    """Recursively converts Decimal objects to int or float for JSON serialization."""
    if isinstance(obj, list):
        return [serialize_item(x) for x in obj]
    elif isinstance(obj, dict):
        return {k: serialize_item(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj


def lambda_handler(event, context):
    logger.info(f"Get incidents invoked: {json.dumps(event)}")

    # 1. Handle CORS pre-flight
    if event.get("httpMethod") == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps({"status": "ok"}),
        }

    try:
        response = table.scan(Limit=100)
        items = response.get("Items", [])

        # Sort by timestamp descending
        items.sort(key=lambda x: int(x.get("timestamp", 0)), reverse=True)

        formatted_incidents = []
        for it in items:
            formatted_incidents.append({
                "incident_id": it.get("incident_id"),
                "timestamp": int(it.get("timestamp", 0)),
                "resource": it.get("resource", "guardrail-demo-api"),
                "environment": it.get("environment", "prod"),
                "classification": it.get("classification", "UNKNOWN"),
                "confidence": float(it.get("confidence", 0.0)) if it.get("confidence") else None,
                "bedrock_explanation": it.get("bedrock_explanation", ""),
                "action_taken": it.get("action_taken", "NONE"),
                "metric_snapshot": serialize_item(it.get("metric_snapshot", {})),
                "deploy_context": serialize_item(it.get("deploy_context", {})),
            })

        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps({"incidents": formatted_incidents}),
        }
    except Exception as e:
        logger.error(f"Failed to scan Incidents table: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": "Failed to fetch incidents", "details": str(e)}),
        }
