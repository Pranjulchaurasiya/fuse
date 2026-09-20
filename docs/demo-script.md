# Fuse — AWS Cost Guardrail & Circuit Breaker
## 3-Minute Demo Video Script

**Project**: **Fuse**  
**Event**: First Commit — Bharat Builds Tour (WeMakeDevs &times; AWS)  
**Track**: Ship It (First Prize) & Best UI  
**Team Code**: `ZK2FP6`  
**Builder**: Pranjul Chaurasiya (`@pranjul_chaurasiya`, Solo)  
**Target Duration**: 2 minutes 45 seconds (Strictly under the 3:00 hard ceiling)  
**Live Console**: `https://main.d1hndpgpwb40h8.amplifyapp.com`  
**YouTube Video**: [https://youtu.be/UWzPBdO63ek](https://youtu.be/UWzPBdO63ek)  
**GitHub**: `https://github.com/Pranjulchaurasiya/fuse`

---

## Pre-Video Preparation Checklist
1. **Clean Slate**: Run `python scripts/clear_test_data.py` to wipe DynamoDB test records and restore baseline throttle (1000/2000).
2. **Dashboard Open**: Open the live dashboard in your browser:
   `https://main.d1hndpgpwb40h8.amplifyapp.com`
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
> "Hi everyone, I'm Pranjul Chaurasiya, and this is Fuse.
> 
> Serverless architecture is incredible until an infinite client retry loop or runaway agent racks up a surprise $5,000 AWS bill overnight. You don't find out until your billing alarm emails you at 3 AM.
> 
> Look at this comparison: Traditional CloudWatch static alarms only count raw requests. During a marketing flash sale with 1,000 real buyers, a static alarm trips and kills paying customers—a catastrophic false-positive outage. But during a real runaway loop, it offers zero caller context and zero automated remediation.
> 
> Meet **Fuse**—an autonomous, context-aware circuit breaker for AWS APIs powered by Amazon Bedrock."

---

### ACT 2: Scenario 1 — Legitimate Spike (0:30 – 1:15)

**[Screen]**: Run `python scripts/load_test_legit.py` in the terminal.

**[Voiceover]**:
> "Let's test Scenario 1: A legitimate traffic surge.
> 
> We fire 35 requests into our demo API Gateway endpoint. Notice each request originates from a unique IP and caller ID, carrying diverse search and catalog payloads.
> 
> Every minute, an EventBridge schedule triggers our lightweight Poller Lambda. It queries CloudWatch metrics and checks DynamoDB for recent deployment heartbeats.
> 
> When Bedrock evaluates this cycle, it correlates caller diversity with deployment context. Let's switch to our live Fuse Console..."

**[Screen]**: Browser showing incident feed auto-updating. The new card appears with `[NORMAL]`.

**[Voiceover]**:
> "Bedrock classifies the traffic as **NORMAL** with 98% confidence: *'Traffic surge consists of distinct callers with diverse payloads.'* Baseline stays intact, zero false alarm, zero customer disruption."

---

### ACT 3: Scenario 2 — Runaway Loop & Human Approval Gate (1:15 – 2:15)

**[Screen]**: Run `python scripts/load_test_runaway.py` in the terminal.

**[Voiceover]**:
> "Now, Scenario 2: A developer deploys a client with an unhandled retry loop without backoff jitter.
> 
> We fire 40 rapid requests—all from a single caller ID with identical stuck payloads.
> 
> Our Poller detects the volume spike and passes the snapshot to our Reasoner Lambda. Bedrock's Converse API immediately identifies the anomaly signature as **RUNAWAY**."

**[Screen]**: Switch to Dashboard. An incident card appears with `[RUNAWAY]` and status `AWAITING APPROVAL // PRODUCTION SAFETY GATE`.

**[Voiceover]**:
> "Because this is our production workload, our safety guardrail **withholds automated throttling**. In dev or staging, it auto-throttles directly. In production, human judgment is protected.
> 
> The target API is still serving traffic right now. As the operator, I inspect Bedrock's synthesis: *'Single caller, identical retry payload, no deployment event.'*
> 
> I click **Approve Circuit Trip**..."

**[Action]**: Click the **Approve Circuit Trip — Set RateLimit to 0** button in the dashboard. Card transitions to `APPROVED & THROTTLED`.

**[Screen]**: Click **Probe Target API Now** in the dashboard sidebar, and verify `HTTP 429 Too Many Requests`. Also show terminal running `curl.exe -i https://poim5xmgs2.execute-api.ap-south-1.amazonaws.com/prod/items`.

**[Voiceover]**:
> "Our Remediator Lambda immediately patches the API Gateway stage throttle to 0.
> 
> We follow the independent observation principle: we verify the throttle directly at the regional API Gateway edge. Both our live probe and raw curl confirm: **HTTP 429 Too Many Requests**. The runaway loop is severed before the bill can multiply!"

---

### ACT 4: Under the Hood (2:15 – 2:45)

**[Screen]**: Show [ARCHITECTURE.md](file:///c:/Users/pranj/Documents/Fuse/ARCHITECTURE.md) diagram or GitHub repository.

**[Voiceover]**:
> "Here's what makes Fuse production-grade:
> 
> 1. **Isolated Control Plane**: The dashboard and approval endpoints run on a completely separate API Gateway. Throttling the demo workload never locks the operator out of the control room.
> 2. **Single-Turn Structured Bedrock**: We invoke Bedrock Converse exactly once per cycle using toolConfig, enforcing typed JSON without expensive multi-turn loops.
> 3. **Fail-Closed Cost Safety**: If Bedrock ever times out, our reasoner safely defaults to RUNAWAY—guaranteeing cost protection is never compromised."

---

### ACT 5: Conclusion & Links (2:45 – 3:00)

**[Screen]**: Display GitHub repo (`github.com/Pranjulchaurasiya/fuse`) and live S3 dashboard URL.

**[Voiceover]**:
> "Fuse transforms cloud cost governance from brittle static alarms into intelligent, context-aware circuit breakers.
> 
> Deployed live on AWS in ap-south-1. I'm Pranjul Chaurasiya, submitting for the Ship It track at First Commit, Bharat Builds Tour 2026. The code, architecture docs, and live console are available on GitHub. Thank you!"

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
