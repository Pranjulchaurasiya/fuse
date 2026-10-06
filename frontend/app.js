/**
 * app.js — Fuse Precision Console Controller
 * Connects to AWS Cost Guardrail Control Plane API (ap-south-1)
 */

// Configuration loaded from config.js (FUSE_CONFIG) or window fallback
const cfg = (typeof FUSE_CONFIG !== "undefined") ? FUSE_CONFIG : (typeof window !== "undefined" && window.FUSE_CONFIG ? window.FUSE_CONFIG : {});
const CONTROL_API_BASE = cfg.CONTROL_API_BASE || "";
const CONTROL_API_KEY = cfg.API_KEY || "";
const TARGET_API_URL = cfg.TARGET_API_URL || "";

/**
 * Returns fetch headers with x-api-key if configured.
 */
function getAuthHeaders(extraHeaders = {}) {
  const headers = { ...extraHeaders };
  if (CONTROL_API_KEY) {
    headers["x-api-key"] = CONTROL_API_KEY;
  }
  return headers;
}

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
      headers: getAuthHeaders({ "Accept": "application/json" })
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
      const configNotice = !CONTROL_API_BASE ? "<br><span style='font-size:12px;color:var(--text-muted);font-weight:normal;'>CONTROL_API_BASE is not set in config.js. For Amplify, ensure config.js is populated during build.</span>" : "";
      container.innerHTML = `
        <div class="empty-state-box">
          <p style="color: var(--state-danger); font-weight: 700;">Control Plane Unreachable: ${escapeHtml(err.message)}${configNotice}</p>
          <button class="btn btn-sync" onclick="fetchIncidents()" style="margin-top: 10px;">Retry Connection</button>
        </div>
      `;
    }
  } finally {
    if (refreshBtn) refreshBtn.classList.remove("loading");
  }
}

/**
 * Smoothly animates number transitions using requestAnimationFrame.
 */
function animateCount(el, targetVal, duration = 650) {
  if (!el) return;
  const startVal = parseInt(el.textContent, 10) || 0;
  if (startVal === targetVal) {
    el.textContent = targetVal;
    return;
  }
  const startTime = performance.now();
  function update(now) {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    // Ease out quad
    const ease = 1 - (1 - progress) * (1 - progress);
    const current = Math.round(startVal + (targetVal - startVal) * ease);
    el.textContent = current;
    if (progress < 1) {
      requestAnimationFrame(update);
    } else {
      el.textContent = targetVal;
    }
  }
  requestAnimationFrame(update);
}

/**
 * Computes metrics scorecard strictly from real DynamoDB Incidents records.
 */
function updateMetrics(incidents) {
  const total = incidents.length;
  const runaways = incidents.filter(i => i.classification === "RUNAWAY").length;
  const pending = incidents.filter(i => i.action_taken === "PENDING_APPROVAL").length;
  const throttled = incidents.filter(i => 
    i.action_taken === "IP_BLOCKED" || i.action_taken === "APPROVED_AND_BLOCKED" ||
    i.action_taken === "AUTO_THROTTLED" || i.action_taken === "APPROVED_AND_THROTTLED"
  ).length;

  animateCount(metricTotal, total);
  animateCount(metricRunaways, runaways);
  animateCount(metricPending, pending);
  animateCount(metricThrottled, throttled);

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
 * Renders the incident feed directly.
 */
function renderFeed() {
  if (feedCount) {
    feedCount.textContent = `${allIncidents.length} incident${allIncidents.length === 1 ? "" : "s"}`;
  }

  if (allIncidents.length === 0) {
    container.innerHTML = `
      <div class="empty-state-box">
        <p style="font-weight: 600; color: var(--text-primary);">No incidents recorded</p>
        <span style="font-size: 12px; color: var(--text-muted);">Run load_test_runaway.py or await the next 1-minute EventBridge evaluation cycle.</span>
      </div>
    `;
    return;
  }

  container.innerHTML = allIncidents.map(inc => renderIncidentCard(inc)).join("");
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
  const confidence = (inc.confidence !== undefined && inc.confidence !== null) ? `${Math.round(Number(inc.confidence) * 100)}%` : "N/A";

  let actionHtml = "";
  if (isPending) {
    actionHtml = `
      <div style="display: flex; align-items: center; gap: 8px;">
        <span class="action-status-chip text-amber">PENDING APPROVAL</span>
        <button class="btn-approve-trip" onclick="approveIncident('${inc.incident_id}', this)" style="padding: 4px 10px; font-size: 11px;">
          Approve WAF IP Block
        </button>
      </div>
    `;
  } else if (inc.action_taken === "IP_BLOCKED") {
    actionHtml = `<span class="action-status-chip text-crimson">WAF IP BLOCKED</span>`;
  } else if (inc.action_taken === "APPROVED_AND_BLOCKED") {
    actionHtml = `<span class="action-status-chip text-crimson">APPROVED &bull; WAF BLOCKED</span>`;
  } else if (inc.action_taken === "AUTO_RECOVERED") {
    actionHtml = `<span class="action-status-chip text-green">AUTO-RECOVERED</span>`;
  } else if (inc.action_taken === "AUTO_THROTTLED" || inc.action_taken === "APPROVED_AND_THROTTLED") {
    actionHtml = `<span class="action-status-chip text-crimson">THROTTLED</span>`;
  } else {
    actionHtml = `<span class="action-status-chip text-green">NORMAL BASELINE</span>`;
  }

  const blockedList = Array.isArray(inc.blocked_ips) && inc.blocked_ips.length > 0 
    ? `<span style="font-family: var(--font-mono); font-size: 11px; color: var(--state-danger);">IP: ${escapeHtml(inc.blocked_ips.join(', '))}</span>` 
    : '';

  return `
    <article class="${cardClass}" id="card-${inc.incident_id}">
      <div class="inc-head" style="padding: 10px 14px;">
        <div class="inc-head-left" style="gap: 8px; align-items: center;">
          <span class="inc-badge ${isRunaway ? "badge-runaway" : "badge-normal"}">
            [${escapeHtml(inc.classification)}]
          </span>
          <span class="inc-resource" style="font-weight: 600;">${escapeHtml(inc.resource || "guardrail-demo-api")}</span>
          <span class="inc-stage" style="font-size: 10px;">[${escapeHtml(stage)}]</span>
          ${blockedList}
        </div>
        <div class="inc-time" style="font-size: 11px;">
          ${formatTimestamp(inc.timestamp)} &bull; ${formatRelativeTime(inc.timestamp)}
        </div>
      </div>

      <div class="inc-body" style="padding: 10px 14px; gap: 8px;">
        <!-- Real Telemetry Grid -->
        <div class="inc-telemetry-grid" style="grid-template-columns: repeat(5, 1fr); gap: 6px;">
          <div class="tele-box" style="padding: 6px 8px;">
            <span class="tele-k">Callers</span>
            <span class="tele-v">${escapeHtml(String(callers))}</span>
          </div>
          <div class="tele-box" style="padding: 6px 8px;">
            <span class="tele-k">Traffic</span>
            <span class="tele-v">${escapeHtml(String(count))}/m</span>
          </div>
          <div class="tele-box" style="padding: 6px 8px;">
            <span class="tele-k">Baseline</span>
            <span class="tele-v">${escapeHtml(String(baseline))}/m</span>
          </div>
          <div class="tele-box" style="padding: 6px 8px;">
            <span class="tele-k">Delta</span>
            <span class="tele-v ${Number(delta) > 0 ? "delta-surge" : ""}">${Number(delta) > 0 ? "+" : ""}${escapeHtml(String(delta))}</span>
          </div>
          <div class="tele-box" style="padding: 6px 8px;">
            <span class="tele-k">Confidence</span>
            <span class="tele-v">${escapeHtml(confidence)}</span>
          </div>
        </div>

        ${inc.bedrock_explanation ? `
        <!-- Genuine Bedrock Rationale from DynamoDB -->
        <div class="reasoning-box" style="padding: 8px 10px; margin-top: 2px;">
          <p class="reasoning-text" style="font-size: 12px; line-height: 1.45; margin: 0;">
            ${escapeHtml(inc.bedrock_explanation)}
          </p>
        </div>
        ` : ''}
      </div>

      <div class="inc-actions" style="padding: 8px 14px; border-top: 1px solid var(--border-light); display: flex; align-items: center; justify-content: space-between;">
        <div class="action-left">
          ${actionHtml}
        </div>
        <button class="btn-toggle-json" onclick="toggleRawDrawer('${inc.incident_id}')" style="font-size: 11px; padding: 3px 8px;">View JSON</button>
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
      headers: getAuthHeaders({ "Content-Type": "application/json" }),
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

// Target API Live Probe (TARGET_API_URL defined in config at top)
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

// Motion & 3D Interactivity
/**
 * Initializes IntersectionObserver for scroll-triggered reveal animations.
 */
function initScrollReveal() {
  const revealElements = document.querySelectorAll(".reveal-on-scroll");
  if (!revealElements.length) return;

  if (!("IntersectionObserver" in window)) {
    revealElements.forEach(el => el.classList.add("is-revealed"));
    return;
  }

  const observer = new IntersectionObserver((entries, obs) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-revealed");
        obs.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.08,
    rootMargin: "0px 0px -30px 0px"
  });

  revealElements.forEach(el => observer.observe(el));
}

/**
 * Initializes 3D tactile perspective tilt on cursor movement.
 */
function init3DTilt() {
  // 1. Hero visual wrapper 3D depth tilt
  const heroWrapper = document.querySelector(".visual-wrapper");
  if (heroWrapper) {
    heroWrapper.addEventListener("mousemove", (e) => {
      const rect = heroWrapper.getBoundingClientRect();
      const x = e.clientX - rect.left - rect.width / 2;
      const y = e.clientY - rect.top - rect.height / 2;
      const rotX = -((y / (rect.height / 2)) * 7).toFixed(2);
      const rotY = ((x / (rect.width / 2)) * 7).toFixed(2);
      heroWrapper.style.transform = `perspective(1000px) rotateX(${rotX}deg) rotateY(${rotY}deg) scale3d(1.02, 1.02, 1.02)`;
    });

    heroWrapper.addEventListener("mouseleave", () => {
      heroWrapper.style.transform = "perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)";
    });
  }

  // 2. Cards subtle tactile 3D tilt
  const tiltCards = document.querySelectorAll(".tilt-3d");
  tiltCards.forEach(card => {
    card.addEventListener("mousemove", (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left - rect.width / 2;
      const y = e.clientY - rect.top - rect.height / 2;
      const rotX = -((y / (rect.height / 2)) * 3.5).toFixed(2);
      const rotY = ((x / (rect.width / 2)) * 3.5).toFixed(2);
      card.style.transform = `perspective(800px) rotateX(${rotX}deg) rotateY(${rotY}deg) translateY(-2px)`;
    });

    card.addEventListener("mouseleave", () => {
      card.style.transform = "perspective(800px) rotateX(0deg) rotateY(0deg) translateY(0)";
    });
  });
}

// Event Listeners
if (refreshBtn) refreshBtn.addEventListener("click", fetchIncidents);
if (btnProbeTarget) btnProbeTarget.addEventListener("click", probeTargetApi);

// Auto-Refresh Loop (6s)
autoRefreshTimer = setInterval(fetchIncidents, POLL_INTERVAL_MS);

// Initial Load
fetchIncidents();
probeTargetApi();
initScrollReveal();
init3DTilt();
