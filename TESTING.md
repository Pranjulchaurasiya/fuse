# TESTING.md — Test strategy & acceptance matrix

No automated test suite is required for a 4-day hackathon build — manual,
scripted verification is sufficient and faster. This document defines what
"working" means for each piece, so Day 4 has a clear go/no-go checklist
instead of vague confidence.

## Acceptance matrix

| # | Scenario | Trigger | Expected result | Verified? |
|---|---|---|---|---|
| 1 | Baseline idle | No load | Poller logs low, stable metrics; no incident created | ☐ |
| 2 | Legitimate spike | `load_test_legit.py` (many unique callers, varied payloads) + heartbeat written just before | Incidents table logs `NORMAL`; no throttle | ☐ |
| 3 | Runaway loop | `load_test_runaway.py` (1–3 callers, identical payload, no heartbeat) | Incidents table logs `RUNAWAY` | ☐ |
| 4 | Runaway in dev/staging | Scenario 3, resource tagged `dev` | Auto-throttled within 1–2 poll cycles, `action_taken: AUTO_THROTTLED` | ☐ |
| 5 | Runaway in prod | Scenario 3, resource tagged `prod` | `PENDING_APPROVAL` written, NOT throttled yet | ☐ |
| 6 | Approval flow | `POST /incidents/{id}/approve` with `APPROVED` | Throttle applied, status → `APPROVED_AND_THROTTLED` | ☐ |
| 7 | Rejection flow | `POST /incidents/{id}/approve` with `REJECTED` | Incident marked resolved, no throttle applied | ☐ |
| 8 | Static-rule false positive (demo prop) | Naive threshold script vs. scenario 2 traffic | Static rule fires and would throttle; Bedrock does not | ☐ |
| 9 | Idempotent remediation | Call remediator Lambda twice on the same incident | Second call is a no-op, no error, `ALREADY_THROTTLED` | ☐ |
| 10 | Bedrock parse failure | Malformed/unexpected model output (simulate by truncating response) | System fails closed: treated as `RUNAWAY`, flagged for manual review, never silently ignored | ☐ |
| 11 | Dashboard load | Open dashboard URL fresh | Incident list renders, matches DynamoDB contents | ☐ |
| 12 | End-to-end cold start | Fresh deploy, no prior state | Full pipeline runs without relying on leftover test data | ☐ |

## Test data hygiene
Before recording the final demo video (Day 4), wipe the `Incidents` and
`ApprovalQueue` tables and re-run the three demo scenarios clean. A dashboard
full of earlier debugging noise undermines the pitch.

## What is explicitly not tested
- Load beyond what the three demo scripts generate — this is not a
  production load-test exercise
- Multi-region behavior — single region only (pick one, stay consistent
  across all services)
- Security penetration testing of the approval endpoint — acceptable risk
  for a hackathon demo; note as a known limitation in the README, mirroring
  how Mayday's writeup was upfront about what wasn't hardened
