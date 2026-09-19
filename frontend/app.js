/**
 * app.js — Fuse Precision Console Controller
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
const tilePending = document.getElementById("tile-pending");
const feedCount = document.getElementById("feed-count");
const envFilter = document.getElementById("env-filter");
const stageTabs = document.querySelectorAll(".stage-tab");
const refreshBtn = document.getElementById("refresh-btn");
const ledgerList = document.getElementById("ledger-list");

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
    updateLedger(allIncidents);
    renderFeed();
  } catch (err) {
    console.error("Failed to fetch incidents:", err);
    if (allIncidents.length === 0) {
      container.innerHTML = `
        <div class="empty-state-box">
          <p style="color: var(--state-danger); font-weight: 700;">Control Plane Unreachable: ${escapeHtml(err.message)}</p>
          <button class="btn btn-sync" onclick="fetchIncidents()" style="margin-top: 10px;">Retry Connection</button>
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

  if (tilePending) {
    if (pending > 0) {
      tilePending.classList.add("active-pending");
    } else {
      tilePending.classList.remove("active-pending");
    }
  }
}

/**
 * Updates the evaluation ledger in the right sidebar.
 */
function updateLedger(incidents) {
  if (!ledgerList) return;
  if (incidents.length === 0) {
    ledgerList.innerHTML = `
      <div class="ledger-row" style="color: var(--text-muted); font-size: 11px;">
        Awaiting initial evaluation cycle...
      </div>
    `;
    return;
  }

  const recents = incidents.slice(0, 5);
  ledgerList.innerHTML = recents.map(inc => {
    const isRunaway = inc.classification === "RUNAWAY";
    const stage = (inc.environment || "prod").toLowerCase();
    const time = formatTimestamp(inc.timestamp);
    const badgeClass = isRunaway ? "badge-runaway" : "badge-normal";
    return `
      <div class="ledger-row">
        <span class="ledger-time">${time}</span>
        <div class="ledger-desc">
          <span class="ledger-target">${escapeHtml(inc.resource || "demo-api")} [${stage}]</span>
          <span class="ledger-badge ${badgeClass}">${inc.classification}</span>
        </div>
      </div>
    `;
  }).join("");
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
      <div class="empty-state-box">
        <p style="font-weight: 600; color: var(--text-primary);">No incidents recorded for stage [${escapeHtml(filterVal).toUpperCase()}]</p>
        <span style="font-size: 12px; color: var(--text-muted);">Run load_test_runaway.py or await the next 1-minute EventBridge evaluation cycle.</span>
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map(inc => renderIncidentCard(inc)).join("");
}

/**
 * Generates HTML for a single incident card matching Stitch precision style.
 * Strictly zero emojis.
 */
function renderIncidentCard(inc) {
  const isRunaway = inc.classification === "RUNAWAY";
  const isPending = inc.action_taken === "PENDING_APPROVAL";
  const stage = (inc.environment || "prod").toUpperCase();
  
  let cardClass = isRunaway ? "incident-card card-runaway" : "incident-card card-normal";
  if (isPending) {
    cardClass = "incident-card card-runaway card-pending";
  }

  const snapshot = inc.metric_snapshot || {};
  const callers = snapshot.unique_callers ?? "1";
  const count = snapshot.count ?? "0";
  const delta = snapshot.delta ?? "0";
  const baseline = snapshot.baseline ?? "0";
  const confidence = inc.confidence !== undefined ? `${Math.round(Number(inc.confidence) * 100)}%` : "95%";

  let actionHtml = "";
  if (isPending) {
    actionHtml = `
      <div style="display: flex; flex-direction: column; gap: 8px;">
        <div class="action-status-chip text-amber">
          <span class="pulse-dot" style="background-color: var(--state-warning);"></span>
          <span>AWAITING APPROVAL // PRODUCTION SAFETY GATE</span>
        </div>
        <button class="btn-approve-trip" onclick="approveIncident('${inc.incident_id}', this)">
          Approve Circuit Trip — Set RateLimit to 0
        </button>
      </div>
    `;
  } else if (inc.action_taken === "AUTO_THROTTLED") {
    actionHtml = `
      <div class="action-status-chip text-crimson">
        <span>AUTO-THROTTLED (${escapeHtml(stage)}) &mdash; RATE: 0 &bull; ZERO HUMAN LATENCY</span>
      </div>
    `;
  } else if (inc.action_taken === "APPROVED_AND_THROTTLED") {
    actionHtml = `
      <div class="action-status-chip text-crimson">
        <span>APPROVED &amp; THROTTLED &mdash; 429 TOO MANY REQUESTS ACTIVE</span>
      </div>
    `;
  } else {
    actionHtml = `
      <div class="action-status-chip text-green">
        <span>VERIFIED NORMAL &mdash; BASELINE INTACT</span>
      </div>
    `;
  }

  return `
    <article class="${cardClass}" id="card-${inc.incident_id}">
      <div class="inc-head">
        <div class="inc-head-left">
          <span class="inc-badge ${isRunaway ? "badge-runaway" : "badge-normal"}">
            [${escapeHtml(inc.classification)}]
          </span>
          ${isRunaway ? '<span class="inc-tier">CRITICAL - TIER 0</span>' : ''}
          <span class="inc-stage">${escapeHtml(stage)}</span>
          <span class="inc-resource">${escapeHtml(inc.resource || "guardrail-demo-api")}</span>
        </div>
        <div class="inc-time">
          ${formatTimestamp(inc.timestamp)} (${formatRelativeTime(inc.timestamp)})
        </div>
      </div>

      <div class="inc-body">
        <!-- Multi-Dimensional Telemetry Grid -->
        <div class="inc-telemetry-grid">
          <div class="tele-box">
            <span class="tele-k">Unique Callers</span>
            <span class="tele-v">${escapeHtml(String(callers))}</span>
          </div>
          <div class="tele-box">
            <span class="tele-k">Traffic Count</span>
            <span class="tele-v">${escapeHtml(String(count))}/min</span>
          </div>
          <div class="tele-box">
            <span class="tele-k">Rolling Baseline</span>
            <span class="tele-v">${escapeHtml(String(baseline))}/min</span>
          </div>
          <div class="tele-box">
            <span class="tele-k">Traffic Delta</span>
            <span class="tele-v ${Number(delta) > 0 ? "delta-surge" : ""}">${Number(delta) > 0 ? "+" : ""}${escapeHtml(String(delta))}</span>
          </div>
          <div class="tele-box">
            <span class="tele-k">Confidence</span>
            <span class="tele-v">${escapeHtml(confidence)}</span>
          </div>
        </div>

        ${isRunaway ? `
        <!-- Trajectory Bars (Visual Single-Caller Surge) -->
        <div class="trajectory-box">
          <div class="trajectory-head">
            <span style="color: var(--text-muted); font-weight: 600;">EXECUTION TRAJECTORY (SINGLE CALLER RETRY LOOP)</span>
            <span style="color: var(--state-danger); font-weight: 700;">THRESHOLD BREACHED</span>
          </div>
          <div class="trajectory-bars">
            <div class="bar-step" style="height: 12%;"></div>
            <div class="bar-step" style="height: 15%;"></div>
            <div class="bar-step" style="height: 18%;"></div>
            <div class="bar-step" style="height: 22%;"></div>
            <div class="bar-step" style="height: 38%;"></div>
            <div class="bar-step" style="height: 60%;"></div>
            <div class="bar-step step-surge" style="height: 88%;"></div>
            <div class="bar-step step-surge" style="height: 100%;"></div>
          </div>
        </div>
        ` : ''}

        <!-- Bedrock Sentinel Synthesis -->
        <div class="reasoning-box">
          <span class="reasoning-label">AWS Bedrock Sentinel Analysis</span>
          <p class="reasoning-text">
            ${escapeHtml(inc.bedrock_explanation || inc.explanation || "No explanation recorded.")}
          </p>
        </div>
      </div>

      <div class="inc-actions">
        <div class="action-left">
          ${actionHtml}
        </div>
        <button class="btn-toggle-json" onclick="toggleRawDrawer('${inc.incident_id}')">Inspect JSON Payload</button>
      </div>

      <div class="json-drawer" id="raw-${inc.incident_id}">
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
  btnElement.textContent = "Executing Throttle (RateLimit -> 0)...";

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

// Target API Live Probe
const TARGET_API_URL = "https://poim5xmgs2.execute-api.ap-south-1.amazonaws.com/prod/items";
const probeStatusPill = document.getElementById("probe-status-pill");
const probeStatusText = document.getElementById("probe-status-text");
const probeThrottleState = document.getElementById("probe-throttle-state");
const btnProbeTarget = document.getElementById("btn-probe-target");

async function probeTargetApi() {
  if (btnProbeTarget) btnProbeTarget.disabled = true;
  if (probeStatusText) probeStatusText.textContent = "Probing target...";

  try {
    const res = await fetch(TARGET_API_URL, {
      method: "GET",
      cache: "no-store"
    });

    if (res.status === 429) {
      if (probeStatusPill) {
        probeStatusPill.textContent = "THROTTLED (429)";
        probeStatusPill.className = "probe-status-pill status-throttled";
      }
      if (probeStatusText) probeStatusText.innerHTML = '<span class="text-crimson">HTTP 429 Too Many Requests</span>';
      if (probeThrottleState) probeThrottleState.innerHTML = '<span class="text-crimson">Circuit Tripped &bull; Rate = 0</span>';
    } else if (res.ok) {
      if (probeStatusPill) {
        probeStatusPill.textContent = "HEALTHY (200)";
        probeStatusPill.className = "probe-status-pill status-ok";
      }
      if (probeStatusText) probeStatusText.innerHTML = '<span class="text-green">HTTP 200 OK</span>';
      if (probeThrottleState) probeThrottleState.innerHTML = '<span class="text-green">Normal Flow &bull; Baseline Active</span>';
    } else {
      if (probeStatusPill) {
        probeStatusPill.textContent = `HTTP ${res.status}`;
        probeStatusPill.className = "probe-status-pill";
      }
      if (probeStatusText) probeStatusText.textContent = `HTTP ${res.status} ${res.statusText}`;
      if (probeThrottleState) probeThrottleState.textContent = "Non-200 Status";
    }
  } catch (err) {
    if (probeStatusPill) {
      probeStatusPill.textContent = "PROBE FAILED";
      probeStatusPill.className = "probe-status-pill";
    }
    if (probeStatusText) probeStatusText.textContent = err.message;
    if (probeThrottleState) probeThrottleState.textContent = "Network error / CORS";
  } finally {
    if (btnProbeTarget) btnProbeTarget.disabled = false;
  }
}

// Stage Tabs Event Handlers
stageTabs.forEach(tab => {
  tab.addEventListener("click", () => {
    stageTabs.forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    const stage = tab.getAttribute("data-stage");
    if (envFilter) {
      envFilter.value = stage;
    }
    renderFeed();
  });
});

// Event Listeners
if (refreshBtn) refreshBtn.addEventListener("click", fetchIncidents);
if (btnProbeTarget) btnProbeTarget.addEventListener("click", probeTargetApi);

// Auto-Refresh Loop (6s)
autoRefreshTimer = setInterval(fetchIncidents, POLL_INTERVAL_MS);

// Initial Load
fetchIncidents();
probeTargetApi();
