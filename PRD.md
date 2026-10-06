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

## In scope (Implemented & Shipped)
- Request-volume based detection (API Gateway `Count` metric + CloudWatch logs)
- Deploy-heartbeat context (custom DynamoDB table `Deployments`)
- Deterministic Z-score & caller dominance pre-filter (fast math gate)
- Bedrock-based narrative enrichment using Converse API with `toolConfig`
- Surgical remediation: AWS WAFv2 regional IP Set (`fuse-blocked-ips`) drops bad caller IP with HTTP 403
- Automated 15-minute cooldown recovery (unblocks stale IPs via EventBridge scan)
- Cross-account customer onboarding via CloudFormation template (`fuse-cross-account-role.yaml`)
- Operator dashboard on AWS Amplify with session auth gate
- Developer CLI (`cli/fuse.py`) and Model Context Protocol server (`mcp_server.py`)

## Evolution from Initial Prototype
- **From Stage Throttle to WAF IP Blocking**: The original prototype set API Gateway `RateLimit -> 0`, which worked for testing but took down the whole API for paying customers. The current build replaces global throttling with regional AWS WAFv2 IP Sets. Offending IPs get dropped at the edge; healthy traffic continues uninterrupted.
- **From Sync Bedrock to Deterministic Gate**: Initially, Bedrock was in the critical path for every check. To guarantee sub-second decision times and eliminate LLM latency/outage risks, the Poller evaluates Z-scores and caller concentration deterministically in Python. Bedrock runs asynchronously for structured post-incident analysis.

## Competitive Reality & Technical Tradeoffs
- **AWS Budgets & Cost Anomaly Detection**: AWS Budgets does support automated actions (IAM policies, SCPs, stopping EC2/RDS). The practical issue is data freshness: Cost and Usage Reports (CUR) and billing metrics lag reality by 6 to 24+ hours. When an infinite client loop fires 500 req/s, automated actions that run tomorrow are useless.
- **AWS WAF Rate-Based Rules**: WAF supports 1, 2, 5, or 10-minute sliding windows (down to 10 requests). The limitation is that they are stateless window counters. A slow-burn loop (e.g., 40 req/min from a rogue worker) stays well under standard rate limits but costs thousands over an 8-hour stretch. Native WAF rules also have no concept of deployment events or caller diversity.
- **Cloudflare Rate Limiting**: While Cloudflare supports Partial (CNAME) setups without delegating full DNS, it still runs as an inline reverse proxy. Every user request takes an extra network hop to an external edge network. Fuse runs out-of-band on AWS, adding 0ms of latency to normal requests.
- **Shared IP / NAT Tradeoff**: Surgical `/32` blocking is reliable for machine-to-machine traffic, cron jobs, and webhooks. If abusive traffic comes through a shared corporate proxy, NAT gateway, or carrier network, blocking that IP affects everyone behind that IP. The production roadmap addresses this by combining WAF IP blocking with per-API-key and JWT-claim throttling.
- **Telemetry Latency Reality**: CloudWatch API Gateway metrics publish in 1-minute aggregation buckets. Total time-to-block for out-of-band analysis is ~60 to 70 seconds. To buffer against extreme instant floods during that 60-second window, Fuse pairs with a native Tier-1 WAF rate rule (`fuse-emergency-burst-cap`).

## Constraints
- Solo build, Bharat Builds Tour (Ship It track)
- Core compute, telemetry, and remediation must remain 100% native AWS
- Infrastructure managed declaratively via AWS SAM (`template.yaml`)
