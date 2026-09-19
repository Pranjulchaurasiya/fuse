/**
 * app.js — Fuse Incident Response Stream Controller
 * Connects to AWS Cost Guardrail Control Plane API (ap-south-1)
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
 * Formats epoch timestamp into clean local time string.
 */
function formatTimestamp(epochSec) {
  if (!epochSec) return "--:--:--";
  const date = new Date(Number(epochSec) * 1000);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
}

/**
 * Formats epoch timestamp into relative time (e.g. '2m ago').
 */
function formatRelativeTime(epochSec) {
  if (!epochSec) return "";
  const diffSec = Math.floor(Date.now() / 1000 - Number(epochSec));
  if (diffSec < 60) return `${Math.max(1, diffSec)}s ago`;
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  return `${Math.floor(diffSec / 3600)}h ago`;
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
        <div class="empty-box">
          <p style="color: var(--status-runaway); font-weight: 600;">Control Plane Unreachable: ${escapeHtml(err.message)}</p>
          <button class="btn btn-refresh" onclick="fetchIncidents()" style="margin-top: 10px;">Retry Connection</button>
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
 * Renders the incident feed based on current environment filter.
 */
function renderFeed() {
  const filterVal = envFilter ? envFilter.value : "all";
  const filtered = allIncidents.filter(inc => {
    if (filterVal === "all") return true;
    const env = (inc.environment || "prod").toLowerCase();
    return env === filterVal.toLowerCase();
  });

  if (feedCount) {
    feedCount.textContent = `${filtered.length} incident${filtered.length === 1 ? "" : "s"}`;
  }

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-box">
        <p style="font-weight: 600; color: var(--text-main);">No incidents recorded for stage [${escapeHtml(filterVal).toUpperCase()}]</p>
        <span style="font-size: 13px; color: var(--text-subtle);">Run load_test_runaway.py or await the next 1-minute EventBridge evaluation cycle.</span>
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map(inc => renderIncidentCard(inc)).join("");
}

/**
 * Generates HTML for a single incident card matching the light editorial theme.
 * Strictly zero emojis.
 */
function renderIncidentCard(inc) {
  const isRunaway = inc.classification === "RUNAWAY";
  const isPending = inc.action_taken === "PENDING_APPROVAL";
  const stage = (inc.environment || "prod").toUpperCase();
  
  let cardStateClass = isRunaway ? "card-runaway" : "card-normal";
  if (isPending) {
    cardStateClass = "card-pending";
  }

  const snapshot = inc.metric_snapshot || {};
  const callers = snapshot.unique_callers ?? "N/A";
  const count = snapshot.count ?? "0";
  const delta = snapshot.delta ?? "0";
  const baseline = snapshot.baseline ?? "0";
  const confidence = inc.confidence !== undefined ? `${Math.round(Number(inc.confidence) * 100)}%` : "N/A";

  let actionHtml = "";
  if (isPending) {
    actionHtml = `
      <div class="action-label-box text-pending">
        <span class="dot-amber"></span>
        <span>AWAITING APPROVAL // PRODUCTION SAFETY GATE</span>
      </div>
      <button class="btn btn-approve" onclick="approveIncident('${inc.incident_id}', this)">
        Approve Throttle (Rate &rarr; 0)
      </button>
    `;
  } else if (inc.action_taken === "AUTO_THROTTLED") {
    actionHtml = `
      <div class="action-label-box text-throttled">
        <span>AUTO-THROTTLED (${escapeHtml(stage)}) &mdash; ZERO HUMAN LATENCY</span>
      </div>
    `;
  } else if (inc.action_taken === "APPROVED_AND_THROTTLED") {
    actionHtml = `
      <div class="action-label-box text-throttled">
        <span>APPROVED &amp; THROTTLED &mdash; 429 TOO MANY REQUESTS ACTIVE</span>
      </div>
    `;
  } else {
    actionHtml = `
      <div class="action-label-box text-normal">
        <span>VERIFIED NORMAL &mdash; BASELINE INTACT</span>
      </div>
    `;
  }

  return `
    <article class="incident-card ${cardStateClass}" id="card-${inc.incident_id}">
      <div class="card-header-row">
        <div class="card-header-left">
          <span class="status-badge ${isRunaway ? "badge-runaway" : "badge-normal"}">
            [${escapeHtml(inc.classification)}]
          </span>
          <span class="tag-stage">${escapeHtml(stage)}</span>
          <span class="tag-resource">${escapeHtml(inc.resource || "guardrail-demo-api")}</span>
        </div>
        <div class="card-timestamp">
          ${formatTimestamp(inc.timestamp)} (${formatRelativeTime(inc.timestamp)})
        </div>
      </div>

      <div class="card-explanation">
        ${escapeHtml(inc.bedrock_explanation || inc.explanation || "No explanation recorded.")}
      </div>

      <div class="telemetry-cluster">
        <div class="tele-pill">
          <span class="tele-label">Unique Callers</span>
          <span class="tele-val">${escapeHtml(String(callers))}</span>
        </div>
        <div class="tele-pill">
          <span class="tele-label">Traffic Count</span>
          <span class="tele-val">${escapeHtml(String(count))}/min</span>
        </div>
        <div class="tele-pill">
          <span class="tele-label">Rolling Baseline</span>
          <span class="tele-val">${escapeHtml(String(baseline))}/min</span>
        </div>
        <div class="tele-pill">
          <span class="tele-label">Traffic Delta</span>
          <span class="tele-val ${Number(delta) > 0 ? "delta-pos" : ""}">${Number(delta) > 0 ? "+" : ""}${escapeHtml(String(delta))}</span>
        </div>
        <div class="tele-pill">
          <span class="tele-label">Confidence</span>
          <span class="tele-val">${escapeHtml(confidence)}</span>
        </div>
      </div>

      <div class="card-action-bar">
        <div class="action-left">
          ${actionHtml}
        </div>
        <button class="btn-inspect" onclick="toggleRawDrawer('${inc.incident_id}')">Inspect JSON</button>
      </div>

      <div class="raw-drawer" id="raw-${inc.incident_id}">
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
  btnElement.textContent = "Executing Throttle...";

  try {
    const res = await fetch(`${CONTROL_API_BASE}/incidents/${incidentId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resolved_by: "Fuse Operator Console",
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
    alert(`Failed to execute approval: ${err.message}`);
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
