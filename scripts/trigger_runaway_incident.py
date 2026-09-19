import boto3
import json

REGION_NAME = "ap-south-1"
lam = boto3.client("lambda", region_name=REGION_NAME)

payload = {
    "resource": "guardrail-demo-api",
    "stage": "prod",
    "current_count_per_min": 40,
    "baseline_count_per_min": 0.0,
    "delta": 40.0,
    "unique_caller_count": 1,
    "total_requests_in_window": 40,
    "recent_deploy": False,
    "deploy_note": None,
    "sample_payloads": [
        '{"action": "retry_failed_job", "job_id": "job-runaway-99120", "error_code": "RESOURCE_BUSY", "retry_loop": true}'
    ],
}

resp = lam.invoke(
    FunctionName="guardrail-reasoner",
    InvocationType="RequestResponse",
    Payload=json.dumps(payload),
)
body = json.loads(resp["Payload"].read().decode("utf-8")).get("body", {})
print(json.dumps(body, indent=2))
