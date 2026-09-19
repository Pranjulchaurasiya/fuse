# Fuse — Developer Quickstart & 1-Click Deployment Guide

> Deploy an autonomous, context-aware circuit breaker to your AWS account in under 90 seconds.

---

## 01 / Prerequisites

Before deploying Fuse to your AWS account, ensure you have:
1. **AWS CLI** installed and configured (`aws configure`).
2. **Amazon Bedrock Model Access**: Enable access to **Amazon Nova Micro** (`apac.amazon.nova-micro-v1:0`) or **Claude 3.5 Haiku** (`anthropic.claude-3-5-haiku-20241022-v1:0`) in the AWS Bedrock console.
3. An existing **Amazon API Gateway REST API** and stage you want to protect.

---

## 02 / 1-Command Deployment

You can deploy Fuse using either **AWS SAM CLI** or the standard **AWS CLI**:

### Method A: Using AWS SAM CLI (Recommended)
```bash
# 1. Clone the repository
git clone https://github.com/Pranjulchaurasiya/fuse.git
cd fuse

# 2. Build and deploy interactively
sam build
sam deploy --guided
```
During the interactive prompt, provide:
* **Stack Name**: `fuse-guardrail`
* **TargetRestApiId**: Your API Gateway REST API ID (e.g. `a1b2c3d4e5`)
* **TargetStageName**: The stage to monitor (e.g. `prod` or `dev`)
* **BedrockModelId**: Default (`apac.amazon.nova-micro-v1:0` or `anthropic.claude-3-5-haiku-20241022-v1:0`)

---

### Method B: Using Standard AWS CLI (No SAM required)
```bash
# 1. Package code to your S3 bucket
aws cloudformation package \
  --template-file template.yaml \
  --s3-bucket YOUR_DEPLOYMENT_BUCKET \
  --output-template-file packaged.yaml

# 2. Deploy CloudFormation stack
aws cloudformation deploy \
  --template-file packaged.yaml \
  --stack-name fuse-guardrail \
  --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
  --parameter-overrides \
      TargetRestApiId=YOUR_REST_API_ID \
      TargetStageName=prod
```

---

## 03 / What Gets Created in Your Account

| Resource | Service | Purpose |
| :--- | :--- | :--- |
| `fuse-guardrail-Deployments` | Amazon DynamoDB | Tracks release timestamps to prevent false-positive alarms after deploys |
| `fuse-guardrail-Incidents` | Amazon DynamoDB | Incident audit log storing Bedrock classification rationale and metric deltas |
| `fuse-guardrail-ApprovalQueue` | Amazon DynamoDB | Production safety gate holding runaway anomalies pending human approval |
| `fuse-guardrail-poller` | AWS Lambda | Scheduled 1-minute CloudWatch metric scraper |
| `fuse-guardrail-reasoner` | AWS Lambda | Amazon Bedrock Converse single-turn classification engine |
| `fuse-guardrail-remediator` | AWS Lambda | Patches API Gateway stage `rateLimit=0` and `burstLimit=0` |
| `fuse-guardrail-control-api` | Amazon API Gateway | Isolated control plane REST API for incident querying and approvals |
| `fuse-guardrail-poller-schedule` | Amazon EventBridge | 1-minute rate rule triggering the detection pipeline |

---

## 04 / Immediate Verification

Once deployed, verify your stack outputs:
```bash
aws cloudformation describe-stacks \
  --stack-name fuse-guardrail \
  --query "Stacks[0].Outputs" \
  --output table
```

### Test Scenario: Triggering a Test Anomaly
Run the provided runaway client loop against your API:
```bash
python scripts/load_test_runaway.py
```
Within 60 seconds:
1. Query the newly deployed incidents endpoint:
   ```bash
   curl -s https://<ControlApiId>.execute-api.<region>.amazonaws.com/prod/incidents
   ```
2. Approve the circuit trip:
   ```bash
   curl -X POST https://<ControlApiId>.execute-api.<region>.amazonaws.com/prod/incidents/<incident_id>/approve \
     -H "Content-Type: application/json" \
     -d '{"decision": "APPROVED", "resolved_by": "Engineer"}'
   ```
3. Verify your protected API stage now responds with `HTTP 429 Too Many Requests`:
   ```bash
   curl -i https://<YourApiId>.execute-api.<region>.amazonaws.com/prod/items
   ```

---

## 05 / Teardown & Clean Up

To remove all Fuse resources without leaving orphaned cloud assets:
```bash
aws cloudformation delete-stack --stack-name fuse-guardrail
```
