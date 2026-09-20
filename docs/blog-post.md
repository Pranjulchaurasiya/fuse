# Fuse: The Cognitive Circuit Breaker for Your AWS Bill

*Built by [Pranjul Chaurasiya](https://github.com/Pranjulchaurasiya) for First Commit — Bharat Builds Tour 2026 (Ship It Track).*  
*Live Console: [https://main.d1hndpgpwb40h8.amplifyapp.com](https://main.d1hndpgpwb40h8.amplifyapp.com)*  
*Demo Video (2m 58s): [https://youtu.be/UWzPBdO63ek](https://youtu.be/UWzPBdO63ek)*  
*GitHub Repository: [github.com/Pranjulchaurasiya/fuse](https://github.com/Pranjulchaurasiya/fuse)*

---

## 1. The $5,000 Infinite Loop: Why Serverless Needs Cognitive Protection

Serverless architectures built on **AWS Lambda**, **Amazon API Gateway**, and **Amazon DynamoDB** give engineering teams instant scalability and pay-per-use economics. However, automatic scaling has a dangerous operational blind spot: **unbounded financial liability**.

A subtle bug in a client SDK, an exponential backoff algorithm without jitter, or a recursive agent loop can blast thousands of requests per second into your API. Because AWS serverless primitives scale seamlessly to meet demand, the platform will process every single request—leaving you with a massive cloud bill by morning.

### The Dilemma of Static Alarms
The conventional defense is a static CloudWatch alarm:  
`If Request Count > 1,000 over 5 minutes, trigger an alert.`

In real-world production, this creates an impossible trade-off:
1. **False Positives (The Flash Sale Outage)**: When your marketing team launches a campaign and 1,000 legitimate, paying customers hit checkout simultaneously, a static threshold trips and cuts off your highest-value traffic.
2. **Alert Lag**: By the time an on-call engineer gets paged, logs into the AWS console, reviews metrics, and manually applies stage throttling, thousands of dollars have already been burned.

To solve this, I built **Fuse**—an autonomous, context-aware circuit breaker that uses **Amazon Bedrock** to distinguish between authentic traffic surges and destructive runaway loops in under 60 seconds.

---

## 2. Architecture & Design Principles

Fuse operates completely out-of-band to introduce **zero latency** to your user-facing request path.

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
                                  │ (telemetry snapshot)
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
                 ▼ (dev / staging: Auto)           ▼ (prod: Human Gate)
        ┌─────────────────┐               ┌─────────────────┐
        │ guardrail-      │               │ DynamoDB        │
        │ remediator      │               │ (ApprovalQueue) │
        └────────┬────────┘               └────────┬────────┘
                 │                                 │
                 ▼                                 ▼ (Operator Approves)
        ┌─────────────────┐               ┌─────────────────┐
        │ API Gateway     │◄──────────────┤ guardrail-      │
        │ Stage Throttle  │               │ approve-action  │
        │ (RateLimit → 0) │               └─────────────────┘
        └─────────────────┘
```

### Key Architectural Pillars:
1. **Single Responsibility Lambdas**: Telemetry ingestion (`poller`), classification (`reasoner`), remediation (`remediator`), and approval handling (`approve-action`) are strictly decoupled.
2. **Decoupled Control Plane**: The operator console and incident APIs run on an isolated API Gateway (`guardrail-control-api`). Even if a compromised target API is throttled to 0 requests/sec, operators never lose dashboard access.
3. **Deployment Heartbeat Reconciliation**: CI/CD pipelines write a lightweight release heartbeat to DynamoDB (`Deployments`). When Bedrock evaluates a traffic surge, it factors in recent code releases to prevent false alarms during planned rollouts.
4. **Fail-Closed Safety**: If Bedrock encounters rate limits or upstream timeouts, the system safely falls back to conservative protection (`RUNAWAY` classification with `is_fallback: true`).

---

## 3. Deterministic AI Reasoning with Bedrock Converse API

One of the common hurdles with LLMs in operational loops is non-deterministic output: models returning markdown fluff or unexpected JSON keys.

Fuse eliminates this using the **Amazon Bedrock Converse API** with `toolConfig` and forced tool choice (`classify_anomaly`). This guarantees that Bedrock responds strictly according to a typed schema:

```python
import boto3

bedrock = boto3.client("bedrock-runtime", region_name="ap-south-1")

CLASSIFY_TOOL_SPEC = {
    "tools": [
        {
            "toolSpec": {
                "name": "classify_anomaly",
                "description": "Classifies whether an API traffic surge is legitimate or a runaway cost loop.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "classification": {
                                "type": "string",
                                "enum": ["NORMAL", "RUNAWAY"]
                            },
                            "confidence": {
                                "type": "number"
                            },
                            "explanation": {
                                "type": "string",
                                "description": "Concise 1-2 sentence engineering rationale."
                            }
                        },
                        "required": ["classification", "confidence", "explanation"]
                    }
                }
            }
        }
    ],
    "toolChoice": {"tool": {"name": "classify_anomaly"}}
}
```

### Multi-Dimensional Context Evaluation
Instead of relying on request count alone, Fuse passes Bedrock four operational dimensions:
* **Caller Diversity**: Are incoming requests distributed across hundreds of unique IP addresses, or originating from a single runaway client?
* **Traffic Velocity Delta**: How steep is the surge relative to the rolling 15-minute moving average?
* **Payload Variance**: Are requests carrying diverse query parameters, or byte-for-byte identical retry loops?
* **Release Correlation**: Was a new build deployed within the last 15 minutes?

**The Result:**
* **Legitimate Surge** (e.g., 35 unique callers, varied payloads) &rarr; `NORMAL` (Confidence: 0.98, No throttle).
* **Runaway Loop** (e.g., 40 rapid requests from 1 caller, repeated errors) &rarr; `RUNAWAY` (Confidence: 0.99, Circuit tripped).

---

## 4. Autonomous Containment vs. Human-in-the-Loop Safety

How a circuit breaker reacts must depend on the environment:

### Dev / Staging (Autonomous Instant Cutoff)
In non-production environments, cost velocity is the priority. The Reasoner directly triggers `guardrail-remediator`, which updates the target API Gateway stage method settings:
* `throttling/rateLimit` &rarr; `0`
* `throttling/burstLimit` &rarr; `0`

Subsequent requests immediately receive `HTTP 429 Too Many Requests` directly at the API Gateway edge, instantly halting downstream Lambda invocations and DynamoDB write costs.

### Production (Human-in-the-Loop Approval Gate)
In production, dropping an API stage to 0 requests/sec requires human validation. 
1. The Reasoner logs the incident into the `ApprovalQueue` table as `PENDING_APPROVAL`.
2. The **Fuse Console** (hosted on AWS Amplify) surfaces an amber alert with Bedrock's synthesized explanation.
3. An on-call engineer reviews the rationale and clicks **Approve Circuit Trip**.
4. The control plane invokes `guardrail-approve-action` to safely execute the throttle and log the audit trail.

### Idempotent Remediation
To prevent race conditions during rapid alerting, `guardrail-remediator` inspects current stage limits before applying patches. If the stage is already at `0 rps`, it returns `ALREADY_THROTTLED` with zero duplicate mutations.

---

## 5. Live Edge Verification

A core design principle of Fuse is **Independent Edge Observation**:
> *Never trust internal Lambda success callbacks to declare an incident resolved. Verify from the outside in.*

When Fuse executes a circuit trip, an independent edge prober tests the public API Gateway endpoint. The remediation is only marked complete once the regional edge returns a genuine `HTTP 429 Too Many Requests`.

---

## 6. What We Learned Building Fuse

1. **Structured Outputs are Essential**: Using Bedrock Converse API with forced tool schemas turns generative models into dependable, deterministic decision engines suitable for critical infrastructure.
2. **Never Share Control Plane Infrastructure**: If your operator dashboard relies on the same API Gateway or VPC as the services you might need to shut down, you risk locking yourself out of your own emergency brakes.
3. **Context Trumps Raw Thresholds**: High request volume is not a problem—monopolized single-caller volume during an error storm is. Contextual classification is the missing layer in cloud cost governance.

---

## Resources & Live Links

* 🌐 **Live Console**: [https://main.d1hndpgpwb40h8.amplifyapp.com](https://main.d1hndpgpwb40h8.amplifyapp.com)
* 📺 **Demo Walkthrough Video**: [Watch on YouTube](https://youtu.be/UWzPBdO63ek)
* 💻 **Source Code & Runbooks**: [GitHub Repository](https://github.com/Pranjulchaurasiya/fuse)
* 📍 **AWS Region**: `ap-south-1` (Mumbai)
