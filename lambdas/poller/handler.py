"""Poller Lambda: Pulls CloudWatch metrics for the protected API Gateway,
extracts real unique callers and sample payloads from demo API CloudWatch logs,
checks DynamoDB Deployments heartbeat table, computes rolling baseline,
and triggers the Reasoner Lambda when traffic is detected.

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
DEMO_TARGET_LOG_GROUP = os.environ.get("DEMO_TARGET_LOG_GROUP", "/aws/lambda/guardrail-demo-target")
REASONER_FUNCTION_NAME = os.environ.get("REASONER_FUNCTION_NAME", "guardrail-reasoner")
WINDOW_MINUTES = int(os.environ.get("WINDOW_MINUTES", "15"))

cw_client = boto3.client("cloudwatch", region_name=REGION_NAME)
logs_client = boto3.client("logs", region_name=REGION_NAME)
lambda_client = boto3.client("lambda", region_name=REGION_NAME)
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
            items.sort(key=lambda x: int(x.get("timestamp", 0)), reverse=True)
            latest = items[0]
            logger.info(f"Recent deploy detected for {resource_name}: {latest}")
            return True, latest.get("note", "No note provided"), latest.get("deployment_id")
        return False, None, None
    except Exception as e:
        logger.error(f"Error checking Deployments table: {e}", exc_info=True)
        return False, None, None


def get_unique_callers_and_payloads(log_group_name: str, window_minutes: int = 15):
    """Extracts real unique caller IPs and request payload samples from demo API CloudWatch logs."""
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (window_minutes * 60 * 1000)

    unique_ips = set()
    sample_payloads = []

    try:
        response = logs_client.filter_log_events(
            logGroupName=log_group_name,
            startTime=start_ms,
            filterPattern='DEMO_API_REQUEST',
            limit=100,
        )
        events = response.get("events", [])
        for ev in events:
            msg = ev.get("message", "").strip()
            try:
                # Find start of JSON object in log message
                brace_idx = msg.find("{")
                if brace_idx != -1:
                    data = json.loads(msg[brace_idx:])
                    caller = data.get("caller") or data.get("ip")
                    if caller and caller != "unknown":
                        unique_ips.add(caller)
                    body = data.get("body")
                    if body:
                        str_body = body if isinstance(body, str) else json.dumps(body)
                        if str_body not in sample_payloads and len(sample_payloads) < 5:
                            sample_payloads.append(str_body)
            except Exception:
                continue

        caller_count = max(len(unique_ips), 1) if events else 1
        logger.info(f"Extracted {len(unique_ips)} unique caller IPs and {len(sample_payloads)} payload samples from logs.")
        return caller_count, sample_payloads
    except Exception as e:
        logger.warning(f"Could not query demo logs from {log_group_name}: {e}")
        return 1, []


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
    """Computes current 1-min count, rolling baseline from historical buckets, and delta."""
    if not values:
        return 0, 0.0, 0.0, 0

    total_requests = int(sum(values))
    current_count = int(values[0])

    history = values[1:]
    if history:
        baseline = round(float(sum(history)) / len(history), 2)
    else:
        baseline = 0.0

    delta = round(float(current_count - baseline), 2)
    return current_count, baseline, delta, total_requests


def trigger_reasoner(payload: dict):
    """Invokes the Reasoner Lambda with the evaluated traffic snapshot."""
    try:
        logger.info(f"Invoking Reasoner Lambda '{REASONER_FUNCTION_NAME}' with payload: {payload}")
        resp = lambda_client.invoke(
            FunctionName=REASONER_FUNCTION_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload),
        )
        reasoner_result = json.loads(resp["Payload"].read().decode("utf-8"))
        logger.info(f"REASONER_TRIGGER_RESULT: {json.dumps(reasoner_result)}")
        return reasoner_result
    except Exception as e:
        logger.error(f"Error invoking Reasoner Lambda: {e}", exc_info=True)
        return {"error": str(e)}


def lambda_handler(event, context):
    """Entry point for EventBridge schedule or manual test trigger."""
    now_epoch = int(time.time())
    logger.info(f"Poller execution started for {API_NAME} [{STAGE_NAME}] at epoch {now_epoch}")

    # 1. Pull CloudWatch metrics
    timestamps, values = get_api_metric_data(API_NAME, STAGE_NAME, WINDOW_MINUTES)
    current_count, baseline, delta, total_requests = compute_baseline_and_delta(values)

    # 2. Check Deployments heartbeat table
    recent_deploy, deploy_note, deployment_id = check_deploy_heartbeat(API_NAME, window_seconds=WINDOW_MINUTES * 60)

    # 3. Extract real unique callers and sample payloads from demo API CloudWatch logs
    unique_caller_count, sample_payloads = get_unique_callers_and_payloads(
        DEMO_TARGET_LOG_GROUP, window_minutes=WINDOW_MINUTES
    )

    # 4. Construct structured metric snapshot payload
    payload = {
        "timestamp": now_epoch,
        "resource": API_NAME,
        "stage": STAGE_NAME,
        "current_count_per_min": current_count,
        "baseline_count_per_min": baseline,
        "delta": delta,
        "unique_caller_count": unique_caller_count,
        "sample_payloads": sample_payloads,
        "total_requests_in_window": total_requests,
        "recent_deploy": recent_deploy,
        "deploy_note": deploy_note,
        "deployment_id": deployment_id,
        "data_points_count": len(values),
    }

    # 5. Structured log for monitoring
    logger.info(f"POLLER_CYCLE_RESULT: {json.dumps(payload)}")

    # 6. Wire real Poller output into Reasoner whenever traffic is observed or delta > 0
    reasoner_output = None
    if current_count > 0 or delta > 0:
        logger.info(f"Traffic activity detected (current={current_count}, delta={delta}). Triggering Reasoner...")
        reasoner_output = trigger_reasoner(payload)
    else:
        logger.info("Traffic is at baseline (count=0). Skipping Reasoner invocation for this cycle.")

    return {
        "statusCode": 200,
        "body": {
            "poller_payload": payload,
            "reasoner_output": reasoner_output,
        },
    }
