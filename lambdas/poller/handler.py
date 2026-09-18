"""Poller Lambda: Pulls CloudWatch metrics for the protected API Gateway,
checks DynamoDB Deployments heartbeat table, computes rolling baseline,
and logs structured metric deltas.

Adheres strictly to the single-responsibility boundary defined in ARCHITECTURE.md.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
import boto3
from boto3.dynamodb.conditions import Attr

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION_NAME = os.environ.get("AWS_REGION", "ap-south-1")
API_NAME = os.environ.get("API_NAME", "guardrail-demo-api")
STAGE_NAME = os.environ.get("STAGE_NAME", "prod")
DEPLOYMENTS_TABLE = os.environ.get("DEPLOYMENTS_TABLE", "Deployments")
WINDOW_MINUTES = int(os.environ.get("WINDOW_MINUTES", "15"))

cw_client = boto3.client("cloudwatch", region_name=REGION_NAME)
ddb_client = boto3.resource("dynamodb", region_name=REGION_NAME)
deployments_table = ddb_client.Table(DEPLOYMENTS_TABLE)


def check_deploy_heartbeat(resource_name: str, window_seconds: int = 900):
    """Check if a deployment heartbeat was registered within the last window_seconds (default 15m)."""
    now_epoch = int(time.time())
    cutoff_epoch = now_epoch - window_seconds

    try:
        response = deployments_table.scan(
            FilterExpression=Attr("resource").eq(resource_name) & Attr("timestamp").gte(cutoff_epoch)
        )
        items = response.get("Items", [])
        if items:
            # Sort by timestamp descending to get the freshest deploy
            items.sort(key=lambda x: int(x.get("timestamp", 0)), reverse=True)
            latest = items[0]
            logger.info(f"Recent deploy detected for {resource_name}: {latest}")
            return True, latest.get("note", "No note provided"), latest.get("deployment_id")
        return False, None, None
    except Exception as e:
        logger.error(f"Error checking Deployments table: {e}", exc_info=True)
        return False, None, None


def get_api_metric_data(api_name: str, stage_name: str, window_minutes: int = 15):
    """Query CloudWatch for 1-minute Count sums over the past window_minutes."""
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(minutes=window_minutes)

    metric_query = {
        "Id": "m1",
        "MetricStat": {
            "Metric": {
                "Namespace": "AWS/ApiGateway",
                "MetricName": "Count",
                "Dimensions": [
                    {"Name": "ApiName", "Value": api_name},
                    {"Name": "Stage", "Value": stage_name},
                ],
            },
            "Period": 60,
            "Stat": "Sum",
        },
        "ReturnData": True,
    }

    try:
        response = cw_client.get_metric_data(
            MetricDataQueries=[metric_query],
            StartTime=start_time,
            EndTime=now,
            ScanBy="TimestampDescending",
        )
        results = response.get("MetricDataResults", [])
        if not results:
            return [], []

        timestamps = results[0].get("Timestamps", [])
        values = results[0].get("Values", [])
        return timestamps, values
    except Exception as e:
        logger.error(f"Error fetching CloudWatch metric data: {e}", exc_info=True)
        return [], []


def compute_baseline_and_delta(values: list):
    """Computes current 1-min count, rolling baseline from historical buckets, and delta.
    Values are expected in descending timestamp order (index 0 is latest).
    """
    if not values:
        return 0, 0.0, 0.0, 0

    total_requests = int(sum(values))
    current_count = int(values[0])

    # Historical values are buckets prior to the current 1-minute bucket
    history = values[1:]
    if history:
        baseline = round(float(sum(history)) / len(history), 2)
    else:
        baseline = 0.0

    delta = round(float(current_count - baseline), 2)
    return current_count, baseline, delta, total_requests


def lambda_handler(event, context):
    """Entry point for EventBridge schedule or manual test trigger."""
    now_epoch = int(time.time())
    logger.info(f"Poller execution started for {API_NAME} [{STAGE_NAME}] at epoch {now_epoch}")

    # 1. Pull CloudWatch metrics
    timestamps, values = get_api_metric_data(API_NAME, STAGE_NAME, WINDOW_MINUTES)
    current_count, baseline, delta, total_requests = compute_baseline_and_delta(values)

    # 2. Check Deployments heartbeat table
    recent_deploy, deploy_note, deployment_id = check_deploy_heartbeat(API_NAME, window_seconds=WINDOW_MINUTES * 60)

    # 3. Construct structured metric snapshot payload
    payload = {
        "timestamp": now_epoch,
        "resource": API_NAME,
        "stage": STAGE_NAME,
        "current_count_per_min": current_count,
        "baseline_count_per_min": baseline,
        "delta": delta,
        "total_requests_in_window": total_requests,
        "recent_deploy": recent_deploy,
        "deploy_note": deploy_note,
        "deployment_id": deployment_id,
        "data_points_count": len(values),
    }

    # 4. Structured log for monitoring
    logger.info(f"POLLER_CYCLE_RESULT: {json.dumps(payload)}")

    return {
        "statusCode": 200,
        "body": payload,
    }
