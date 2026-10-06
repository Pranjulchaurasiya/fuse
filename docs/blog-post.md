# Fuse: The Surgical Cloud Cost Guardrail & WAF Circuit Breaker

*Built by [Pranjul Chaurasiya](https://github.com/Pranjulchaurasiya) for First Commit — Bharat Builds Tour 2026 (Ship It Track).*  
*Live Console: [https://main.d1hndpgpwb40h8.amplifyapp.com](https://main.d1hndpgpwb40h8.amplifyapp.com)*  
*Demo Video (2m 58s): [https://youtu.be/UWzPBdO63ek](https://youtu.be/UWzPBdO63ek)*  
*GitHub Repository: [github.com/Pranjulchaurasiya/fuse](https://github.com/Pranjulchaurasiya/fuse)*

---

## 1. The $5,000 Retry Loop: The Hidden Risk in Serverless

Serverless architectures built on **Amazon API Gateway**, **AWS Lambda**, and **Amazon DynamoDB** give teams instant scalability and pay-per-request economics. But auto-scaling has an operational blind spot: **unbounded financial liability**.

A client SDK missing jitter, a broken retry loop on a 500 error, or an autonomous LLM agent stuck in recursion can hit an API with hundreds of requests per second. Because AWS serverless primitives scale automatically to meet demand, the system processes every call. The developer only finds out hours later when checking billing alerts or waking up to a four-figure charge.

### Why Standard Defenses Fall Short

1. **AWS Budgets & Cost Anomaly Detection**: AWS Budgets does support automated actions (like applying IAM deny policies or stopping EC2 instances). The real bottleneck is data freshness: Cost and Usage Reports (CUR) and billing metrics lag reality by 6 to 24+ hours. If a runaway loop is running at 500 req/s, an automated action that triggers tomorrow morning arrives long after the budget is gone.
2. **Static CloudWatch Alarms (`Count > 1,000`)**: A static volume threshold can't differentiate between 1,000 unique buyers during a flash sale and 1 rogue client hitting a failing endpoint 1,000 times. If you wire a static alarm to shut down the API stage, you take down the service for all paying users.
3. **AWS WAF Native Rate-Based Rules**: AWS WAF supports 1, 2, 5, or 10-minute sliding windows (down to 10 requests per window). But native WAF rules are stateless counters within those fixed windows. A slow-burn loop (e.g., 40 req/min from a background worker) stays comfortably under static rate limits while racking up thousands in compute and database write units over an 8-hour stretch. Native rules also have no visibility into deployment events or client diversity.
4. **Inline API Gateways & Edge Proxies (e.g., Cloudflare)**: While edge proxies provide rate-limiting, they sit inline in front of your traffic. Even with partial CNAME setups, every API request incurs an extra network transit hop to an external network.

To solve this without adding request latency or taking down entire APIs, I built **Fuse**: an autonomous, out-of-band circuit breaker that uses deterministic statistical analysis, AWS WAFv2, and Amazon Bedrock to isolate runaway caller IPs at the edge in ~60 seconds.

---

## 2. Architecture & How It Works

Fuse operates entirely out-of-band. Healthy API requests go straight to API Gateway with **0ms added proxy latency**.

```
                   ┌──────────────────────────────┐
                   │  EventBridge (1-min rule)    │
                   └──────────────┬───────────────┘
                                  │
                                  ▼
┌──────────────────┐      ┌───────────────┐        ┌──────────────────┐
│ CloudWatch Logs  │◄─────┤ guardrail-    │───────►│ DynamoDB         │
│ & API GW Metrics │      │ poller        │        │ (Deployments)    │
└──────────────────┘      └───────┬───────┘        └──────────────────┘
                                  │
                                  ├────────────────────────┐
                                  │ (Deterministic anomaly)│ (Async enrichment)
                                  ▼                        ▼
                          ┌───────────────┐        ┌──────────────────┐
                          │ guardrail-    │        │ guardrail-       │
                          │ remediator    │        │ reasoner         │
                          └───────┬───────┘        └────────┬─────────┘
                                  │                         │ (Converse API)
                                  ▼                         ▼
                          ┌───────────────┐        ┌──────────────────┐
                          │ AWS WAFv2     │        │ Amazon Bedrock   │
                          │ IP Set (/32)  │        │ (Nova Micro)     │
                          └───────┬───────┘        └────────┬─────────┘
                                  │                         │
                                  ▼                         ▼
                          ┌───────────────┐        ┌──────────────────┐
                          │ API Gateway   │◄───────┤ DynamoDB         │
                          │ (Drops IP 403)│        │ (Incidents Log)  │
                          └───────────────┘        └──────────────────┘
```

### The Telemetry & Remediation Flow

1. **Observe (60s Cadence)**: Amazon EventBridge invokes `guardrail-poller` once per minute. The poller pulls the `Count` metric from CloudWatch for the target API Gateway and fetches recent log lines from the CloudWatch Log Group.
2. **Evaluate (Deterministic Python Math)**: The poller calculates a rolling 15-minute baseline, standard deviation, and statistical Z-score:
   $$Z = \frac{\text{Current Count} - \text{Baseline}}{\sigma}$$
   If $Z \ge 2.5$ and volume exceeds a minimum threshold (10 req/min), an anomaly is confirmed. The poller then checks caller concentration: if a single IP accounts for $>85\%$ of the traffic (or unique caller count $\le 2$), it flags a `RUNAWAY` loop.
3. **Isolate (AWS WAFv2 IP Set)**: The poller immediately calls `guardrail-remediator`. The remediator adds the offending IP (`/32`) into the regional AWS WAFv2 IP Set (`fuse-blocked-ips`) associated with the API Gateway Web ACL. Subsequent requests from that specific IP receive an immediate **HTTP 403 Forbidden** at the edge. Legitimate users continue getting HTTP 200 responses uninterrupted.
4. **Enrich (Async Amazon Bedrock)**: Non-blocking post-incident enrichment invokes `guardrail-reasoner` asynchronously. Using the Bedrock Converse API with structured `toolConfig`, Amazon Nova Micro generates a concise forensic explanation written directly into DynamoDB for operator review.
5. **Auto-Recover (15-Minute Cooldown)**: During each run, the poller scans DynamoDB for active IP blocks older than 15 minutes. Stale blocks trigger an unblock payload to the remediator, releasing the IP from WAF so transient bugs don't become permanent bans.

---

## 3. Real-World Latency & The Edge Defense

Here is the realistic timing breakdown of how out-of-band remediation performs against sudden traffic:

| Step | Subsystem | Typical Latency | What Happens |
| :--- | :--- | :--- | :--- |
| **Tier 1: Emergency Burst** | Native AWS WAF Rate Rule | **< 1s inline** | Catches extreme spikes (>500 req/5min) before metrics register. |
| **Metric Ingestion** | CloudWatch API GW `Count` | **~60s aggregation** | EventBridge polls `get_metric_data` on a 1-minute cadence. |
| **Log Extraction** | CloudWatch Logs Filter | **150ms – 400ms** | Bounded `startTime` and log pattern filtering avoid timeouts. |
| **Statistical Analysis** | Poller Lambda (Python) | **< 50ms** | Evaluates volume floor, Z-score, and caller concentration. |
| **WAF Mutation** | Remediator Lambda | **~250ms** | Calls `wafv2.update_ip_set` using optimistic locking (`LockToken`). |
| **Edge Sync** | AWS Regional WAF | **2s – 4s** | Syncs rule across regional points of presence. |

**Total Time-to-Block:** **~62 to 65 seconds.**

Against an unconstrained runaway loop firing 500 requests per second, capping execution within ~60 seconds limits the total cost to **~$1 to $3**, compared to hundreds or thousands of dollars accumulated overnight before manual intervention.

### The Shared IP / NAT Boundary
Surgical `/32` blocking works cleanly for machine-to-machine APIs, webhooks, and rogue developer scripts. However, if abusive traffic originates from an IP shared behind a corporate NAT gateway or Apple Private Relay, blocking that `/32` will temporarily affect other users sharing that egress IP. In the production roadmap, we plan to pair WAF IP blocking with per-API-key and JWT-claim throttling to isolate authenticated users individually.

---

## 4. Multi-Tenant Cross-Account IAM Architecture

For teams running multi-account setups or using Fuse as an internal platform service, Fuse never asks for static AWS access keys.

```
Customer AWS Account                     Fuse Engine (515903395012)
┌──────────────────────────────┐        ┌──────────────────────────────┐
│  fuse-cross-account-role     │◄───────┤  sts:AssumeRole              │
│  - CloudWatch Read           │        │  (ExternalId validated)      │
│  - WAFv2 IP Set Write        │        │                              │
└──────────────────────────────┘        └──────────────────────────────┘
```

1. **1-Click CloudFormation Stack**: Customers deploy `fuse-cross-account-role.yaml` in their AWS account.
2. **Confused Deputy Prevention**: The trust policy requires a tenant-unique `sts:ExternalId` generated during onboarding. Fuse validates this string on every `assume_role` call.
3. **Scoped Least Privilege**: The role can only read CloudWatch metrics/logs and modify WAF IP sets. It has no access to data storage, IAM roles, or Lambda source code.

---

## 5. Structured AI Output with Bedrock Converse

To avoid JSON parsing errors or unpredictable LLM output in operations, Fuse uses the **Amazon Bedrock Converse API** with a strict `toolConfig` schema:

```python
CLASSIFY_TOOL_SPEC = {
    "tools": [{
        "toolSpec": {
            "name": "classify_anomaly",
            "description": "Classifies whether an API traffic surge is legitimate or a runaway cost loop.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "classification": {"type": "string", "enum": ["NORMAL", "RUNAWAY"]},
                        "confidence": {"type": "number"},
                        "explanation": {"type": "string"}
                    },
                    "required": ["classification", "confidence", "explanation"]
                }
            }
        }
    }],
    "toolChoice": {"tool": {"name": "classify_anomaly"}}
}
```

By forcing `toolChoice`, Bedrock returns structured JSON directly into `toolUse.input`, eliminating regex parsing or schema validation failures in production.

---

## 6. What We Learned Building Fuse

1. **Keep LLMs Off the Critical Fast Path**: Generative models are great for synthesizing context and summarizing logs for humans, but deterministic Python math (standard deviations and caller concentration) is faster, cheaper, and more reliable for sub-second blocking decisions. Running Bedrock asynchronously gives us the best of both worlds: instant edge mitigation and rich audit logs.
2. **Surgical Containment Beats Blunt Throttles**: Taking down an entire API Gateway stage during an incident stops the bleeding, but it creates a self-inflicted outage for good users. Modifying a WAF IP Set isolates the bad actor while preserving revenue flow for everyone else.
3. **Decouple the Management Plane**: The operator console and incident APIs run on an independent API Gateway (`guardrail-control-api`). Even if a target workload is under attack, operators never lose dashboard visibility or control.

---

## Live Links & Verification

* 🌐 **Live Console**: [https://main.d1hndpgpwb40h8.amplifyapp.com](https://main.d1hndpgpwb40h8.amplifyapp.com)
* 📋 **Customer Onboarding**: [https://main.d1hndpgpwb40h8.amplifyapp.com/onboarding.html](https://main.d1hndpgpwb40h8.amplifyapp.com/onboarding.html)
* 📺 **Demo Walkthrough Video (2m 58s)**: [Watch on YouTube](https://youtu.be/UWzPBdO63ek)
* 💻 **Source Code**: [GitHub: Pranjulchaurasiya/fuse](https://github.com/Pranjulchaurasiya/fuse)
* 📍 **AWS Region**: `ap-south-1` (Mumbai)
