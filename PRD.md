# PRD.md — AWS Cost Guardrail Agent

## Problem
Cloud billing dashboards lag reality by hours. A runaway process — a
misconfigured loop, a rogue AI agent retrying the same failing tool call —
can burn thousands of dollars before any alert fires. The canonical example:
a Cloudflare Durable Objects misconfiguration produced a $34,000 bill in 8
days with no real-time intervention.

Static threshold rules ("alert if requests > N/min") are the naive fix, but
they can't distinguish a legitimate traffic spike from a runaway loop — they
either miss the loop (threshold too high) or kill legitimate load (threshold
too low).

## Solution
A serverless AWS-native agent that:
1. Watches request-volume metrics (a fast leading indicator, not lagging
   billing data) in near-real-time
2. On a spike, gathers context (recent deploy activity, unique-caller
   diversity, repeated-payload signature)
3. Asks Bedrock to reason about *why* the spike is happening — legitimate
   growth vs. a semantically repeating failure loop — not just whether a
   number crossed a line
4. Auto-throttles dev/staging resources; gates production behind a one-click
   human approval
5. Logs every incident for review

## Target user
Any team running AWS workloads that could enter a runaway state — AI agent
pipelines are the sharpest example, but the same failure mode applies to any
retry-loop bug.

## Success criteria for this hackathon
- A live, working detect → reason → act pipeline deployed on AWS with a URL
- A 3-minute demo video showing three scenarios:
  1. Static rule kills a legitimate load-test spike (false positive)
  2. Bedrock correctly passes the same legitimate spike
  3. Bedrock correctly catches and throttles a semantic repeat-loop that a
     raw count threshold would miss entirely
- Incident log visible in a simple dashboard
- AWS Builder Center blog post documenting the build (bonus prize track)

## In scope
- Request-volume based detection (API Gateway `Count` metric)
- Deploy-heartbeat context (custom DynamoDB table, not CloudTrail lookups)
- Bedrock-based classification with a structured prompt
- Single remediation action: API Gateway stage throttle to zero
- Dev/staging auto-execute; prod approval gate (DynamoDB flag + one endpoint)
- Incident log + minimal dashboard

## Out of scope (explicitly — do not build, even if "quick to add")
- Multi-resource remediation (EC2, Lambda concurrency, IAM)
- Real billing-metric integration (`EstimatedCharges` — too laggy to be
  useful for a demo)
- Kinesis/Firehose streaming pipelines
- API Gateway caching and cache-hit/miss reasoning
- Cedar policy engine, sub-agents, sandboxed code execution
- Multi-tenant support, user accounts/auth beyond a single approval token
- Slack/WhatsApp integration (nice-to-have only if Day 4 has slack — pun
  intended — in the schedule)

## Constraints
- Solo build, 4 days (Sept 17–20, 2026)
- Must use AWS services as core logic, not just hosting (mandatory to win
  any prize per hackathon rules)
- Demo is video-only — no live demo in front of judges — so the recorded
  scenario must be bulletproof and pre-scripted
