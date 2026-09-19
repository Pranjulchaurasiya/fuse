# Fuse: Building an Autonomous Serverless Cost Guardrail with Amazon Bedrock, EventBridge, and DynamoDB

*Author: Pranjul Chaurasiya (@pranjul_chaurasiya)*  
*Event: First Commit — Bharat Builds Tour (WeMakeDevs &times; AWS)*  
*Track: Ship It & Best UI (Team Code: ZK2FP6)*  
*Live Console: [https://main.d1hndpgpwb40h8.amplifyapp.com](https://main.d1hndpgpwb40h8.amplifyapp.com)*  
*Repository: [github.com/Pranjulchaurasiya/fuse](https://github.com/Pranjulchaurasiya/fuse)*

---

## 1. The $5,000 Infinite Loop: Why Serverless Needs Context-Aware Protection

Serverless computing (AWS Lambda, API Gateway, DynamoDB) gives developers instant scalability and pay-per-use efficiency. But infinite scalability has a dangerous dark side: **unbounded financial liability**.

A subtle bug in a client SDK, an exponential backoff that forgets jitter, or a recursive retry loop between microservices can fire thousands of requests per second into an API. Because serverless scales seamlessly, AWS dutifully processes every single request—and generates a massive bill while you sleep.

### The Dilemma of Static CloudWatch Alarms
The standard defense is a CloudWatch Alarm: *"If Request Count > 1,000 over 5 minutes, trigger an alert."*

However, static alarms suffer from a fundamental trade-off:
1. **False Positives (The Flash Sale Disaster)**: If your marketing team launches a flash sale, 1,000 real paying users arrive at once. A naive alarm trips and triggers auto-throttling, breaking production for your best customers.
2. **Delayed Response**: By the time an on-call engineer wakes up to a PagerDuty alert, logs into the AWS Management Console, diagnoses the anomaly, and manually adjusts stage throttle limits, thousands of dollars have already burned.

To solve this, we built **AWS Cost Guardrail Agent**—an autonomous, context-aware circuit breaker that uses Amazon Bedrock to distinguish between legitimate business surges and destructive runaway loops, remediating anomalies in seconds.

---

## 2. Architecture Overview

To maintain safety and zero framework sprawl during a 4-day sprint, the architecture follows five core principles:
1. **Single Responsibility Lambdas**: Detection, reasoning, remediation, and human approval are cleanly separated.
2. **Isolated Control Plane**: The operator dashboard and approval endpoints live on a completely separate API Gateway from the protected workload. Throttling the application API never breaks the control plane.
3. **No Request-Time Latency**: The guardrail does not sit inline in the request path; it polls CloudWatch metrics asynchronously every minute via EventBridge.
4. **Context-Rich Heartbeats**: Deployments write a heartbeat to DynamoDB (`Deployments`), allowing Bedrock to correlate spikes with recent software releases.
5. **Fail-Closed Cost Safety**: If Bedrock ever encounters a network timeout or service quota limit, the reasoner defaults to `RUNAWAY` to guarantee financial safety.

```
                    ┌────────────────────────────┐
                    │  EventBridge (1-min rate)   │
                    └─────────────┬──────────────┘
                                  │
                                  ▼
┌─────────────────┐       ┌───────────────┐        ┌──────────────────┐
│ CloudWatch Logs │◄──────┤ guardrail-    │───────►│ DynamoDB         │
│ & Metrics       │       │ poller        │        │ (Deployments)    │
└─────────────────┘       └───────┬───────┘        └──────────────────┘
                                  │ (snapshot payload)
                                  ▼
                          ┌───────────────┐        ┌──────────────────┐
                          │ guardrail-    │◄──────►│ Amazon Bedrock   │
                          │ reasoner      │        │ (Converse API)   │
                          └───────┬───────┘        └──────────────────┘
                                  │
                                  ▼
                      ┌───────────────────────┐
                      │ DynamoDB (Incidents)  │
                      └───────────────────────┘
                                  │
                 ┌────────────────┴────────────────┐
                 ▼ (dev / staging)                 ▼ (prod)
        ┌─────────────────┐               ┌─────────────────┐
        │ guardrail-      │               │ DynamoDB        │
        │ remediator      │               │ (ApprovalQueue) │
        └────────┬────────┘               └────────┬────────┘
                 │                                 │
                 ▼                                 ▼ (Human Approves)
        ┌─────────────────┐               ┌─────────────────┐
        │ API Gateway     │◄──────────────┤ guardrail-      │
        │ Stage Throttle  │               │ approve-action  │
        │ (RateLimit → 0) │               └─────────────────┘
        └─────────────────┘
```

---

## 3. Structured Reasoning with Amazon Bedrock Converse API

One of the biggest risks with LLM integrations in production is non-deterministic output: models adding conversational filler, markdown formatting, or hallucinating schema keys.

To eliminate text-parsing errors, Guardrail Agent uses the Amazon Bedrock **Converse API** with `toolConfig`. By setting `toolChoice = {"tool": {"name": "classify_anomaly"}}`, we force Bedrock to respond exclusively through a typed schema:

```python
CLASSIFY_TOOL_SPEC = {
    "tools": [
        {
            "toolSpec": {
                "name": "classify_anomaly",
                "description": "Classifies whether an API traffic spike is legitimate or a runaway cost anomaly.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "classification": {
                                "type": "string",
                                "enum": ["NORMAL", "RUNAWAY"],
                                "description": "Classification of the traffic spike."
                            },
                            "confidence": {
                                "type": "number",
                                "description": "Confidence score between 0.0 and 1.0."
                            },
                            "explanation": {
                                "type": "string",
                                "description": "Crisp 1-2 sentence rationale explaining the classification."
                            }
                        },
                        "required": ["classification", "confidence", "explanation"]
                    }
                }
            }
        }
    ]
}
```

### Contextual Decision Matrix
The prompt supplies Bedrock with four critical signals:
1. **Delta over Baseline**: How far above the rolling 15-minute moving average is current traffic?
2. **Caller Diversity (`unique_caller_count`)**: Are requests originating from dozens of distinct IP addresses, or a single client ID?
3. **Payload Variance**: Are request bodies diverse (shopping cart, search, review), or byte-for-byte identical?
4. **Deploy Heartbeat**: Did a deployment occur in the last 10 minutes that explains this spike?

When evaluated against live traffic:
* **Legitimate Surge (35 distinct IPs, varied search terms)**: Classified as `NORMAL` (confidence 0.98).
* **Runaway Loop (1 IP, repeated failed-retry body)**: Classified as `RUNAWAY` (confidence 0.99).

---

## 4. Remediation & The Human Approval Gate

When Bedrock identifies a `RUNAWAY` incident, how should the system react?

### Dev / Staging: Autonomous Remediation
In non-production environments, speed is priority. The Reasoner immediately invokes `guardrail-remediator`, which executes an `apigateway.update_stage` call setting `throttling/rateLimit` and `throttling/burstLimit` to `0`. Within seconds, subsequent buggy requests receive `HTTP 429 Too Many Requests`.

### Production: Human-in-the-Loop Safety Gate
In production, false positives carry business risk. Therefore, on `prod`:
1. The Reasoner **withholds automated throttling**.
2. It writes a `PENDING` record into DynamoDB `ApprovalQueue`.
3. The operator dashboard highlights the incident with an amber pulsing badge and Bedrock's reasoning summary.
4. When an on-call engineer clicks **Approve Throttle**, the control plane calls `guardrail-approve-action`, which executes the stage throttle and updates the audit log.

### Strict Idempotency
Because multiple alerts can trigger simultaneously, the Remediator inspects the stage settings first. If `rateLimit == 0.0`, it returns `ALREADY_THROTTLED` without throwing errors or creating redundant API Gateway deployments.

---

## 5. Live Dashboard on Amazon S3

The operator console is hosted directly on AWS Amplify Hosting (with Amazon S3 static website fallback), connecting to the isolated `guardrail-control-api` via CORS:
* **Live Dashboard URL**: `https://main.d1hndpgpwb40h8.amplifyapp.com`
* **Real Metrics**: Scorecards for evaluations monitored, runaways caught, pending approvals, and throttled stages are derived directly from DynamoDB items—no simulated counters or guessing.
* **One-Click Approval**: Operators can review Bedrock's explanations and approve throttle actions with a single click.

---

## 6. What We Learned

1. **Structured Outputs are Non-Negotiable**: Bedrock Converse `toolConfig` completely eliminated prompt extraction errors. It makes LLMs behave like reliable deterministic microservices.
2. **Control Plane Isolation is Vital**: If your management dashboard shares an API Gateway stage with the application you throttle to 0 rps, you lock yourself out of your own emergency brakes.
3. **Deployment Context Solves False Positives**: Simply knowing that a release happened 3 minutes ago turns what looks like an anomaly into expected behavior.

---

## Summary Links
* **GitHub Repository**: [https://github.com/Pranjulchaurasiya/fuse](https://github.com/Pranjulchaurasiya/fuse)
* **Live Console (HTTPS)**: [https://main.d1hndpgpwb40h8.amplifyapp.com](https://main.d1hndpgpwb40h8.amplifyapp.com)
* **Region**: AWS Asia Pacific (Mumbai) `ap-south-1`
