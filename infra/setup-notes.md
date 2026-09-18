# infra/setup-notes.md — Setup Notes & Manual / CLI Commands

Target Region: `ap-south-1` (Mumbai) — locked across all services.

### Active Demo Resources (Deployed):
- **API Gateway ID**: `poim5xmgs2`
- **Invoke URL**: `https://poim5xmgs2.execute-api.ap-south-1.amazonaws.com/prod`
- **Backing Lambda**: `guardrail-demo-target` (`arn:aws:lambda:ap-south-1:515903395012:function:guardrail-demo-target`)
- **DynamoDB Tables**: `Deployments`, `Incidents`, `ApprovalQueue`
- **Poller Lambda**: `guardrail-poller` (`arn:aws:lambda:ap-south-1:515903395012:function:guardrail-poller`)
- **Reasoner Lambda**: `guardrail-reasoner` (`arn:aws:lambda:ap-south-1:515903395012:function:guardrail-reasoner`)
- **EventBridge Rule**: `guardrail-poller-schedule` (`rate(1 minute)`)

---

## 1. DynamoDB Tables Setup

All tables use `PAY_PER_REQUEST` (on-demand capacity).

### A. `Deployments`
```bash
aws dynamodb create-table \
  --table-name Deployments \
  --attribute-definitions AttributeName=deployment_id,AttributeType=S \
  --key-schema AttributeName=deployment_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region ap-south-1
```

### B. `Incidents`
```bash
aws dynamodb create-table \
  --table-name Incidents \
  --attribute-definitions \
      AttributeName=incident_id,AttributeType=S \
      AttributeName=environment,AttributeType=S \
      AttributeName=timestamp,AttributeType=N \
  --key-schema AttributeName=incident_id,KeyType=HASH \
  --global-secondary-indexes '[
    {
      "IndexName": "environment-timestamp-index",
      "KeySchema": [
        {"AttributeName": "environment", "KeyType": "HASH"},
        {"AttributeName": "timestamp", "KeyType": "RANGE"}
      ],
      "Projection": {
        "ProjectionType": "ALL"
      }
    }
  ]' \
  --billing-mode PAY_PER_REQUEST \
  --region ap-south-1
```

### C. `ApprovalQueue`
```bash
aws dynamodb create-table \
  --table-name ApprovalQueue \
  --attribute-definitions AttributeName=approval_id,AttributeType=S \
  --key-schema AttributeName=approval_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region ap-south-1
```

*(Alternatively, run `python scripts/setup_dynamodb.py` to create and wait for all three tables).*

---

## 2. Demo API Gateway + Trivial Backing Lambda

This creates the mock workload that is monitored for runaway cost spikes and throttled during remediation.

### Step 2.1: IAM Role for Backing Lambda
```bash
# Trust policy
cat << 'EOF' > /tmp/lambda-trust-policy.json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "lambda.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name guardrail-demo-target-role \
  --assume-role-policy-document file:///tmp/lambda-trust-policy.json

# Attach basic execution policy
aws iam attach-role-policy \
  --role-name guardrail-demo-target-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

### Step 2.2: Package & Deploy Demo Backing Lambda
```bash
# Zip handler
cd lambdas/demo_api && zip -q function.zip handler.py && cd ../..

# Get Account ID and create Lambda
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws lambda create-function \
  --function-name guardrail-demo-target \
  --runtime python3.12 \
  --role arn:aws:iam::${ACCOUNT_ID}:role/guardrail-demo-target-role \
  --handler handler.lambda_handler \
  --zip-file fileb://lambdas/demo_api/function.zip \
  --timeout 10 \
  --memory-size 128 \
  --region ap-south-1
```

### Step 2.3: Create REST API Gateway & Proxy Route
```bash
# 1. Create REST API
API_ID=$(aws apigateway create-rest-api \
  --name "guardrail-demo-api" \
  --description "Protected demo API for AWS Cost Guardrail" \
  --endpoint-configuration types=REGIONAL \
  --region ap-south-1 \
  --query id --output text)

# 2. Get Root Resource ID
ROOT_ID=$(aws apigateway get-resources \
  --rest-api-id ${API_ID} \
  --region ap-south-1 \
  --query 'items[?path==`/`].id' --output text)

# 3. Create /{proxy+} Resource
PROXY_ID=$(aws apigateway create-resource \
  --rest-api-id ${API_ID} \
  --parent-id ${ROOT_ID} \
  --path-part '{proxy+}' \
  --region ap-south-1 \
  --query id --output text)

# 4. Create ANY method on /{proxy+}
aws apigateway put-method \
  --rest-api-id ${API_ID} \
  --resource-id ${PROXY_ID} \
  --http-method ANY \
  --authorization-type NONE \
  --region ap-south-1

# 5. Integrate /{proxy+} ANY method with Demo Lambda (AWS_PROXY)
LAMBDA_ARN=$(aws lambda get-function --function-name guardrail-demo-target --region ap-south-1 --query Configuration.FunctionArn --output text)

aws apigateway put-integration \
  --rest-api-id ${API_ID} \
  --resource-id ${PROXY_ID} \
  --http-method ANY \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri "arn:aws:apigateway:ap-south-1:lambda:path/2015-03-31/functions/${LAMBDA_ARN}/invocations" \
  --region ap-south-1

# 6. Also create ANY method and integration on root (/)
aws apigateway put-method \
  --rest-api-id ${API_ID} \
  --resource-id ${ROOT_ID} \
  --http-method ANY \
  --authorization-type NONE \
  --region ap-south-1

aws apigateway put-integration \
  --rest-api-id ${API_ID} \
  --resource-id ${ROOT_ID} \
  --http-method ANY \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri "arn:aws:apigateway:ap-south-1:lambda:path/2015-03-31/functions/${LAMBDA_ARN}/invocations" \
  --region ap-south-1

# 7. Grant API Gateway permission to invoke the Lambda
aws lambda add-permission \
  --function-name guardrail-demo-target \
  --statement-id apigateway-demo-invoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:ap-south-1:${ACCOUNT_ID}:${API_ID}/*/*" \
  --region ap-south-1

# 8. Deploy to 'prod' stage
aws apigateway create-deployment \
  --rest-api-id ${API_ID} \
  --stage-name prod \
  --region ap-south-1

# 9. Set baseline throttle (RateLimit: 1000, BurstLimit: 2000)
aws apigateway update-stage \
  --rest-api-id ${API_ID} \
  --stage-name prod \
  --patch-operations \
      op=replace,path=/*/*/throttling/rateLimit,value=1000 \
      op=replace,path=/*/*/throttling/burstLimit,value=2000 \
  --region ap-south-1
```

*(Alternatively, run `python scripts/setup_demo_api.py` to automate all of Step 2)*.

---

### AWS Console Steps (Alternative to CLI)

1. **Lambda Console**:
   - Go to **AWS Lambda** > **Create function**.
   - Function name: `guardrail-demo-target`, Runtime: `Python 3.12`, Architecture: `x86_64`.
   - Paste code from [lambdas/demo_api/handler.py](file:///c:/Users/pranj/Documents/Fuse/lambdas/demo_api/handler.py) and click **Deploy**.
2. **API Gateway Console**:
   - Go to **API Gateway** > **Create API** > **REST API** (Build).
   - API name: `guardrail-demo-api`, Endpoint Type: `Regional`.
   - Under **Resources**, click **Create Resource**: Resource Path: `{proxy+}`. Check **Configure as proxy resource**.
   - Integration type: **Lambda function**, enable **Lambda Proxy integration**, select Lambda function `guardrail-demo-target`.
   - Click **Deploy API**, Stage name: `prod`.
   - Under Stage `prod` > **Settings** > **Default Method Throttling**, set Rate: `1000`, Burst: `2000`. Save changes.

---

## 3. Deploy Heartbeat Script

Run as the final step of a deployment:
```bash
python scripts/deploy_heartbeat.py --resource guardrail-demo-api --note "v1.0.0 initial deploy"
```

---

## 4. Poller Lambda & EventBridge 1-Minute Schedule

Monitors API Gateway `Count` metric, checks `Deployments` heartbeat, and computes traffic baseline.

### Automated Setup:
```bash
python scripts/setup_poller.py
```

### Manual / CLI Steps:
```bash
# 1. Create IAM Role with poller-role.json and basic execution
aws iam create-role \
  --role-name guardrail-poller-role \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'

aws iam attach-role-policy \
  --role-name guardrail-poller-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam put-role-policy \
  --role-name guardrail-poller-role \
  --policy-name guardrail-poller-permissions \
  --policy-document file://infra/iam-policies/poller-role.json

# 2. Package and Create Lambda
cd lambdas/poller && zip -q function.zip handler.py && cd ../..

aws lambda create-function \
  --function-name guardrail-poller \
  --runtime python3.12 \
  --role arn:aws:iam::${ACCOUNT_ID}:role/guardrail-poller-role \
  --handler handler.lambda_handler \
  --zip-file fileb://lambdas/poller/function.zip \
  --timeout 15 \
  --memory-size 128 \
  --environment 'Variables={API_NAME=guardrail-demo-api,STAGE_NAME=prod,DEPLOYMENTS_TABLE=Deployments,WINDOW_MINUTES=15}' \
  --region ap-south-1

# 3. Create EventBridge Rule (1-minute rate)
aws events put-rule \
  --name guardrail-poller-schedule \
  --schedule-expression "rate(1 minute)" \
  --state ENABLED \
  --region ap-south-1

# 4. Wire Target and Add Permission
aws lambda add-permission \
  --function-name guardrail-poller \
  --statement-id eventbridge-guardrail-poller-schedule \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:ap-south-1:${ACCOUNT_ID}:rule/guardrail-poller-schedule \
  --region ap-south-1

aws events put-targets \
  --rule guardrail-poller-schedule \
  --targets "Id"="1","Arn"="arn:aws:lambda:ap-south-1:${ACCOUNT_ID}:function:guardrail-poller" \
  --region ap-south-1
```

---

## 5. Reasoner Lambda (Bedrock Converse & Incidents Persistence)

Classifies traffic anomaly snapshots using Amazon Bedrock Converse API (`toolConfig`), enforcing deterministic JSON classification (`NORMAL` vs `RUNAWAY`), confidence, and explanation. Persists every cycle's outcome to DynamoDB `Incidents`.

### Automated Setup:
```bash
python scripts/setup_reasoner.py
```

### Verification & Fallback Testing:
```bash
python scripts/test_reasoner.py
```
