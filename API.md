# API.md — Interface contract

## Public HTTP API (API Gateway → Lambda)

### `GET /incidents`
Returns the incident log for the dashboard.

**Response 200**
```json
{
  "incidents": [
    {
      "incident_id": "string",
      "timestamp": 1758100000,
      "resource": "guardrail-demo-api",
      "classification": "RUNAWAY",
      "bedrock_explanation": "string",
      "action_taken": "PENDING_APPROVAL",
      "environment": "prod"
    }
  ]
}
```

### `POST /incidents/{incident_id}/approve`
Human approval for a prod incident.

**Request body**
```json
{ "resolved_by": "Pranjul", "decision": "APPROVED" }
```

**Response 200**
```json
{ "approval_id": "string", "status": "APPROVED", "throttled": true }
```

`decision: "REJECTED"` skips throttling and just marks the incident resolved.

---

## Internal contract: Bedrock reasoning call

This is the single most important interface in the system — it's what
justifies using an LLM instead of a static rule. Keep the prompt structured
and explicit; do not let the model free-associate.

**System prompt (fixed):**
```
You are a cloud cost-anomaly classifier. You will be given metrics and
context about a spike in API request volume. Decide whether this spike is:
- NORMAL: legitimate traffic growth (e.g. many unique callers, matches a
  recent deploy or marketing event)
- RUNAWAY: a malfunctioning process or agent loop (e.g. one caller repeating
  an identical request/payload at high frequency, no corresponding deploy or
  traffic-driving event)

Respond ONLY in this JSON shape, nothing else:
{"classification": "NORMAL" | "RUNAWAY", "explanation": "<one paragraph>"}
```

**User message (built by the reasoner Lambda):**
```json
{
  "current_count_per_min": 120,
  "baseline_count_per_min": 15,
  "unique_caller_count": 3,
  "total_requests_in_window": 480,
  "recent_deploy": false,
  "deploy_note": null,
  "sample_payloads": [
    "{\"action\":\"retry_fetch\",\"id\":\"x92\"}",
    "{\"action\":\"retry_fetch\",\"id\":\"x92\"}",
    "{\"action\":\"retry_fetch\",\"id\":\"x92\"}"
  ]
}
```

**Expected model output:**
```json
{
  "classification": "RUNAWAY",
  "explanation": "3 unique callers generating 480 requests with an
  identical repeated payload, no corresponding deploy event. This matches
  a stuck retry loop, not organic traffic growth."
}
```

Reasoner Lambda parses this JSON directly (`json.loads`). If parsing fails,
default to `RUNAWAY` + `escalate-for-manual-review` — fail closed, never
fail open on a cost-safety system.

---

## Internal contract: Remediator Lambda

**Input (invoked by reasoner or by approve-action Lambda):**
```json
{
  "incident_id": "string",
  "resource": "guardrail-demo-api",
  "stage": "prod"
}
```

**Action:** `apigateway.update_stage` — set `throttle/rateLimit` and
`throttle/burstLimit` to `0` for the given stage.

**Idempotency:** check current throttle settings before writing; if already
zero, no-op and log `action_taken: ALREADY_THROTTLED`.
