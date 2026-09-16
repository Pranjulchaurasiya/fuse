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

## Deployment order (must follow this sequence — later steps depend on earlier ones)
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
- [ ] Demo video ≤ 3 minutes, uploaded and linked
- [ ] AWS Builder Center blog post published and linked
- [ ] All docs in this set (AGENTS/PRD/ARCHITECTURE/SCHEMA/API/TASKS/
      DESIGN/TESTING/DEPLOY) committed to the repo — judges reading the repo
      see a team that planned, not one that improvised
