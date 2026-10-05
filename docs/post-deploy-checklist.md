# Fuse Post-Deployment Verification Checklist (Windows / PowerShell)

This checklist provides step-by-step PowerShell-safe verification procedures for the `fuse-sam` stack.
All commands avoid Linux-only syntax (e.g., `cp`) and shell-escaping pitfalls with inline JSON.

---

## 1. Inspect Stack Outputs

Retrieve all CloudFormation outputs from the deployed SAM stack:

```powershell
aws cloudformation describe-stacks --stack-name fuse-sam --query "Stacks[0].Outputs" --output table
```

Extract the primary resource references into PowerShell variables:

```powershell
$CONTROL_API_URL = (aws cloudformation describe-stacks --stack-name fuse-sam --query "Stacks[0].Outputs[?OutputKey=='ControlApiUrl'].OutputValue" --output text)
$API_KEY_ID = (aws cloudformation describe-stacks --stack-name fuse-sam --query "Stacks[0].Outputs[?OutputKey=='ControlApiKeyId'].OutputValue" --output text)

Write-Host "Control API URL: $CONTROL_API_URL"
Write-Host "Control API Key ID: $API_KEY_ID"
```

---

## 2. Verify Reasoner Lambda & Amazon Bedrock Model

Rather than assuming a hardcoded Lambda name, query CloudFormation for the actual physical function name:

```powershell
$REASONER_NAME = (aws cloudformation describe-stack-resource --stack-name fuse-sam --logical-resource-id ReasonerFunction --query "StackResourceDetail.PhysicalResourceId" --output text)
Write-Host "Reasoner Function Physical Name: $REASONER_NAME"
```

Invoke the Reasoner Lambda using the provided test payload file (`scripts/payloads/reasoner_test.json`):

```powershell
aws lambda invoke --function-name $REASONER_NAME --payload fileb://scripts/payloads/reasoner_test.json response.json
```

Display and verify the output:

```powershell
Get-Content response.json | ConvertFrom-Json | Select-Object -ExpandProperty body
```

### Expected Result
* **HTTP Status**: `200`
* **classification**: `"RUNAWAY"`
* **is_fallback**: `false` (confirms live invocation against Bedrock inference profile `apac.amazon.nova-micro-v1:0` succeeded without error)
* **confidence**: `>= 0.90`
* **action_taken**: `"PENDING_APPROVAL"` (safety gate active for `prod` stage)
* **metrics_synthesis**: Object containing `caller_diversity_score` and `deployment_correlation: false`

---

## 3. Verify Control API Security (GET /incidents)

Fetch the secret API key value using the stack's outputted key ID:

```powershell
$API_KEY_VALUE = (aws apigateway get-api-key --api-key $API_KEY_ID --include-value --query "value" --output text)
Write-Host "API Key fetched successfully (length: $($API_KEY_VALUE.Length) chars)"
```

### Test 3A: Request Without API Key (Negative Test)
Run `curl.exe` (do not use PowerShell `curl` alias):

```powershell
curl.exe -i -X GET "$CONTROL_API_URL/incidents"
```

#### Expected Result
* **HTTP Status**: `HTTP/1.1 403 Forbidden`
* **Response Body**: `{"message":"Forbidden"}`

---

### Test 3B: Request With x-api-key Header (Positive Test)

```powershell
curl.exe -i -X GET "$CONTROL_API_URL/incidents" -H "x-api-key: $API_KEY_VALUE"
```

#### Expected Result
* **HTTP Status**: `HTTP/1.1 200 OK`
* **Response Body**: Valid JSON containing `{"incidents": [...]}`

---

## 4. Configure Frontend Console

Initialize the local configuration file:

```powershell
Copy-Item frontend\config.example.js frontend\config.js
```

Edit `frontend\config.js` and set:
* `CONTROL_API_BASE`: Value of `$CONTROL_API_URL`
* `API_KEY`: Value of `$API_KEY_VALUE`
* `TARGET_API_URL`: Your target API endpoint (e.g. `https://<TargetApiId>.execute-api.ap-south-1.amazonaws.com/prod/items`)

Test the console locally by opening `frontend\index.html` in your browser. All incident queries and approval calls will automatically include the `x-api-key` header.
