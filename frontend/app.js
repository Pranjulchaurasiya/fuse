/**
 * app.js — Terminal Incident Response Stream Controller
 * Connects directly to AWS Cost Guardrail Control Plane API (ap-south-1)
 */

const CONTROL_API_BASE = "https://agcki2mnvi.execute-api.ap-south-1.amazonaws.com/prod";
let allIncidents = [];
let autoRefreshTimer = null;
const POLL_INTERVAL_MS = 6000;

// DOM Elements
const container = document.getElementById("incidents-container");
const metricTotal = document.getElementById("metric-total");
const metricRunaways = document.getElementById("metric-runaways");
const metricPending = document.getElementById("metric-pending");
const metricThrottled = document.getElementById("metric-throttled");
const feedCount = document.getElementById("feed-count");
const envFilter = document.getElementById("env-filter");
const refreshBtn = document.getElementById("refresh-btn");

/**
 * Formats epoch timestamp into clean terminal time string.
 */
function formatTimestamp(epochSec) {
  if (!epochSec) return "[--:--:--]";
  const date = new Date(Number(epochSec) * 1000);
  return `[${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })}]`;
}

/**
 * Formats date into relative time string (e.g. '2m ago').
 */
function formatRelativeTime(epochSec) {
  if (!epochSec) return "";
  const diffSec = Math.floor(Date.now() / 1000 - Number(epochSec));
  if (diffSec < 60) return `-${Math.max(1, diffSec)}s`;
  if (diffSec < 3600) return `-${Math.floor(diffSec / 60)}m`;
  return `-${Math.floor(diffSec / 3600)}h`;
}

/**
 * Fetches latest incidents from Control Plane API.
 */
async function fetchIncidents() {
  if (refreshBtn) refreshBtn.classList.add("loading");
  try {
    const res = await fetch(`${CONTROL_API_BASE}/incidents?limit=50`, {
      method: "GET",
      headers: { "Accept": "application/json" }
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }

    const data = await res.json();
    allIncidents = data.incidents || [];
    updateMetrics(allIncidents);
    renderFeed();
  } catch (err) {
    console.error("Failed to fetch incidents:", err);
    if (allIncidents.length === 0) {
      container.innerHTML = `
        <div class="terminal-empty">
          <p style="color: var(--accent-amber);">[ERROR] CONTROL_PLANE_UNREACHABLE: ${escapeHtml(err.message)}</p>
          <button class="terminal-btn" onclick="fetchIncidents()" style="margin-top: 10px;">[RETRY_CONNECTION]</button>
        </div>
      `;
    }
  } finally {
    if (refreshBtn) refreshBtn.classList.remove("loading");
  }
}

/**
 * Computes metrics scorecard strictly from real DynamoDB Incidents records.
 */
function updateMetrics(incidents) {
  const total = incidents.length;
  const runaways = incidents.filter(i => i.classification === "RUNAWAY").length;
  const pending = incidents.filter(i => i.action_taken === "PENDING_APPROVAL").length;
  const throttled = incidents.filter(i => 
    i.action_taken === "AUTO_THROTTLED" || i.action_taken === "APPROVED_AND_THROTTLED"
  ).length;

  if (metricTotal) metricTotal.textContent = total;
  if (metricRunaways) metricRunaways.textContent = runaways;
  if (metricPending) metricPending.textContent = pending;
  if (metricThrottled) metricThrottled.textContent = throttled;
}

/**
 * Renders the timeline feed based on current environment filter.
 */
function renderFeed() {
  const filterVal = envFilter.value;
  const filtered = allIncidents.filter(inc => {
    if (filterVal === "all") return true;
    const env = (inc.environment || "prod").toLowerCase();
    return env === filterVal.toLowerCase();
  });

  if (feedCount) feedCount.textContent = `COUNT: ${filtered.length} ENTRIES`;

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="terminal-empty">
        <p>&gt; NO INCIDENTS RECORDED FOR STAGE [${escapeHtml(filterVal).toUpperCase()}]</p>
        <span style="font-size: 11px; color: var(--text-subtle);">Run load_test_runaway.py or await the next 1-min EventBridge cycle.</span>
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map(inc => renderTimelineEntry(inc)).join("");
}

/**
 * Generates HTML for a single vertical timeline entry.
 */
function renderTimelineEntry(inc) {
  const isRunaway = inc.classification === "RUNAWAY";
  const isPending = inc.action_taken === "PENDING_APPROVAL";
  const stage = (inc.environment || "prod").toUpperCase();
  const entryClass = isPending ? "timeline-entry entry-pending" : "timeline-entry";
  
  const snapshot = inc.metric_snapshot || {};
  const callers = snapshot.unique_callers ?? "N/A";
  const count = snapshot.count ?? "0";
  const delta = snapshot.delta ?? "0";
  const baseline = snapshot.baseline ?? "0";
  const confidence = inc.confidence !== undefined ? `${Math.round(Number(inc.confidence) * 100)}%` : "N/A";

  let actionHtml = "";
  if (isPending) {
    actionHtml = `
      <div class="pending-alert-badge">
        <span class="terminal-cursor">&#9608;</span>
        <span>AWAITING HUMAN INTERVENTION // REASON: PROD_SAFETY_GATE</span>
      </div>
      <button class="btn-approve-terminal" onclick="approveIncident('${inc.incident_id}', this)">
        [ EXECUTE THROTTLE: RATE &rarr; 0 ]
      </button>
    `;
  } else if (inc.action_taken === "AUTO_THROTTLED") {
    actionHtml = `
      <span class="action-status-text text-white">
        [&#9889; AUTO_THROTTLED (${stage}) &mdash; ZERO HUMAN LATENCY]
      </span>
      <span style="font-size: 10px; color: var(--text-subtle);">RATELIMIT: 0 &bull; BURST: 0</span>
    `;
  } else if (inc.action_taken === "APPROVED_AND_THROTTLED") {
    actionHtml = `
      <span class="action-status-text text-white">
        [&check; APPROVED_AND_THROTTLED &mdash; 429 TOO MANY REQUESTS ACTIVE]
      </span>
      <span style="font-size: 10px; color: var(--text-subtle);">RESOLVER: OPERATOR</span>
    `;
  } else {
    actionHtml = `
      <span class="action-status-text">
        [&check; VERIFIED_NORMAL &mdash; NO ACTION REQUIRED]
      </span>
      <span style="font-size: 10px; color: var(--text-subtle);">BASELINE INTACT</span>
    `;
  }

  return `
    <article class="${entryClass}" id="entry-${inc.incident_id}">
      <div class="entry-header-row">
        <div class="entry-classification ${isRunaway ? "class-runaway" : "class-normal"}">
          [${escapeHtml(inc.classification)}]
        </div>
        <div class="entry-axis-time">
          ${formatTimestamp(inc.timestamp)} <span style="color: var(--text-subtle);">${formatRelativeTime(inc.timestamp)}</span>
          <span class="entry-stage-tag">// ${escapeHtml(stage)}</span>
          <span class="entry-stage-tag">// ${escapeHtml(inc.resource || "guardrail-demo-api")}</span>
        </div>
      </div>

      <div class="entry-explanation">
        &gt; ${escapeHtml(inc.bedrock_explanation || inc.explanation || "No explanation recorded.")}
      </div>

      <div class="entry-telemetry-row">
        <span class="telemetry-item">CALLERS: <strong>${escapeHtml(String(callers))}</strong></span>
        <span class="telemetry-item">COUNT: <strong>${escapeHtml(String(count))}/MIN</strong></span>
        <span class="telemetry-item">BASELINE: <strong>${escapeHtml(String(baseline))}/MIN</strong></span>
        <span class="telemetry-item">DELTA: <strong class="telemetry-delta ${Number(delta) > 0 ? "text-white" : ""}">${Number(delta) > 0 ? "+" : ""}${escapeHtml(String(delta))}</strong></span>
        <span class="telemetry-item">CONFIDENCE: <strong>${escapeHtml(confidence)}</strong></span>
      </div>

      <div class="entry-action-row">
        ${actionHtml}
        <button class="btn-raw-toggle" onclick="toggleRawDrawer('${inc.incident_id}')">[RAW_DATA]</button>
      </div>

      <div class="entry-raw-drawer" id="raw-${inc.incident_id}">
        <pre>${escapeHtml(JSON.stringify(inc, null, 2))}</pre>
      </div>
    </article>
  `;
}

/**
 * Handles one-click human approval of a pending incident.
 */
async function approveIncident(incidentId, btnElement) {
  if (!btnElement) return;
  const origText = btnElement.textContent;
  btnElement.disabled = true;
  btnElement.textContent = "[ EXECUTING THROTTLE... ]";

  try {
    const res = await fetch(`${CONTROL_API_BASE}/incidents/${incidentId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resolved_by: "Operator Console",
        decision: "APPROVED"
      })
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`HTTP ${res.status}: ${errText}`);
    }

    // Optimistically update local item
    const target = allIncidents.find(i => i.incident_id === incidentId);
    if (target) {
      target.action_taken = "APPROVED_AND_THROTTLED";
    }
    updateMetrics(allIncidents);
    renderFeed();
  } catch (err) {
    alert(`FAILED TO EXECUTE APPROVAL: ${err.message}`);
    btnElement.disabled = false;
    btnElement.textContent = origText;
  }
}

/**
 * Toggles visibility of raw JSON drawer.
 */
function toggleRawDrawer(incidentId) {
  const el = document.getElementById(`raw-${incidentId}`);
  if (el) {
    el.classList.toggle("open");
  }
}

/**
 * HTML escaper helper to prevent XSS.
 */
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Event Listeners
if (envFilter) envFilter.addEventListener("change", renderFeed);
if (refreshBtn) refreshBtn.addEventListener("click", fetchIncidents);

// Auto-Refresh Loop (6s)
autoRefreshTimer = setInterval(fetchIncidents, POLL_INTERVAL_MS);

// Initial Load
fetchIncidents();
