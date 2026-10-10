# AGENTS.md — Rules for any AI coding assistant working on this repo

Project: **AWS Cost Guardrail Agent** ("Guardrail")
Event: First Commit — Bharat Builds Tour (Ship It track)
Builder: Pranjul Chaurasiya, solo, AI-assisted

## Prime directive
Ship a working, demo-able system by end of Day 4. Never trade a working narrow
feature for a broken broad one. If a task in TASKS.md is at risk, cut scope —
do not add abstraction, retries, or "just in case" code.

## Hard scope boundaries (do not cross these without explicit approval)
- **No Kinesis, no Firehose, no streaming pipelines.** Poll `get_metric_data`
  on a 1-minute EventBridge schedule. Latency of ~1 min is acceptable; this is
  a scripted demo, not a production SLA.
- **No CloudTrail `lookup_events` calls at request time.** Use the
  `Deployments` DynamoDB heartbeat table instead (see SCHEMA.md). One
  `put_item` call at the end of the deploy script, nothing else.
- **No API Gateway caching.** Leave it off. Do not build cache hit/miss
  logic — there is nothing to reconcile if caching is never enabled.
- **One remediation target: AWS WAFv2 IP Set surgical blocking.**
  Blocks runaway offending caller IPs at the cloud edge with optimistic lock retries.
  Avoids blunt scorched-earth full-stage throttling whenever possible.
- **No Cedar, no sub-agents, no sandboxed code execution, no mCRL2/UPPAAL.**
  These were considered and explicitly rejected for this build — do not
  reintroduce them even if a later idea "would benefit."
- **Bedrock is called asynchronously for incident enrichment**, with a single
  structured prompt and Converse API `toolConfig`. Zero LLM calls on the deterministic detection path.

## Tech stack (locked)
- **Compute**: AWS Lambda (Python 3.12, boto3)
- **Scheduling**: EventBridge (1-min rate rule)
- **Metrics source**: `AWS/ApiGateway` namespace (`Count`), via
  `cloudwatch.get_metric_data`
- **Reasoning**: Amazon Bedrock (`apac.amazon.nova-micro-v1:0` via Converse API toolConfig)
- **State**: DynamoDB — `Deployments`, `Incidents`, `ApprovalQueue`, `Fuse_Tenants`
- **API surface**: API Gateway (REST) fronting `get-incidents`, `approve-action`, `onboarding`
- **Frontend**: one static HTML/JS page (or a single React page if time
  allows), hosted on S3 or Amplify Hosting. No framework sprawl.
- **IaC**: plain boto3/console setup is acceptable for a 4-day hackathon.
  Do not spend Day 1 learning CDK/Terraform unless already fluent in it.

## Non-negotiable code quality bars (small, cheap, keep them)
- Every Lambda has a single responsibility (see ARCHITECTURE.md) — do not
  merge the poller and the remediator into one function for convenience.
- Every DynamoDB write includes a timestamp and an `incident_id` /
  `deployment_id` — the demo narrative depends on being able to show a clean
  incident log.
- The remediation Lambda must be idempotent — calling it twice on the same
  incident must not double-throttle or error.
- Secrets (API keys, tokens) go in environment variables or Secrets Manager,
  never hardcoded, never committed.

## When stuck
Re-read PRD.md's "Out of scope" section before adding anything new. If a fix
requires touching more than one new AWS service, it is probably out of scope
for this hackathon — flag it instead of building it.
