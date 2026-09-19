# Fuse — AWS Cost Guardrail & Real-Time Circuit Breaker

> **An autonomous, context-aware circuit breaker for serverless APIs powered by Amazon Bedrock, EventBridge, DynamoDB, and API Gateway.**  
> Built for **First Commit — Bharat Builds Tour 2026 (Ship It Track)**  
> Builder: **Pranjul Chaurasiya** (@pranjul_chaurasiya | Team Code: `ZK2FP6`)

[![Live Console](https://img.shields.io/badge/Live_Console-S3_Static_Website-blue?style=for-the-badge&logo=amazons3)](http://guardrail-dashboard-515903395012.s3-website.ap-south-1.amazonaws.com)
[![AWS Region](https://img.shields.io/badge/Region-ap--south--1_(Mumbai)-orange?style=for-the-badge&logo=amazonwebservices)](http://guardrail-dashboard-515903395012.s3-website.ap-south-1.amazonaws.com)
[![Amazon Bedrock](https://img.shields.io/badge/Bedrock-Converse_toolConfig-violet?style=for-the-badge&logo=amazonbedrock)](https://aws.amazon.com/bedrock/)
[![Track](https://img.shields.io/badge/Track-Ship_It-green?style=for-the-badge)](https://www.wemakedevs.org/aws/first-commit)

---

## 01 / The Problem

Serverless auto-scaling hides runaway loops. An infinite client retry loop, exponential backoff without jitter, unhandled 500 error cascades, or recursive LLM agent loops can generate thousands of requests per second, accumulating catastrophic AWS bills before human operators wake up.

Traditional CloudWatch static alarms (*"if requests > 100/min then alarm"*) create an impossible operational tradeoff:
* **False Positives**: During a legitimate marketing launch or flash sale with 1,000 unique buyers, a static alarm trips and throttles paying customers.
* **Slow Remediation**: By the time an on-call engineer wakes up, reads an SNS email, and manually updates stage throttling, the damage is already done.

**Fuse** solves this by evaluating multi-dimensional context: **caller diversity**, **traffic deltas**, and **deployment heartbeats** using Amazon Bedrock to distinguish between legitimate business surges and destructive single-caller runaway loops in seconds.

---

## 02 / System Architecture

```mermaid
flowchart TD
    subgraph Scheduling
        EB[EventBridge Rate Rule<br/>1-minute cadence]
    end

    subgraph Telemetry Sources
        CW[CloudWatch Metrics<br/>AWS/ApiGateway Count]
        DH[(DynamoDB Deployments<br/>Release Heartbeat Table)]
    end

    subgraph Fuse Core Engine
        Poller[guardrail-poller<br/>Python 3.12 Lambda]
        Reasoner[guardrail-reasoner<br/>Python 3.12 Lambda]
        Bedrock[Amazon Bedrock<br/>Converse API toolConfig]
        IncidentsTable[(DynamoDB<br/>Incidents Table)]
        ApprovalTable[(DynamoDB<br/>ApprovalQueue Table)]
        Remediator[guardrail-remediator<br/>Python 3.12 Lambda]
    end

    subgraph Protected Workloads
        DemoAPI[guardrail-demo-api<br/>API Gateway - poim5xmgs2]
        DemoTarget[guardrail-demo-target<br/>Protected Lambda]
    end

    subgraph Isolated Control Plane
        ControlAPI[guardrail-control-api<br/>API Gateway - agcki2mnvi]
        GetIncidents[guardrail-get-incidents<br/>Lambda]
        ApproveAction[guardrail-approve-action<br/>Lambda]
        Dashboard[Fuse Operator Console<br/>S3 Static Website]
    end

    EB -->|Every 1m| Poller
    Poller -->|Fetch Count Sum| CW
    Poller -->|Check Recent Deploys T-20m| DH
    Poller -->|Invoke Snapshot| Reasoner
    Reasoner -->|Structured Tool Call| Bedrock
    Bedrock -->|Classification & Confidence| Reasoner
    Reasoner -->|Write Outcome| IncidentsTable

    %% Environment Branching
    Reasoner -->|dev / staging: RUNAWAY| Remediator
    Reasoner -->|prod: RUNAWAY| ApprovalTable

    %% Remediation
    Remediator -->|Update Stage RateLimit to 0| DemoAPI
    DemoAPI -->|Invoke| DemoTarget

    %% Control Plane Isolation
    Dashboard -->|GET /incidents| ControlAPI
    Dashboard -->|POST /incidents/{id}/approve| ControlAPI
    ControlAPI --> GetIncidents
    ControlAPI --> ApproveAction
    GetIncidents --> IncidentsTable
    ApproveAction --> Remediator
    ApproveAction --> ApprovalTable
```

---

## 03 / Key Architectural Pillars

### 1. Completely Decoupled Control Plane
Management endpoints (`/incidents`, `/approve`) run on an isolated REST API (`guardrail-control-api`). When `guardrail-demo-api` stage throttling is tripped to 0 rps, the operator console remains 100% responsive and operational.

### 2. Single-Turn Deterministic Bedrock Contract
The Reasoner invokes Amazon Bedrock's **Converse API** exactly once per evaluation cycle using `toolConfig` with schema enforcement (`classify_anomaly`). This forces the model to respond strictly via typed JSON:
* `classification`: `"NORMAL"` or `"RUNAWAY"`
* `confidence`: `0.0 - 1.0`
* `explanation`: Contextual natural language rationale explaining caller concentration and deployment correlation.

### 3. Fail-Closed Cost Safety
If Bedrock encounters network timeouts, regional throttling, or invalid configuration, the reasoner catches the exception and safely defaults to `classification: "RUNAWAY"` (`is_fallback: true`). Cost protection is never compromised by upstream AI failures.

### 4. Human-in-the-Loop Production Safety Gate
* **Development / Staging (`dev`)**: Reasoner triggers `guardrail-remediator` directly (`action_taken: AUTO_THROTTLED`).
* **Production (`prod`)**: Reasoner withholds automated throttling, records the incident in `ApprovalQueue` (`action_taken: PENDING_APPROVAL`), and waits for an engineer to review Bedrock's synthesis on the Fuse Console and click **Approve Circuit Trip**.

### 5. Strict Idempotency
`guardrail-remediator` inspects stage method settings first. If `rateLimit == 0.0` and `burstLimit == 0`, it returns `ALREADY_THROTTLED` as a no-op without duplicate API calls or state mutation.

---

## 04 / Live Verification & Test Scripts

Every script interacts directly with live AWS endpoints and DynamoDB tables in `ap-south-1`:

| Script | Command | Purpose & Expected Verification |
| :--- | :--- | :--- |
| **Naive Comparison** | `python scripts/simulate_naive_threshold.py` | Proves static threshold fails during flash sale while Fuse preserves legitimate traffic. |
| **Scenario 1 (Legit Traffic)** | `python scripts/load_test_legit.py` | 35 requests from 35 unique callers &rarr; Bedrock classifies `NORMAL`. |
| **Scenario 2 (Runaway Loop)** | `python scripts/load_test_runaway.py` | 40 rapid requests from 1 caller &rarr; Bedrock classifies `RUNAWAY` &rarr; prod withheld in `ApprovalQueue`. |
| **Live Web Approval** | Open [Fuse Console](http://guardrail-dashboard-515903395012.s3-website.ap-south-1.amazonaws.com) | Click *Approve Circuit Trip* &rarr; Stage `RateLimit` drops to 0 &rarr; Live Probe confirms `HTTP 429`. |
| **Automated End-to-End** | `python scripts/test_day3_remediation.py` | Automated validation of approval, stage mutation, and curl 429 verification. |
| **Clean Slate Reset** | `python scripts/clear_test_data.py` | Wipes DynamoDB incident records and resets API Gateway stage throttles back to 1000/2000. |

---

## 05 / Deployed AWS Resources (ap-south-1)

| Component | AWS Resource Name | Type / Endpoint |
| :--- | :--- | :--- |
| **Fuse Console** | `guardrail-dashboard-515903395012` | [S3 Static Website](http://guardrail-dashboard-515903395012.s3-website.ap-south-1.amazonaws.com) |
| **Control Plane API** | `guardrail-control-api` (`agcki2mnvi`) | `https://agcki2mnvi.execute-api.ap-south-1.amazonaws.com/prod` |
| **Protected Target API** | `guardrail-demo-api` (`poim5xmgs2`) | `https://poim5xmgs2.execute-api.ap-south-1.amazonaws.com/prod/items` |
| **DynamoDB State** | `Incidents`, `ApprovalQueue`, `Deployments` | Amazon DynamoDB (Pay-per-request) |
| **Sentinel Reasoner** | `guardrail-reasoner` | AWS Lambda (Python 3.12, boto3, Bedrock Converse) |
| **Circuit Remediator** | `guardrail-remediator` | AWS Lambda (Python 3.12, boto3, API Gateway Stage Patch) |
| **Metrics Poller** | `guardrail-poller` | AWS Lambda (Python 3.12, EventBridge 1-min rule) |
| **Approval Endpoint** | `guardrail-approve-action` | AWS Lambda fronted by Control Plane API |
| **Incidents Query** | `guardrail-get-incidents` | AWS Lambda fronted by Control Plane API |

---

## 06 / Hackathon Evaluation Alignment (First Commit)

| Hackathon Criteria | How Fuse Directly Satisfies It |
| :--- | :--- |
| **01 / Idea & Impact** | Solves the silent financial liability of serverless auto-scaling by replacing dumb thresholds with context-aware anomaly detection. |
| **02 / Built on AWS** | Deployed live across 6 native AWS services in `ap-south-1`: Lambda, API Gateway, DynamoDB, Bedrock, CloudWatch, EventBridge, and S3. |
| **03 / Learning** | Mastered Amazon Bedrock Converse API structured tool calling, CloudWatch metric correlation, and isolated control plane architecture. |
| **04 / Execution** | Complete end-to-end working system: live poller, Bedrock classification, approval queue, stage throttle remediation, and responsive dashboard. |
| **05 / Demo Video** | 3-minute scripted demonstration showing live anomaly detection, human approval, and real HTTP 429 stage cutoff. |

---

## 07 / Key Learnings

1. **Structured Tool Calls over Free-Text**: Using Bedrock Converse with `toolConfig` turned an LLM into a reliable, typed microservice with zero JSON parsing failures.
2. **Context Eliminates False Outages**: Correlating deployment heartbeats and unique caller ratios completely solves the false-positive outage problem inherent to static CloudWatch alarms.
3. **Control Plane Isolation is Essential**: Decoupling the management API from the workload API guarantees that an emergency circuit trip never locks the operator out of the control room.

---

## 08 / Project Documentation

* [docs/demo-script.md](docs/demo-script.md) — 3-Minute Video Walkthrough Script
* [docs/blog-post.md](docs/blog-post.md) — AWS Builder Center Technical Article
* [PRD.md](PRD.md) — Product Requirements Document
* [ARCHITECTURE.md](ARCHITECTURE.md) — Architecture & Data Flow Specifications
* [SCHEMA.md](SCHEMA.md) — DynamoDB Table Schemas
* [API.md](API.md) — Internal Interface Contracts
* [TASKS.md](TASKS.md) — Hackathon Build Log & Progress
