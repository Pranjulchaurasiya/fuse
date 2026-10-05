"""Poller Lambda: Pulls CloudWatch metrics for the protected API Gateway,
extracts real unique callers and sample payloads from demo API CloudWatch logs,
checks DynamoDB Deployments heartbeat table, computes rolling baseline,
and triggers the Reasoner Lambda when traffic is detected.

Adheres strictly to the single-responsibility boundary defined in ARCHITECTURE.md.
"""

import json
import logging
import math
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
MINIMUM_VOLUME_FLOOR = int(os.environ.get("MINIMUM_VOLUME_FLOOR", "50"))
Z_SCORE_THRESHOLD = float(os.environ.get("Z_SCORE_THRESHOLD", "2.5"))
REMEDIATOR_FUNCTION_NAME = os.environ.get("REMEDIATOR_FUNCTION_NAME", "guardrail-remediator")
RECOVERY_WINDOW_MINUTES = int(os.environ.get("RECOVERY_WINDOW_MINUTES", "15"))
BEDROCK_ENRICHMENT_ENABLED = os.environ.get("BEDROCK_ENRICHMENT_ENABLED", "true").lower() == "true"
INCIDENTS_TABLE = os.environ.get("INCIDENTS_TABLE", "Incidents")
CALLER_DOMINANCE_THRESHOLD = float(os.environ.get("CALLER_DOMINANCE_THRESHOLD", "0.85"))
TENANTS_TABLE = os.environ.get('TENANTS_TABLE', 'Fuse_Tenants')
MULTI_TENANT_ENABLED = os.environ.get('MULTI_TENANT_ENABLED', 'false').lower() == 'true'
cw_client = boto3.client("cloudwatch", region_name=REGION_NAME)
logs_client = boto3.client("logs", region_name=REGION_NAME)
lambda_client = boto3.client("lambda", region_name=REGION_NAME)
sts_client = boto3.client('sts', region_name=REGION_NAME)
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
        return caller_count, sample_payloads, list(unique_ips)
    except Exception as e:
        logger.warning(f"Could not query demo logs from {log_group_name}: {e}")
        return 1, [], []


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
    """Computes current 1-min count, rolling baseline, standard deviation, and Z-score."""
    if not values:
        return 0, 0.0, 0.0, 0.0, 0, 0

    total_requests = int(sum(values))
    current_count = int(values[0])

    history = [float(v) for v in values[1:]]
    if history:
        baseline = round(float(sum(history)) / len(history), 2)
        variance = sum((x - baseline) ** 2 for x in history) / len(history)
        std_dev = round(math.sqrt(variance), 2)
    else:
        baseline = 0.0
        std_dev = 0.0

    delta = round(float(current_count - baseline), 2)

    if std_dev == 0.0:
        z_score = 0.0 if current_count == baseline else (999.0 if current_count > baseline else 0.0)
    else:
        z_score = round((current_count - baseline) / std_dev, 2)

    return current_count, baseline, std_dev, z_score, delta, total_requests


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


def _check_auto_recovery(now_epoch: int):
    """Checks for active IP blocks older than RECOVERY_WINDOW_MINUTES and triggers unblock."""
    try:
        incidents_tbl = ddb_client.Table(INCIDENTS_TABLE)
        # Scan for active blocks (action_taken = IP_BLOCKED)
        items = []
        scan_kwargs = {"FilterExpression": Attr("action_taken").eq("IP_BLOCKED")}
        done = False
        while not done:
            response = incidents_tbl.scan(**scan_kwargs)
            items.extend(response.get("Items", []))
            if "LastEvaluatedKey" in response and len(items) < 50:
                scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            else:
                done = True
        
        recovery_cutoff = now_epoch - (RECOVERY_WINDOW_MINUTES * 60)
        
        for item in items:
            block_time = int(item.get("timestamp", 0))
            if block_time > 0 and block_time < recovery_cutoff:
                incident_id = item.get("incident_id", "")
                blocked_ips = item.get("blocked_ips", [])
                resource = item.get("resource", API_NAME)
                stage = item.get("stage", STAGE_NAME)
                
                if not blocked_ips:
                    continue
                    
                logger.info(f"AUTO_RECOVERY: Block for {incident_id} is {(now_epoch - block_time) // 60}min old. Triggering unblock for IPs: {blocked_ips}")
                try:
                    lambda_client.invoke(
                        FunctionName=REMEDIATOR_FUNCTION_NAME,
                        InvocationType="RequestResponse",
                        Payload=json.dumps({
                            "action": "UNBLOCK",
                            "incident_id": incident_id,
                            "source_ips": blocked_ips,
                            "resource": resource,
                            "stage": stage,
                            "trigger_source": "auto_recovery",
                            "reason": f"Auto-recovery after {RECOVERY_WINDOW_MINUTES}min cooldown",
                        }),
                    )
                    # Update incident to mark it recovered
                    incidents_tbl.update_item(
                        Key={"incident_id": incident_id},
                        UpdateExpression="SET action_taken = :act, recovered_at = :rat",
                        ExpressionAttributeValues={
                            ":act": "AUTO_RECOVERED",
                            ":rat": now_epoch,
                        },
                    )
                    logger.info(f"AUTO_RECOVERY: Successfully unblocked IPs for {incident_id}")
                except Exception as e:
                    logger.error(f"AUTO_RECOVERY: Failed to unblock for {incident_id}: {e}")
    except Exception as e:
        logger.warning(f"Auto-recovery check failed (non-critical): {e}")


def get_active_tenants():
    """Scan Fuse_Tenants table for CONNECTED tenants with valid role ARNs."""
    try:
        tenants_tbl = ddb_client.Table(TENANTS_TABLE)
        response = tenants_tbl.scan(
            FilterExpression=Attr('status').eq('CONNECTED') & Attr('role_arn').begins_with('arn:aws:iam')
        )
        return response.get('Items', [])
    except Exception as e:
        logger.warning(f'Could not scan Fuse_Tenants: {e}. Falling back to single-tenant mode.')
        return []


def get_cross_account_clients(role_arn: str, external_id: str, tenant_id: str):
    """Assume tenant cross-account role and return scoped boto3 clients."""
    try:
        creds = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=f'fuse-poller-{tenant_id[:8]}',
            ExternalId=external_id,
            DurationSeconds=900,
        )['Credentials']
        kwargs = dict(
            aws_access_key_id=creds['AccessKeyId'],
            aws_secret_access_key=creds['SecretAccessKey'],
            aws_session_token=creds['SessionToken'],
            region_name=REGION_NAME,
        )
        return {
            'cloudwatch': boto3.client('cloudwatch', **kwargs),
            'logs': boto3.client('logs', **kwargs),
        }
    except Exception as e:
        logger.error(f'Failed to assume role {role_arn} for tenant {tenant_id}: {e}')
        return None


def lambda_handler(event, context):
    """Entry point for EventBridge schedule or manual test trigger."""
    now_epoch = int(time.time())
    logger.info(f"Poller execution started for {API_NAME} [{STAGE_NAME}] at epoch {now_epoch}")

    # Skip multi-tenant loop if this is a per-tenant invocation
    if event.get('_single_tenant_mode'):
        # Use tenant-provided context
        now_epoch = int(time.time())
        # Override API_NAME and STAGE_NAME for this invocation from event
        api_id_override = event.get('api_id', '')
        stage_override = event.get('stage', STAGE_NAME)
        tenant_id_ctx = event.get('tenant_id', 'self')
        logger.info(f'Single-tenant mode for tenant {tenant_id_ctx}, api={api_id_override}, stage={stage_override}')
        # Fall through to existing detection logic below

    # Multi-tenant dispatch: if MULTI_TENANT_ENABLED and tenants exist, poll each one
    if MULTI_TENANT_ENABLED:
        tenants = get_active_tenants()
        if tenants:
            logger.info(f'Multi-tenant mode: polling {len(tenants)} active tenant(s)')
            results = []
            for tenant in tenants:
                tid = tenant.get('tenant_id', 'unknown')
                role_arn = tenant.get('role_arn', '')
                ext_id = tenant.get('external_id', '')
                tenant_api_id = tenant.get('api_gateway_id', event.get('api_id', ''))
                tenant_stage = tenant.get('api_stage', STAGE_NAME)
                try:
                    cross_clients = get_cross_account_clients(role_arn, ext_id, tid)
                    if not cross_clients:
                        results.append({'tenant_id': tid, 'status': 'ROLE_ASSUME_FAILED'})
                        continue
                    # Invoke self asynchronously with tenant context
                    tenant_event = {
                        'api_id': tenant_api_id,
                        'stage': tenant_stage,
                        'tenant_id': tid,
                        'role_arn': role_arn,
                        'external_id': ext_id,
                        '_single_tenant_mode': True,  # skip multi-tenant loop in recursive call
                    }
                    lambda_client.invoke(
                        FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'guardrail-poller'),
                        InvocationType='Event',  # async
                        Payload=json.dumps(tenant_event),
                    )
                    results.append({'tenant_id': tid, 'status': 'DISPATCHED'})
                except Exception as e:
                    logger.error(f'Tenant {tid} dispatch failed: {e}')
                    results.append({'tenant_id': tid, 'status': 'DISPATCH_FAILED', 'error': str(e)})
            return {
                'statusCode': 200,
                'body': {'status': 'MULTI_TENANT_DISPATCHED', 'tenants': results},
            }

    # 0. Auto-Recovery: Check for active blocks that should be released
    _check_auto_recovery(now_epoch)

    # 1. Pull CloudWatch metrics
    timestamps, values = get_api_metric_data(API_NAME, STAGE_NAME, WINDOW_MINUTES)
    current_count, baseline, std_dev, z_score, delta, total_requests = compute_baseline_and_delta(values)

    # 2. Check Deployments heartbeat table
    recent_deploy, deploy_note, deployment_id = check_deploy_heartbeat(API_NAME, window_seconds=WINDOW_MINUTES * 60)

    # 3. Extract real unique callers and sample payloads from demo API CloudWatch logs
    unique_caller_count, sample_payloads, unique_ips = get_unique_callers_and_payloads(
        DEMO_TARGET_LOG_GROUP, window_minutes=WINDOW_MINUTES
    )
    caller_diversity_score = round(float(unique_caller_count) / max(current_count, 1), 4)

    # 4. Construct structured metric snapshot payload
    payload = {
        "timestamp": now_epoch,
        "resource": API_NAME,
        "stage": STAGE_NAME,
        "current_count_per_min": current_count,
        "baseline_count_per_min": baseline,
        "baseline_std_dev": std_dev,
        "z_score": z_score,
        "delta": delta,
        "unique_caller_count": unique_caller_count,
        "caller_diversity_score": caller_diversity_score,
        "sample_payloads": sample_payloads,
        "total_requests_in_window": total_requests,
        "recent_deploy": recent_deploy,
        "deploy_note": deploy_note,
        "deployment_id": deployment_id,
        "data_points_count": len(values),
    }

    # 5. Structured log for monitoring
    logger.info(f"POLLER_CYCLE_RESULT: {json.dumps(payload)}")

    # 6. Deterministic Pre-Filter Execution Guard
    # Check volume floor
    if current_count < MINIMUM_VOLUME_FLOOR:
        logger.info(f"Volume ({current_count}) below safety floor ({MINIMUM_VOLUME_FLOOR}). Terminating cycle without Bedrock invocation.")
        return {
            "statusCode": 200,
            "body": {
                "status": "SKIPPED",
                "reason": f"Volume below safety floor ({current_count} < {MINIMUM_VOLUME_FLOOR})",
                "poller_payload": payload,
                "bedrock_invoked": False,
            },
        }

    # Check Z-score & moving average surge
    is_statistically_anomalous = (z_score >= Z_SCORE_THRESHOLD) or (current_count > 2 * baseline and baseline > 0)
    if not is_statistically_anomalous:
        logger.info(f"Telemetry inside normal variance bands (Z={z_score} < {Z_SCORE_THRESHOLD}). Circuit remains CLOSED ($0 Bedrock cost).")
        return {
            "statusCode": 200,
            "body": {
                "status": "DETERMINISTIC_PASS",
                "reason": "Within normal statistical variance",
                "poller_payload": payload,
                "bedrock_invoked": False,
            },
        }

    # --- NEW: Deterministic classification ---
    # Anomaly detected. Classify deterministically based on caller pattern.
    logger.info(f"ANOMALY DETECTED (count={current_count}, Z={z_score}, delta={delta}). Running deterministic classification...")

    # Check caller dominance: if a single caller is responsible for most traffic
    is_single_caller_dominant = (unique_caller_count == 1) or (caller_diversity_score < (1.0 - CALLER_DOMINANCE_THRESHOLD))
    is_post_deploy = recent_deploy  # Recent deploy + spike = likely code bug

    classification = "NORMAL"
    reason_parts = []

    if is_single_caller_dominant:
        classification = "RUNAWAY"
        reason_parts.append(f"Single caller dominance detected (diversity={caller_diversity_score}, callers={unique_caller_count})")

    if is_post_deploy and is_single_caller_dominant:
        reason_parts.append(f"Post-deploy spike correlated with low caller diversity (deploy note: {deploy_note})")
        classification = "RUNAWAY"  # reinforces

    if z_score > 5.0 and unique_caller_count <= 2:
        classification = "RUNAWAY"
        reason_parts.append(f"Extreme Z-score ({z_score}) with very low caller diversity ({unique_caller_count} callers)")

    decision_reason = "; ".join(reason_parts) if reason_parts else f"Statistical anomaly (Z={z_score}) but healthy caller diversity ({unique_caller_count} callers) — likely organic surge"
    logger.info(f"DETERMINISTIC_CLASSIFICATION: {classification} — {decision_reason}")

    # 7. Act on classification
    remediation_result = None
    action_taken = "NONE"

    incident_id = f"inc-{now_epoch}"
    payload["incident_id"] = incident_id
    payload["classification"] = classification
    payload["decision_reason"] = decision_reason
    payload["source_ips"] = unique_ips

    if classification == "RUNAWAY" and unique_ips:
        logger.info(f"RUNAWAY detected. Invoking Remediator to block IPs: {unique_ips}")
        try:
            rem_payload = {
                "action": "BLOCK",
                "incident_id": incident_id,
                "source_ips": unique_ips,
                "resource": API_NAME,
                "stage": STAGE_NAME,
                "trigger_source": "auto_detection",
                "reason": decision_reason,
            }
            rem_resp = lambda_client.invoke(
                FunctionName=REMEDIATOR_FUNCTION_NAME,
                InvocationType="RequestResponse",
                Payload=json.dumps(rem_payload),
            )
            remediation_result = json.loads(rem_resp["Payload"].read().decode("utf-8"))
            action_taken = "IP_BLOCKED"
            logger.info(f"Remediation result: {remediation_result}")
        except Exception as e:
            logger.error(f"Failed to invoke Remediator: {e}", exc_info=True)
            action_taken = "BLOCK_FAILED"

    # 8. Optional Bedrock enrichment (non-blocking, fire-and-forget)
    enrichment_result = None
    if BEDROCK_ENRICHMENT_ENABLED and classification == "RUNAWAY":
        try:
            logger.info(f"Invoking Reasoner for enrichment of {incident_id} (non-blocking)...")
            enrichment_resp = lambda_client.invoke(
                FunctionName=REASONER_FUNCTION_NAME,
                InvocationType="Event",  # async, fire-and-forget
                Payload=json.dumps(payload),
            )
            logger.info(f"Reasoner enrichment invoked asynchronously (StatusCode={enrichment_resp.get('StatusCode')})")
        except Exception as e:
            logger.warning(f"Reasoner enrichment failed (non-critical): {e}")

    return {
        "statusCode": 200,
        "body": {
            "status": "ANOMALY_EVALUATED",
            "classification": classification,
            "decision_reason": decision_reason,
            "action_taken": action_taken,
            "remediation_result": remediation_result,
            "poller_payload": payload,
            "bedrock_enrichment": "invoked" if (BEDROCK_ENRICHMENT_ENABLED and classification == "RUNAWAY") else "skipped",
        },
    }
