# DEPLOY.md — Environment & deployment runbook

No CDK/Terraform for this build — manual console + boto3 scripts, documented
here so the steps are reproducible and so the AWS Builder Center blog post
can reference this directly.

## Prerequisites
- AWS account with billing alerts already on (basic safety net beneath the
  guardrail itself — see AGENTS.md, do not rely on the guardrail as the only
  safety net during your own testing)
- AWS Builder Center profile created, $100 credit code claimed
- AWS CLI configured locally with a scoped-down IAM user (not root)
- Python 3.12, boto3 installed locally for running deploy/test scripts
- Bedrock model access requested and approved for Claude 3.5 Haiku, in your
  target region (Bedrock model access is opt-in per region/account)

## Region
Pick one region for everything (e.g. `ap-south-1` for lowest latency from
Greater Noida) and do not mix. Note it once in `infra/setup-notes.md` and
reference it everywhere — inconsistent regions is the #1 way a hackathon
demo breaks live.

## Quickstart Provisioning (Recommended)

Run the single master orchestration script to provision the entire Fuse infrastructure in sequence with dependency validation and error halts:

```bash
python scripts/setup_all.py
```

This orchestrator executes the 6 verified deployment steps in strict order:
1. `scripts/setup_dynamodb.py` — Creates `Deployments`, `Incidents`, and `ApprovalQueue` tables (on-demand).
2. `scripts/setup_demo_api.py` — Creates the protected target API Gateway (`guardrail-demo-api`) and backing Lambda.
3. `scripts/setup_poller.py` — Deploys `guardrail-poller` and the 1-minute EventBridge schedule rule.
4. `scripts/setup_reasoner.py` — Deploys `guardrail-reasoner` Lambda wired to Bedrock Converse API.
5. `scripts/setup_day3.py` — Deploys `guardrail-remediator`, `guardrail-approve-action`, `guardrail-get-incidents`, and `guardrail-control-api`.
6. `scripts/deploy_dashboard.py` — Deploys the operator console static assets to S3.

> **Verification Status**: `setup_all.py` has been verified end-to-end on both:
> 1. **Idempotency on existing deployment** (`ap-south-1`): all 6 steps executed and passed in 111.1s without state collision.
> 2. **Real CREATE path on a clean region** (`us-east-1`): exercised initial DynamoDB table creation, Lambda creation, API Gateway generation, EventBridge rule wiring, and S3 static bucket hosting in 198.6s with zero errors, followed by clean automated teardown.

---

## Detailed Step-by-Step Provisioning (Manual Runbook)
If you prefer to inspect, customize, or execute individual steps manually, follow this sequence (must follow this order — later steps depend on earlier ones):
1. **DynamoDB tables** — create `Deployments`, `Incidents`, `ApprovalQueue`
   (SCHEMA.md), on-demand billing mode
2. **Demo API Gateway + backing Lambda** — the resource that will later get
   throttled; deploy this first so it exists as a throttle target
3. **IAM roles** — one per Lambda, least-privilege (poller: CloudWatch read +
   DynamoDB read; reasoner: Bedrock invoke + DynamoDB write; remediator:
   API Gateway `UpdateStage` + DynamoDB write; approve-action: DynamoDB
   read/write; get-incidents: DynamoDB read only)
4. **Poller, reasoner, remediator Lambdas** — deploy in this order since each
   can be smoke-tested standalone before wiring the next
5. **EventBridge rule** — wire to poller only once poller works standalone
6. **approve-action + get-incidents Lambdas**, fronted by API Gateway
   (separate API from the "demo" one being monitored — do not reuse the same
   API Gateway for both roles, that gets confusing fast)
7. **Frontend** — static files to S3 with static website hosting enabled, or
   Amplify Hosting if preferred; point `app.js` at the `get-incidents` /
   `approve-action` endpoints
8. **Deploy heartbeat wiring** — add the `deploy_heartbeat.py` call as the
   last line of whatever counts as your "deploy" step for the demo API

### WAF Web ACL Stage Association (Setup-Only Operation)
Associating the WAF Web ACL (`fuse-guardrail-acl`) with an API Gateway stage (which requires `wafv2:AssociateWebACL` and `apigateway:SetWebACL`) is performed **once during initial onboarding setup** (via `scripts/setup_waf.py`, AWS CLI, or the AWS WAF Console). 

> [!NOTE]
> **Cross-Account Customer Accounts:**
> The customer CloudFormation template (`infra/cloudformation/fuse-cross-account-role.yaml`) provisions the least-privilege IAM role for Fuse. It **does not create or associate** the customer's WAF Web ACL. The customer must have a regional WAF Web ACL containing an IPSet rule, associate it to their API Gateway stage, and verify the attachment:
> ```bash
> # 1. Associate Web ACL to the API Gateway Stage
> aws wafv2 associate-web-acl \
>   --web-acl-arn <WEB_ACL_ARN> \
>   --resource-arn arn:aws:apigateway:<REGION>::/restapis/<API_ID>/stages/<STAGE>
> 
> # 2. Verify Association
> aws wafv2 get-web-acl-for-resource \
>   --resource-arn arn:aws:apigateway:<REGION>::/restapis/<API_ID>/stages/<STAGE>
> ```

At runtime, Fuse never modifies or disassociates stage attachments; the Remediator Lambda operates with surgical least privilege, performing mutations strictly on the WAF IPSet (`wafv2:GetIPSet` and `wafv2:UpdateIPSet`). Neither the runtime cross-account IAM role nor the central SAM stack requires `apigateway:SetWebACL` or runtime `wafv2:AssociateWebACL` permissions.

## AWS Amplify Hosting Deployment & Environment Variables

Fuse supports two deployment paths to AWS Amplify Hosting:

### Path A: Manual API Deployment (`scripts/deploy_amplify.py`)
When deploying directly from your local terminal or CLI without linking GitHub branches:
1. Export the control plane environment variables:
   ```bash
   export CONTROL_API_BASE="https://<api-id>.execute-api.ap-south-1.amazonaws.com/prod"
   export API_KEY="<your-control-api-key>"
   export TARGET_API_URL="https://<target-api-id>.execute-api.ap-south-1.amazonaws.com/prod/items"
   export OPERATOR_PASSWORD="<your-operator-password>"
   ```
2. (Optional) Run local packaging & verification with `--dry-run` (zero AWS calls):
   ```bash
   python scripts/deploy_amplify.py --dry-run
   ```
3. Run live deployment to the existing Amplify app (`fuse-console` / `d1hndpgpwb40h8`):
   ```bash
   python scripts/deploy_amplify.py
   ```
`deploy_amplify.py` generates a temporary `frontend/config.js` via `scripts/generate_config.js`, bundles `frontend/` into a sanitized ZIP archive (excluding `.git`, `.env*`, and `node_modules`), uploads it to the existing live app (`d1hndpgpwb40h8`), starts the deployment job, and cleans up the local `config.js`. It never creates duplicate Amplify apps or alters the live URL (`https://main.d1hndpgpwb40h8.amplifyapp.com`).

### Path B: Git-Connected Continuous Deployment (`amplify.yml`)
When linking your GitHub repository to AWS Amplify Hosting in the AWS Console:
- Amplify executes the build steps in [`amplify.yml`](amplify.yml) which runs `node scripts/generate_config.js`.
- Configure the environment variables in **AWS Amplify Console > App settings > Environment variables**:

| Variable | Description | Example / Source |
|---|---|---|
| `CONTROL_API_BASE` | Base URL of the deployed Fuse Control Plane API | `https://<api-id>.execute-api.ap-south-1.amazonaws.com/prod` (from SAM Output `ControlApiUrl`) |
| `API_KEY` | API Key for authenticating Control API requests (`x-api-key`) | Fetch with: `aws apigateway get-api-key --api-key <KeyId> --include-value` |
| `TARGET_API_URL` | Monitored target API endpoint for live circuit status probes | `https://<target-api-id>.execute-api.ap-south-1.amazonaws.com/prod/items` |
| `OPERATOR_PASSWORD` | Password required to unlock the demo operator dashboard | Secret password string chosen by operator |

> [!WARNING]
> **Client-Side Auth Security Notice:**
> `OPERATOR_PASSWORD` embedded in `frontend/config.js` is delivered to the browser runtime. While it prevents casual unauthorized viewing of the console during hackathon demonstrations, it is **not a cryptographic security boundary** (any browser user inspecting network responses or client memory can see it). In production multi-tenant environments, enforce authentication at the API Gateway layer using Amazon Cognito User Pools (JWT authorizer) or AWS IAM SigV4.

## Environment variables (per Lambda)
| Lambda | Env vars |
|---|---|
| poller | `DEMO_API_STAGE_ARN`, `BASELINE_WINDOW_MINUTES`, `SPIKE_THRESHOLD_MULTIPLIER` |
| reasoner | `BEDROCK_MODEL_ID`, `INCIDENTS_TABLE_NAME`, `DEPLOYMENTS_TABLE_NAME` |
| remediator | `APPROVAL_QUEUE_TABLE_NAME` |
| approve-action | `APPROVAL_QUEUE_TABLE_NAME`, `INCIDENTS_TABLE_NAME` |
| get-incidents | `INCIDENTS_TABLE_NAME` |

## Rollback / reset procedure (use between test runs and before final demo)
```bash
# Reset throttle on the demo API stage back to normal
aws apigateway update-stage --rest-api-id <id> --stage-name prod \
  --patch-operations op=replace,path=/throttle/rateLimit,value=1000 \
                      op=replace,path=/throttle/burstLimit,value=2000

# Clear test data (write a small script; do not hand-delete in console
# under time pressure)
python scripts/clear_test_data.py
```

## Cost hygiene during the hackathon itself
- Set a personal AWS Budget alert at a low threshold ($10–20) as your own
  real safety net while building the thing whose entire purpose is being a
  safety net — the irony of skipping this is not worth it
- Tear down or throttle the demo API between build sessions if left running
  unattended
- Delete unused Lambda versions/aliases before submission to keep the repo
  and account tidy for judges who look

## Submission checklist
- [ ] Live URL (dashboard) works from a clean/incognito browser
- [ ] GitHub repo public, README includes architecture diagram + "what we
      learned" section
- [x] Demo video ≤ 3 minutes, uploaded and linked: https://youtu.be/UWzPBdO63ek
- [ ] AWS Builder Center blog post published and linked
- [ ] All docs in this set (AGENTS/PRD/ARCHITECTURE/SCHEMA/API/TASKS/
      DESIGN/TESTING/DEPLOY) committed to the repo — judges reading the repo
      see a team that planned, not one that improvised
