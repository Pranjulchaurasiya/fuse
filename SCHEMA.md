# SCHEMA.md — DynamoDB tables

Three tables total. All on-demand billing mode (no capacity planning needed
for a hackathon-scale demo).

## 1. `Deployments`
Heartbeat table — written once by the deploy script, read by the poller to
check "did something just ship."

| Attribute | Type | Notes |
|---|---|---|
| `deployment_id` (PK) | String | UUID |
| `timestamp` | Number | Unix epoch, seconds |
| `resource` | String | e.g. `"guardrail-demo-api"` |
| `note` | String | free text, e.g. `"v1.4.2 deploy"` |

Query pattern: poller does a `Scan` filtered on `timestamp > now - 900`
(last 15 minutes). Table stays tiny for a hackathon demo — no GSI needed.

## 2. `Incidents`
Written on every detection cycle, whether or not it escalates. This is the
table the dashboard reads.

| Attribute | Type | Notes |
|---|---|---|
| `incident_id` (PK) | String | UUID |
| `timestamp` | Number | Unix epoch |
| `resource` | String | which API Gateway stage was evaluated |
| `metric_snapshot` | Map | `{ count, unique_callers, baseline }` |
| `deploy_context` | Map | `{ recent_deploy: bool, note }` |
| `classification` | String | `NORMAL` \| `RUNAWAY` |
| `bedrock_explanation` | String | raw text from the reasoning call |
| `action_taken` | String | `NONE` \| `AUTO_THROTTLED` \| `PENDING_APPROVAL` \| `APPROVED_AND_THROTTLED` |
| `environment` | String | `dev` \| `staging` \| `prod` |

GSI: `environment-timestamp-index` (PK `environment`, SK `timestamp`) — lets
the dashboard filter by environment without a full scan.

## 3. `ApprovalQueue`
Only populated for `prod`-tagged incidents classified `RUNAWAY`.

| Attribute | Type | Notes |
|---|---|---|
| `approval_id` (PK) | String | UUID, matches an `incident_id` |
| `status` | String | `PENDING` \| `APPROVED` \| `REJECTED` |
| `created_at` | Number | Unix epoch |
| `resolved_at` | Number | Unix epoch, null until acted on |
| `resolved_by` | String | free text — who clicked approve (no auth system, just a name field for the demo) |

## Access patterns summary
| Need | Table | Method |
|---|---|---|
| Was there a recent deploy? | Deployments | Scan, filter by timestamp |
| Log a detection cycle | Incidents | PutItem |
| List incidents for dashboard | Incidents | Query on GSI, or Scan (fine at demo scale) |
| Check approval status | ApprovalQueue | GetItem by `approval_id` |
| Approve/reject an incident | ApprovalQueue | UpdateItem |
