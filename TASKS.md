# TASKS.md — 4-day roadmap

Event window: Thu Sept 17 – Sun Sept 20, 2026. Solo build.

## Day 1 (Thu) — Foundations, no Bedrock yet
- [ ] AWS Builder Center signup (mandatory to compete)
- [ ] New/existing AWS account, claim the $100 team credit code
- [ ] Create the "demo" API Gateway + a trivial backing Lambda (this is the
      resource that gets throttled later — needs to exist first)
- [ ] Create the three DynamoDB tables (SCHEMA.md)
- [ ] Write `deploy_heartbeat.py`, wire it as the last step of any deploy
- [ ] Poller Lambda: pull `AWS/ApiGateway` Count via `get_metric_data`,
      compute rolling baseline, log to console (no Bedrock/remediation yet)
- [ ] EventBridge rule wired to poller, confirmed firing every 1 min
- **End-of-day check**: poller Lambda logs real metric deltas on a schedule

## Day 2 (Fri) — Reasoning
- [ ] Request Bedrock model access (Claude 3.5 Haiku) if not already enabled
- [ ] Reasoner Lambda: build context payload, single `InvokeModel` call,
      parse JSON response (API.md contract)
- [ ] Unique-caller-count logic (from API Gateway access logs or a header
      you control in the load-test scripts)
- [ ] Incidents table: every cycle writes a record, classification included
- [ ] Manual test: trigger poller manually with fake high metrics, confirm
      Bedrock returns a sane classification
- **End-of-day check**: one full detect→reason→log cycle works end to end,
  manually triggered

## Day 3 (Sat) — Remediation + approval gate
- [ ] Remediator Lambda: `update_stage` throttle logic, idempotency check
- [ ] Dev/staging path: reasoner → remediator direct call on RUNAWAY
- [ ] Prod path: reasoner → ApprovalQueue write on RUNAWAY, no auto-throttle
- [ ] `approve-action` Lambda + API Gateway endpoint
- [ ] `get-incidents` Lambda + API Gateway endpoint
- [ ] Write the three demo scripts: `load_test_legit.py` (many unique
      callers), `load_test_runaway.py` (single caller, identical payload),
      and a naive static-threshold script to show the false-positive
- **End-of-day check**: full pipeline works live — trigger a runaway loop,
  watch it get throttled (dev) or queued (prod), approve it, confirm
  throttle applies

## Day 4 (Sun) — Polish, demo, submit
- [ ] Minimal dashboard: incident list, classification, explanation,
      action taken (frontend/index.html + app.js hitting `/incidents`)
- [ ] Deploy dashboard to S3/Amplify, confirm public URL works
- [ ] Rehearse and record the 3-minute demo video (see docs/demo-script.md)
      — script it, don't improvise live
- [ ] Write the AWS Builder Center blog post (bonus prize track)
- [ ] Final run-through: fresh AWS resources, confirm nothing depends on
      leftover state from earlier testing
- [ ] Submit: GitHub URL, live URL, demo video, blog link
- **End-of-day check**: submission form fully complete before deadline

## Cut list if behind schedule (in order of what goes first)
1. Dashboard polish — a bare unstyled table is fine
2. Blog post — bonus prize only, not core judging
3. Prod approval-gate UI niceties — a raw POST via curl in the demo is
   acceptable if the frontend button doesn't make it in time
4. Never cut: the 3-way demo scenario. That is the entire pitch.
