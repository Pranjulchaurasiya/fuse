# AWS Cost Guardrail Agent — 3-Minute Demo Video Script

**Track**: Ship It (First Commit — Bharat Builds Tour)  
**Builder**: Pranjul Chaurasiya (Solo, AI-assisted)  
**Target Duration**: 2 minutes 50 seconds (under the 3:00 hard ceiling)

---

## Pre-Video Preparation Checklist
1. **Clean Slate**: Run `python scripts/clear_test_data.py` to wipe DynamoDB test records and restore baseline throttle (1000/2000).
2. **Dashboard Open**: Open the live dashboard in your browser:
   `http://guardrail-dashboard-515903395012.s3-website.ap-south-1.amazonaws.com`
3. **Terminal Open**: Split screen with browser on the left, terminal on the right.

---

## Timing Breakdown

```
0:00 - 0:30  | ACT 1: The Problem — Why Static Alarms Fail (30s)
0:30 - 1:15  | ACT 2: Scenario 1 — Legitimate Spike (Flash Sale) (45s)
1:15 - 2:15  | ACT 3: Scenario 2 — Runaway Loop & Human Approval Gate (60s)
2:15 - 2:45  | ACT 4: Under the Hood — Architecture & Single-Turn Bedrock (30s)
2:45 - 3:00  | ACT 5: Conclusion & Links (15s)
```

---

## Detailed Cue-by-Cue Script

### ACT 1: The Problem (0:00 – 0:30)

**[Screen]**: Show terminal running `python scripts/simulate_naive_threshold.py`.

**[Voiceover]**:
> "Serverless architecture is incredible until an infinite client retry loop racks up a surprise $5,000 AWS bill overnight. 
> 
> Traditional CloudWatch alarms only look at raw numbers—if requests exceed 30 per minute, they fire. But look at this simulation: during a flash sale with 35 real buyers, a static threshold breaks production for paying customers—a false positive. Yet during an actual runaway loop, it doesn't give you context or safe remediation.
> 
> Meet **AWS Cost Guardrail Agent**—an autonomous, context-aware circuit breaker powered by Amazon Bedrock."

---

### ACT 2: Scenario 1 — Legitimate Spike (0:30 – 1:15)

**[Screen]**: Run `python scripts/load_test_legit.py` in the terminal.

**[Voiceover]**:
> "Let's test Scenario 1: A legitimate marketing spike. 
> 
> We fire 35 requests into our demo API Gateway endpoint. Notice each request originates from a unique IP and caller ID, carrying varied search and shopping payloads.
> 
> Every minute, an EventBridge schedule triggers our lightweight Poller Lambda. It queries CloudWatch metrics and checks DynamoDB for recent deployment heartbeats. 
> 
> When Bedrock evaluates this cycle, it examines caller diversity and recent deploy context. Let's switch to our live dashboard..."

**[Screen]**: Browser showing incident feed auto-updating. The new green card appears.

**[Voiceover]**:
> "Boom! Bedrock classifies the traffic as **NORMAL** with 98% confidence: *'Spike consists of 35 distinct callers with diverse queries.'* Zero disruption, zero false alarm."

---

### ACT 3: Scenario 2 — Runaway Loop & Human Approval Gate (1:15 – 2:15)

**[Screen]**: Run `python scripts/load_test_runaway.py` in the terminal.

**[Voiceover]**:
> "Now, Scenario 2: A developer deploys a buggy client that enters a recursive infinite retry loop. 
> 
> Here we send 40 rapid requests—all from a single caller ID with identical stuck payloads.
> 
> Our Poller detects the volume spike and passes the snapshot to our Reasoner Lambda. Bedrock's Converse API immediately identifies the anomaly signature as **RUNAWAY**."

**[Screen]**: Switch to Dashboard. A prominent card appears with an amber pulsing dot and badge `[PENDING HUMAN APPROVAL]`.

**[Voiceover]**:
> "Because this is our production workload, our safety guardrail **withholds automated throttling**. In dev or staging, it auto-throttles instantly. In prod, human judgement is protected.
> 
> Notice the demo API is still responding normally right now. But as an operator, I see Bedrock's explanation: *'Single caller, identical retry payload, no deployment event.'*
> 
> I click **Approve Throttle**..."

**[Action]**: Click the **Approve Throttle** button in the dashboard. Button shows spinner, then transitions to `✓ Approved & Throttled`.

**[Screen]**: Switch to terminal and run `curl.exe -i https://poim5xmgs2.execute-api.ap-south-1.amazonaws.com/prod/items`.

**[Voiceover]**:
> "Our Remediator Lambda instantly patches the API Gateway stage throttle to 0. 
> 
> Let's test the live endpoint: **HTTP 429 Too Many Requests**. The runaway loop is severed before the bill can multiply!"

---

### ACT 4: Under the Hood (2:15 – 2:45)

**[Screen]**: Show [ARCHITECTURE.md](file:///c:/Users/pranj/Documents/Fuse/ARCHITECTURE.md) diagram or GitHub repository.

**[Voiceover]**:
> "Here's what makes this architecture production-grade:
> 
> 1. **Isolated Control Plane**: The dashboard and approval endpoints live on a completely separate API Gateway from the protected workload. Throttling the demo API never bricks our operator console.
> 2. **Single-Turn Structured Bedrock**: We invoke Bedrock Converse exactly once per cycle using toolConfig, returning strict JSON (`classification`, `confidence`, `explanation`). No expensive agent loops.
> 3. **Fail-Closed Fallback**: If Bedrock ever times out or has a network glitch, our reasoner safely defaults to RUNAWAY—guaranteeing cost protection."

---

### ACT 5: Conclusion & Links (2:45 – 3:00)

**[Screen]**: Display GitHub repo (`github.com/Pranjulchaurasiya/fuse`) and live S3 dashboard URL.

**[Voiceover]**:
> "AWS Cost Guardrail turns cloud cost protection from dumb static alarms into intelligent, context-aware circuit breakers.
> 
> The code, architecture docs, and live dashboard are available on GitHub. Thank you!"

---

## Commands Summary for the Demo
```bash
# 1. Clean slate before recording
python scripts/clear_test_data.py

# 2. Naive vs Guardrail comparison pitch
python scripts/simulate_naive_threshold.py

# 3. Scenario 1 (Legitimate)
python scripts/load_test_legit.py

# 4. Scenario 2 (Runaway)
python scripts/load_test_runaway.py

# 5. Verify throttled endpoint after clicking Approve in Dashboard
curl.exe -i https://poim5xmgs2.execute-api.ap-south-1.amazonaws.com/prod/items

# 6. Reset throttle after recording
python scripts/clear_test_data.py
```
