# AWS Cost Guardrail Agent ("Guardrail")

> **An autonomous, context-aware circuit breaker for serverless APIs powered by Amazon Bedrock, EventBridge, and DynamoDB.**  
> Built for the **First Commit — Bharat Builds Tour (Ship It Track)** by Pranjul Chaurasiya.

[![Live Dashboard](https://img.shields.io/badge/Live_Dashboard-S3_Website-blue?style=for-the-badge&logo=amazons3)](http://guardrail-dashboard-515903395012.s3-website.ap-south-1.amazonaws.com)
[![AWS Region](https://img.shields.io/badge/Region-ap--south--1_(Mumbai)-orange?style=for-the-badge&logo=amazonwebservices)](http://guardrail-dashboard-515903395012.s3-website.ap-south-1.amazonaws.com)
[![Amazon Bedrock](https://img.shields.io/badge/Bedrock-Converse_API-violet?style=for-the-badge&logo=amazondynamodb)](https://aws.amazon.com/bedrock/)

---

## 🎯 The Problem

Serverless computing scales seamlessly, but unbounded scalability creates **financial liability**. An infinite client retry loop, exponential backoff without jitter, or a recursive microservice call can generate millions of requests and thousands of dollars in surprise bills overnight.

Traditional CloudWatch static alarms (*"if requests > 100/min then alert"*) create a painful dilemma:
* **False Positives**: During a legitimate flash sale with 1,000 unique buyers, a static alarm trips and throttles paying customers.
* **Slow Remediation**: By the time an on-call engineer wakes up and inspects the logs, the damage is already done.

**AWS Cost Guardrail Agent** solves this by evaluating multi-dimensional context: **caller diversity**, **payload variance**, and **deployment heartbeats** using Amazon Bedrock to distinguish between legitimate business surges and destructive runaway loops.

---

## 🏗 System Architecture

```mermaid
flowchart TD
    subgraph Scheduling
        EB[EventBridge Schedule<br/>1-minute rate]
    end

    subgraph Data Sources
        CW[CloudWatch Metrics<br/>& Target Lambda Logs]
        DH[DynamoDB<br/>Deployments Heartbeat]
    end

    subgraph Core Guardrail Engine
        Poller[guardrail-poller<br/>Lambda]
        Reasoner[guardrail-reasoner<br/>Lambda]
        Bedrock[Amazon Bedrock<br/>Converse API - Nova Micro]
        IncidentsTable[(DynamoDB<br/>Incidents Table)]
        ApprovalTable[(DynamoDB<br/>ApprovalQueue Table)]
        Remediator[guardrail-remediator<br/>Lambda]
    end

    subgraph Workloads
        DemoAPI[guardrail-demo-api<br/>API Gateway - poim5xmgs2]
        DemoTarget[guardrail-demo-target<br/>Protected Lambda]
    end

    subgraph Control Plane
        ControlAPI[guardrail-control-api<br/>API Gateway - agcki2mnvi]
        GetIncidents[guardrail-get-incidents<br/>Lambda]
        ApproveAction[guardrail-approve-action<br/>Lambda]
        Dashboard[Operator Console<br/>S3 Static Website]
    end

    EB -->|Every 1m| Poller
    Poller -->|Fetch Count| CW
    Poller -->|Check Recent Releases| DH
    Poller -->|Invoke Snapshot| Reasoner
    Reasoner -->|Structured Tool Call| Bedrock
    Bedrock -->|Classification & Confidence| Reasoner
    Reasoner -->|Write Outcome| IncidentsTable

    %% Branching
    Reasoner -->|dev/staging RUNAWAY| Remediator
    Reasoner -->|prod RUNAWAY| ApprovalTable

    %% Remediation
    Remediator -->|Update Stage RateLimit to 0| DemoAPI
    DemoAPI -->|Invoke| DemoTarget

    %% Control Plane Isolation
    Dashboard -->|GET /incidents| ControlAPI
    Dashboard -->|POST /approve| ControlAPI
    ControlAPI --> GetIncidents
    ControlAPI --> ApproveAction
    GetIncidents --> IncidentsTable
    ApproveAction --> Remediator
    ApproveAction --> ApprovalTable
```

---

## ⚡ Key Architectural Features

### 1. Isolated Control Plane
Management endpoints (`/incidents`, `/approve`) live on a dedicated REST API (`guardrail-control-api`). When `guardrail-demo-api` is throttled to 0 rps, the operator dashboard remains 100% accessible.

### 2. Single-Turn Deterministic Bedrock Contract
The Reasoner calls Amazon Bedrock's **Converse API** exactly once per cycle using `toolConfig` (`classify_anomaly`). This forces the model to respond strictly via JSON:
* `classification`: `"NORMAL"` or `"RUNAWAY"`
* `confidence`: `0.0 - 1.0`
* `explanation`: 1-2 sentence human-readable rationale.

### 3. Fail-Closed Cost Safety
If Bedrock encounters network timeouts, rate limits, or invalid model configuration, the reasoner catches the exception and safely defaults to `classification: "RUNAWAY"` (`is_fallback: true`) to ensure cost protection is never compromised.

### 4. Human-in-the-Loop Approval Gate for Production
* **Non-prod (`dev`, `staging`)**: Reasoner triggers `guardrail-remediator` immediately (`action_taken: AUTO_THROTTLED`).
* **Prod (`prod`)**: Reasoner withholds automated action, writes to `ApprovalQueue` (`status: PENDING`), and waits for an engineer to review Bedrock's rationale and click **Approve Throttle**.

### 5. Strict Idempotency
`guardrail-remediator` reads stage settings first. If `rateLimit == 0.0`, it returns `ALREADY_THROTTLED` without throwing errors or redundant AWS API calls.

---

## 📊 Live Verification & Demo Scripts

All verification scripts use real AWS APIs, real HTTP requests, and real DynamoDB records:

| Script | Purpose | Expected Outcome |
|---|---|---|
| [`scripts/simulate_naive_threshold.py`](scripts/simulate_naive_threshold.py) | Compares static threshold vs Guardrail | Demonstrates false-positive elimination |
| [`scripts/load_test_legit.py`](scripts/load_test_legit.py) | Fires 35 requests from 35 unique callers | Bedrock classifies **NORMAL** (No action) |
| [`scripts/load_test_runaway.py`](scripts/load_test_runaway.py) | Fires 40 rapid requests from 1 caller | Bedrock classifies **RUNAWAY** (Approval required) |
| [`scripts/clear_test_data.py`](scripts/clear_test_data.py) | Resets tables & restores baseline throttle | Clean slate for demo recording |
| [`scripts/test_day3_remediation.py`](scripts/test_day3_remediation.py) | Full automated end-to-end test suite | Verifies 429 response upon throttle |

---

## 🚀 Deployed Resources (ap-south-1)

* **Operator Dashboard**: [http://guardrail-dashboard-515903395012.s3-website.ap-south-1.amazonaws.com](http://guardrail-dashboard-515903395012.s3-website.ap-south-1.amazonaws.com)
* **Control Plane API**: `https://agcki2mnvi.execute-api.ap-south-1.amazonaws.com/prod`
* **Protected Demo API**: `https://poim5xmgs2.execute-api.ap-south-1.amazonaws.com/prod/items`
* **DynamoDB Tables**: `Deployments`, `Incidents`, `ApprovalQueue`
* **Lambda Functions**: `guardrail-poller`, `guardrail-reasoner`, `guardrail-remediator`, `guardrail-approve-action`, `guardrail-get-incidents`, `guardrail-demo-target`

---

## 💡 What We Learned

1. **Structured Tool Calls over Free-Text**: Using Bedrock Converse with `toolChoice` turned an LLM into a reliable, typed microservice with zero parsing errors.
2. **Context Prevents False Outages**: Adding a simple deployment heartbeat table and unique caller analysis completely solved the false positive dilemma of static CloudWatch alarms.
3. **Control Plane Isolation is Non-Negotiable**: Decoupling the management API from the workload API ensured that an emergency brake never trapped the operator outside the control room.

---

## 📄 Documentation

* [PRD.md](PRD.md) — Product Requirements Document
* [ARCHITECTURE.md](ARCHITECTURE.md) — Architecture & Data Flow
* [SCHEMA.md](SCHEMA.md) — DynamoDB Table Schemas
* [API.md](API.md) — Internal Contracts & Interfaces
* [DESIGN.md](DESIGN.md) — UI Tokens & States
* [docs/demo-script.md](docs/demo-script.md) — 3-Minute Video Walkthrough Script
* [docs/blog-post.md](docs/blog-post.md) — AWS Builder Center Technical Article
* [TASKS.md](TASKS.md) — Day-by-Day Hackathon Progress
