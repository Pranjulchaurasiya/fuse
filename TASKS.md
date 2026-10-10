# 🚀 Fuse SaaS Product Roadmap & Task Ledger

This tracking ledger outlines the production milestones required to transition **Fuse** from an advanced, dual-mode backend repository into a highly scalable, commercial Multi-Tenant FinOps SaaS platform.

---

## 🟩 Phase 1: Core Algorithmic Architecture (100% COMPLETE)
- [x] **Deterministic Statistical Pre-Filter:** Built moving Z-score and sample standard deviation metrics filters into the poller to terminate safe cycles in <50ms.
- [x] **Cognitive AI Reasoner Upgrade:** Enforced strict JSON compliance via the `classify_anomaly` tool constraint contract using Amazon Bedrock Converse API.
- [x] **Secure Cross-Account Identity Handshake:** Authored 1-click customer onboarding CloudFormation templates utilizing cryptographic `sts:ExternalId` properties to block the Confused Deputy vulnerability.
- [x] **Idempotent Dual-Mode Remediator:** Engineered a safe containment actuator that handles multi-tenant cross-account API throttling while maintaining a fallback mode for local hackathon demo evaluations.
- [x] **AST Architecture Validation:** Refreshed knowledge graph topologies (`graphify update .`) confirming compilation safety across all components.

---

## 🟩 Phase 2: Backend SaaS Loop Automation (100% COMPLETE)
*Objective: Transition the engine from checking single environment targets to processing batch metrics loops for all global platform tenants concurrent.*

- [x] **Database Scan Routine Integration:** Built dynamic `get_active_tenants()` scan operation against `Fuse_Tenants` table with fallback to local single-target demo mode.
- [x] **Multi-Threaded Tenant Evaluation:** Implemented `concurrent.futures.ThreadPoolExecutor` into `lambdas/poller/handler.py` to evaluate telemetry across multiple tenant accounts concurrently.
- [x] **Dynamic Anomaly Handoff:** Routed `tenant_id` alongside context vectors and metric snapshots directly to `guardrail-reasoner` and `remediator`.

---

## 🔲 Phase 3: Interactive Engagement & Incident Lifecycles
*Objective: Build out the operational Human-in-the-Loop workflows for production monitoring.*

- [ ] **Slack Block Kit Hook Interceptor:** Implement the `lambdas/slack_bot/handler.py` engine to parse URLs, verify cryptographic signatures, and interface directly with user interface components.
- [ ] **Remediator Webhook Callback Route:** Configure the API Gateway HTTP API routes (`POST /slack/interactivity`) via Terraform variables to link Slack interactivity blocks with the master control plane.
- [ ] **Audit State Tracking:** Update the `action_taken` attribute inside `Fuse_Tenant_Incidents` whenever a human operator triggers an `AUTO_THROTTLED` or `DISMISSED` state from their chat environment.

---

## 🔲 Phase 4: Customer Dashboard Console & Web Interface
*Objective: Design a clean web dashboard for client onboarding and real-time cost visualization.*

- [ ] **Next.js Portal Setup:** Generate the SaaS web project boilerplate using standard corporate design frameworks.
- [ ] **REST API Control Plane Contract:** Build lightweight management APIs (`/api/tenants`, `/api/incidents`) to feed records out of DynamoDB into the frontend securely.
- [ ] **Onboarding On-Screen Visuals:** Create the client registration wizard that shows users their unique `ExternalId` token string and provides the direct 1-click AWS CloudFormation setup button.
- [ ] **Metrics Dashboard:** Design graphs to let users visually see their current API traffic counts, moving baseline averages, and active alert state histories.

---

## 🔲 Phase 5: Long-Term Enterprise Governance Extensions
*Objective: Expand protection vectors past API Gateway to catch multi-resource infrastructure leaks.*

- [x] **AWS WAF Edge Block Integration:** Implemented in `lambdas/remediator/handler.py` (`handle_waf_action`). Dynamically mutates AWS WAF IP Set (`fuse-blocked-ips`) with optimistic lock retries and rate-based emergency burst cap.
- [ ] **AWS Lambda Recursion Protection:** Build pluggable remediation functions to set target function reserve concurrency parameters to zero if an unhandled backend loop occurs.
