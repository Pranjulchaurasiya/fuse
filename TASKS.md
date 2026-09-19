# TASKS.md — 4-day roadmap

Event window: Thu Sept 17 – Sun Sept 20, 2026. Solo build.

## Day 1 (Thu) — Foundations, no Bedrock yet
- [ ] AWS Builder Center signup (mandatory to compete)
- [ ] New/existing AWS account, claim the $100 team credit code
- [x] Create the "demo" API Gateway + a trivial backing Lambda (this is the
      resource that gets throttled later — needs to exist first)
- [x] Create the three DynamoDB tables (SCHEMA.md)
- [x] Write `deploy_heartbeat.py`, wire it as the last step of any deploy
- [x] Poller Lambda: pull `AWS/ApiGateway` Count via `get_metric_data`,
      compute rolling baseline, log to console (no Bedrock/remediation yet)
- [x] EventBridge rule wired to poller, confirmed firing every 1 min
- **End-of-day check**: poller Lambda logs real metric deltas on a schedule

## Day 2 (Fri) — Reasoning
- [x] Request Bedrock model access (Claude 3.5 Haiku) — Anthropic console use case form walked through; Nova Micro working model active in ap-south-1
- [x] Reasoner Lambda: build context payload, Bedrock Converse call with toolConfig (structured JSON output), fail-closed fallback
- [x] Unique-caller-count logic & sample payloads ingested in Reasoner contract
- [x] Incidents table: every cycle writes a record, classification included
- [x] Manual test: trigger reasoner manually with fake high metrics, confirm Bedrock returns sane classification + fail-closed fallback
- **End-of-day check**: detect->reason->log cycle works end to end with Bedrock Converse and DynamoDB Incidents

## Day 3 (Sat) — Remediation + approval gate
- [x] Remediator Lambda: `update_stage` throttle logic, idempotency check
- [x] Dev/staging path: reasoner → remediator direct call on RUNAWAY
- [x] Prod path: reasoner → ApprovalQueue write on RUNAWAY, no auto-throttle
- [x] `approve-action` Lambda + API Gateway endpoint
- [x] `get-incidents` Lambda + API Gateway endpoint
- [x] Write the three demo scripts: `load_test_legit.py` (many unique
      callers), `load_test_runaway.py` (single caller, identical payload),
      and a naive static-threshold script to show the false-positive
- [x] **End-of-day check**: full pipeline works live — trigger a runaway loop,
  watch it get throttled (dev) or queued (prod), approve it, confirm
  throttle applies

## Day 4 (Sun) — Polish, demo, submit
- [x] Minimal dashboard: incident list, classification, explanation,
      action taken (frontend/index.html + app.js hitting `/incidents`)
- [x] Deploy dashboard to S3/Amplify, confirm public URL works
- [x] Rehearse and record the 3-minute demo video (see docs/demo-script.md)
      — script it, don't improvise live
- [x] Write the AWS Builder Center blog post (bonus prize track)
- [x] Final run-through: fresh AWS resources, confirm nothing depends on
      leftover state from earlier testing (automated with `clear_test_data.py`)
- [ ] Submit: GitHub URL, live URL, demo video, blog link
- **End-of-day check**: submission form fully complete before deadline

## Cut list if behind schedule (in order of what goes first)
1. Dashboard polish — a bare unstyled table is fine
2. Blog post — bonus prize only, not core judging
3. Prod approval-gate UI niceties — a raw POST via curl in the demo is
   acceptable if the frontend button doesn't make it in time
4. Never cut: the 3-way demo scenario. That is the entire pitch.
