/**
 * app.js — Operator Incident Response Console
 * Fronts AWS Cost Guardrail Control Plane API (ap-south-1)
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
const autoRefreshCheckbox = document.getElementById("auto-refresh-checkbox");

/**
 * Formats epoch timestamp into clean local time string.
 */
function formatTimestamp(epochSec) {
  if (!epochSec) return "Just now";
  const date = new Date(Number(epochSec) * 1000);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

/**
 * Formats date into relative time string (e.g. '2m ago').
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
  refreshBtn.classList.add("loading");
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
        <div class="empty-state">
          <p style="color: var(--color-runaway);">Failed to connect to Control API: ${escapeHtml(err.message)}</p>
          <button class="btn btn-secondary" onclick="fetchIncidents()">Retry</button>
        </div>
      `;
    }
  } finally {
    refreshBtn.classList.remove("loading");
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

  metricTotal.textContent = total;
  metricRunaways.textContent = runaways;
  metricPending.textContent = pending;
  metricThrottled.textContent = throttled;
}

/**
 * Renders the incident feed based on current environment filter.
 */
function renderFeed() {
  const filterVal = envFilter.value;
  const filtered = allIncidents.filter(inc => {
    if (filterVal === "all") return true;
    const env = (inc.environment || "prod").toLowerCase();
    return env === filterVal.toLowerCase();
  });

  feedCount.textContent = `Showing ${filtered.length} incident${filtered.length === 1 ? "" : "s"}`;

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <p>No incidents found for stage: <strong>${escapeHtml(filterVal)}</strong></p>
        <span style="font-size: 12px;">Run a test traffic script or trigger the poller to view live activity.</span>
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map(inc => renderIncidentCard(inc)).join("");
}

/**
 * Generates HTML for a single incident card adhering to DESIGN.md states.
 */
function renderIncidentCard(inc) {
  const isRunaway = inc.classification === "RUNAWAY";
  const isPending = inc.action_taken === "PENDING_APPROVAL";
  const stage = inc.environment || "prod";
  const cardClass = isPending ? "card-pending" : (isRunaway ? "card-runaway" : "card-normal");
  
  const snapshot = inc.metric_snapshot || {};
  const callers = snapshot.unique_callers ?? "N/A";
  const count = snapshot.count ?? "0";
  const delta = snapshot.delta ?? "0";
  const baseline = snapshot.baseline ?? "0";

  let actionHtml = "";
  if (isPending) {
    actionHtml = `
      <div class="action-status-badge" style="color: var(--color-pending);">
        <span class="pulse-amber"></span>
        <span>Awaiting Human Approval</span>
      </div>
      <button class="btn btn-approve" onclick="approveIncident('${inc.incident_id}', this)">
        Approve Throttle (Rate → 0)
      </button>
    `;
  } else if (inc.action_taken === "AUTO_THROTTLED") {
    actionHtml = `
      <div class="action-status-badge" style="color: var(--color-runaway);">
        <span>⚡ Auto-Throttled (${stage})</span>
      </div>
      <span class="chip-val" style="color: var(--color-text-muted); font-size: 12px;">Zero human latency</span>
    `;
  } else if (inc.action_taken === "APPROVED_AND_THROTTLED") {
    actionHtml = `
      <div class="action-status-badge" style="color: var(--color-accent);">
        <span>✓ Approved & Throttled (429 Active)</span>
      </div>
    `;
  } else {
    actionHtml = `
      <div class="action-status-badge" style="color: var(--color-normal);">
        <span>✓ Legitimate Traffic (No Action Needed)</span>
      </div>
    `;
  }

  return `
    <div class="incident-card ${cardClass}" id="card-${inc.incident_id}">
      <div class="card-top">
        <div class="card-top-left">
          <span class="badge-classification ${isRunaway ? "badge-runaway" : "badge-normal"}">
            ${isRunaway ? "🔴 RUNAWAY" : "🟢 NORMAL"}
          </span>
          <span class="badge-stage">${escapeHtml(stage)}</span>
          <span class="badge-resource">${escapeHtml(inc.resource || "guardrail-demo-api")}</span>
        </div>
        <div class="card-timestamp" title="${new Date(Number(inc.timestamp) * 1000).toISOString()}">
          ${formatTimestamp(inc.timestamp)} (${formatRelativeTime(inc.timestamp)})
        </div>
      </div>

      <div class="card-explanation">
        ${escapeHtml(inc.bedrock_explanation || inc.explanation || "No explanation recorded.")}
      </div>

      <div class="card-chips">
        <div class="chip">
          <span class="chip-label">Unique Callers:</span>
          <span class="chip-val">${escapeHtml(String(callers))}</span>
        </div>
        <div class="chip">
          <span class="chip-label">Current:</span>
          <span class="chip-val">${escapeHtml(String(count))}/min</span>
        </div>
        <div class="chip">
          <span class="chip-label">Baseline:</span>
          <span class="chip-val">${escapeHtml(String(baseline))}/min</span>
        </div>
        <div class="chip">
          <span class="chip-label">Delta:</span>
          <span class="chip-val" style="color: ${Number(delta) > 0 ? 'var(--color-runaway)' : 'inherit'}">
            +${escapeHtml(String(delta))}
          </span>
        </div>
        <div class="chip">
          <span class="chip-label">Confidence:</span>
          <span class="chip-val">${inc.confidence !== undefined ? Math.round(Number(inc.confidence) * 100) + "%" : "N/A"}</span>
        </div>
      </div>

      <div class="card-action-bar">
        ${actionHtml}
        <button class="details-toggle" onclick="toggleDetails('${inc.incident_id}')">Inspect Raw Snapshot</button>
      </div>

      <div class="details-drawer" id="details-${inc.incident_id}">
        <pre>${escapeHtml(JSON.stringify(inc, null, 2))}</pre>
      </div>
    </div>
  `;
}

/**
 * Handles one-click human approval of a pending incident.
 */
async function approveIncident(incidentId, btnElement) {
  if (!btnElement) return;
  const origText = btnElement.textContent;
  btnElement.disabled = true;
  btnElement.textContent = "Throttling Stage...";

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

    const data = await res.json();
    console.log("Approval response:", data);

    // Optimistically update local item
    const target = allIncidents.find(i => i.incident_id === incidentId);
    if (target) {
      target.action_taken = "APPROVED_AND_THROTTLED";
    }
    updateMetrics(allIncidents);
    renderFeed();
  } catch (err) {
    alert(`Failed to approve incident: ${err.message}`);
    btnElement.disabled = false;
    btnElement.textContent = origText;
  }
}

/**
 * Toggles visibility of the raw snapshot JSON drawer.
 */
function toggleDetails(incidentId) {
  const el = document.getElementById(`details-${incidentId}`);
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
envFilter.addEventListener("change", renderFeed);
refreshBtn.addEventListener("click", fetchIncidents);

autoRefreshCheckbox.addEventListener("change", (e) => {
  if (e.target.checked) {
    startAutoRefresh();
  } else {
    stopAutoRefresh();
  }
});

function startAutoRefresh() {
  stopAutoRefresh();
  autoRefreshTimer = setInterval(fetchIncidents, POLL_INTERVAL_MS);
}

function stopAutoRefresh() {
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer);
    autoRefreshTimer = null;
  }
}

// Initial Boot
fetchIncidents();
startAutoRefresh();
