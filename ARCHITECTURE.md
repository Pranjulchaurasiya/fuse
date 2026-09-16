# ARCHITECTURE.md — AWS Cost Guardrail Agent

## Data flow

```
[EventBridge: rate(1 minute)]
          |
          v
[Lambda: poller]
   - cloudwatch.get_metric_data("AWS/ApiGateway", "Count")
   - reads Deployments table (heartbeat check)
   - computes unique-caller count from recent access logs (API key/IP)
   - if delta vs rolling baseline exceeds threshold -> trigger reasoner
          |
          v
[Lambda: reasoner]
   - builds structured context payload (metrics + deploy heartbeat +
     unique-caller ratio + sample of repeated request payloads)
   - single Bedrock InvokeModel call (Claude 3.5 Haiku)
   - parses classification: NORMAL | RUNAWAY
   - writes result to Incidents table
          |
          v
   NORMAL -> log only, no action
   RUNAWAY -> [Lambda: remediator]
          |
          +-- resource tagged dev/staging -> throttle immediately
          |
          +-- resource tagged prod -> write ApprovalQueue entry,
                                       wait for human approval via API Gateway
                                       endpoint, THEN throttle
          |
          v
[DynamoDB: Incidents] <- every detection cycle writes a record here,
                          regardless of outcome (for the dashboard)
```

## AWS services and their single responsibility

| Service | Responsibility |
|---|---|
| EventBridge | Fires the poller Lambda every 1 minute |
| Lambda (poller) | Pulls metrics, checks deploy heartbeat, decides if reasoning is needed |
| Lambda (reasoner) | Single Bedrock call, classification only |
| Lambda (remediator) | Executes the one allowed action: API Gateway stage throttle |
| Lambda (approve-action) | Handles the human-approval API call, flips ApprovalQueue status |
| Lambda (get-incidents) | Serves incident log JSON to the dashboard |
| DynamoDB | Three tables: Deployments, Incidents, ApprovalQueue |
| API Gateway | Fronts approve-action and get-incidents; is also the resource being
throttled (the demo's "protected" API) |
| Bedrock | Reasoning step only — classification + explanation string |
| S3 / Amplify Hosting | Static dashboard frontend |

## Folder structure

```
cost-guardrail/
├── AGENTS.md
├── PRD.md
├── ARCHITECTURE.md
├── SCHEMA.md
├── API.md
├── TASKS.md
├── DESIGN.md
├── TESTING.md
├── DEPLOY.md
├── infra/
│   ├── iam-policies/
│   │   ├── poller-role.json
│   │   ├── reasoner-role.json
│   │   └── remediator-role.json
│   └── setup-notes.md          # manual console steps taken (no CDK/Terraform)
├── lambdas/
│   ├── poller/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── reasoner/
│   │   ├── handler.py
│   │   ├── prompt_template.py
│   │   └── requirements.txt
│   ├── remediator/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── approve_action/
│   │   └── handler.py
│   └── get_incidents/
│       └── handler.py
├── scripts/
│   ├── deploy_heartbeat.py     # called at end of "deploy" step
│   ├── load_test_legit.py      # scenario 1 & 2: many unique callers
│   └── load_test_runaway.py    # scenario 3: repeated identical payload
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
└── docs/
    └── demo-script.md
```

## Why five Lambdas, not one
Each maps to a distinct IAM permission boundary (poller only reads metrics;
remediator is the only one allowed to write API Gateway throttle settings).
Keeping them separate makes the "blast radius" containment from the
architecture review real, not just a talking point in the demo video.
