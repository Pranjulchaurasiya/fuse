import boto3
import json

REGION_NAME = "ap-south-1"
lam = boto3.client("lambda", region_name=REGION_NAME)
apigw = boto3.client("apigateway", region_name=REGION_NAME)
ddb = boto3.resource("dynamodb", region_name=REGION_NAME)

payload = {
    "resource": "guardrail-demo-api",
    "stage": "dev",
    "current_count_per_min": 800,
    "baseline_count_per_min": 5.0,
    "delta": 795.0,
    "unique_caller_count": 1,
    "total_requests_in_window": 2400,
    "recent_deploy": False,
    "deploy_note": None,
    "sample_payloads": ['{"action":"dev_runaway_loop"}'],
}

resp = lam.invoke(
    FunctionName="guardrail-reasoner",
    InvocationType="RequestResponse",
    Payload=json.dumps(payload),
)
body = json.loads(resp["Payload"].read().decode("utf-8")).get("body", {})
print("Reasoner Output:", json.dumps(body, indent=2))
inc_id = body.get("incident_id")

# Check Incidents table
inc_item = ddb.Table("Incidents").get_item(Key={"incident_id": inc_id}).get("Item")
print(f"Incidents Table action_taken: {inc_item.get('action_taken')}")

# Check ApprovalQueue (should NOT have an entry for dev)
q_item = ddb.Table("ApprovalQueue").get_item(Key={"approval_id": inc_id}).get("Item")
print(f"ApprovalQueue Entry Exists (Expected False): {q_item is not None}")

# Check Dev stage throttling on API Gateway
stage = apigw.get_stage(restApiId="poim5xmgs2", stageName="dev")
settings = stage.get("methodSettings", {}).get("*/*", {})
print(f"Dev Stage Throttling Settings: {settings}")

assert inc_item.get("action_taken") == "AUTO_THROTTLED"
assert q_item is None
assert settings.get("throttlingRateLimit") == 0.0
assert settings.get("throttlingBurstLimit") == 0
print("\n[SUCCESS] Dev stage auto-throttling verified end-to-end!")
