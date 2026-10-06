/**
 * auth.js — Fuse Operator & Multi-Tenant Auth Gate
 * 
 * Supports two authentication paths:
 * 1. Production Mode: Supabase Auth (Magic Link & Email/Password) if SUPABASE_URL is configured.
 * 2. Standalone Demo Mode: Operator password session gate with localStorage token fallback.
 */

(function () {
  const cfg = (typeof FUSE_CONFIG !== 'undefined') ? FUSE_CONFIG : {};
  const SUPABASE_URL = cfg.SUPABASE_URL || '';
  const SUPABASE_ANON_KEY = cfg.SUPABASE_ANON_KEY || '';
  const PASSWORD = cfg.OPERATOR_PASSWORD || 'fuse-operator-2024';
  const TOKEN_KEY = 'fuse_auth_token';
  const SESSION_HOURS = 8;

  let supabaseClient = null;

  // Initialize Supabase if SDK is available and credentials provided
  if (SUPABASE_URL && SUPABASE_ANON_KEY && typeof window.supabase !== 'undefined') {
    supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
  }

  async function checkAuth() {
    if (supabaseClient) {
      const { data: { session } } = await supabaseClient.auth.getSession();
      return !!session;
    }
    try {
      const raw = localStorage.getItem(TOKEN_KEY);
      if (!raw) return false;
      const { token, expires } = JSON.parse(raw);
      if (Date.now() > expires) {
        localStorage.removeItem(TOKEN_KEY);
        return false;
      }
      return token === btoa(PASSWORD);
    } catch {
      return false;
    }
  }

  function demoLogin(password) {
    if (password !== PASSWORD) return false;
    localStorage.setItem(TOKEN_KEY, JSON.stringify({
      token: btoa(PASSWORD),
      expires: Date.now() + SESSION_HOURS * 3600 * 1000,
    }));
    return true;
  }

  async function logout() {
    if (supabaseClient) {
      await supabaseClient.auth.signOut();
    }
    localStorage.removeItem(TOKEN_KEY);
    window.location.reload();
  }

  function showLockScreen() {
    const existing = document.getElementById('fuse-lock-screen');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'fuse-lock-screen';
    overlay.innerHTML = `
      <style>
        #fuse-lock-screen {
          position: fixed; inset: 0; z-index: 9999;
          background: #090a0f;
          display: flex; align-items: center; justify-content: center;
          font-family: 'Inter', -apple-system, sans-serif;
          backdrop-filter: blur(8px);
        }
        .lock-card {
          background: #11131a;
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 14px;
          padding: 36px 40px;
          width: 100%; max-width: 380px;
          box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
          text-align: center;
        }
        .lock-logo-badge {
          display: inline-flex; align-items: center; justify-content: center;
          width: 42px; height: 42px; border-radius: 10px;
          background: linear-gradient(135deg, #004ac6, #2563eb);
          color: #fff; font-size: 20px; font-weight: 800;
          margin-bottom: 16px;
        }
        .lock-title {
          font-size: 20px; font-weight: 700; color: #fff; margin-bottom: 6px;
          letter-spacing: -0.02em;
        }
        .lock-sub {
          font-size: 13px; color: #8892b0; margin-bottom: 24px; line-height: 1.4;
        }
        .lock-input {
          width: 100%; box-sizing: border-box;
          padding: 11px 14px;
          background: #181b24; border: 1px solid rgba(255, 255, 255, 0.12);
          border-radius: 8px; color: #fff; font-size: 14px;
          outline: none; margin-bottom: 12px; transition: border-color 0.2s;
        }
        .lock-input:focus { border-color: #2563eb; }
        .lock-btn {
          width: 100%; padding: 11px;
          background: #2563eb; border: none; border-radius: 8px;
          color: #fff; font-size: 14px; font-weight: 600;
          cursor: pointer; transition: background 0.2s;
        }
        .lock-btn:hover { background: #1d4ed8; }
        .lock-error {
          color: #ef4444; font-size: 12px; margin-top: 10px;
          display: none;
        }
        .lock-footer {
          margin-top: 20px; font-size: 11px; color: #64748b;
        }
      </style>
      <div class="lock-card">
        <div class="lock-logo-badge">F</div>
        <div class="lock-title">FUSE SENTINEL</div>
        <div class="lock-sub">${supabaseClient ? 'Sign in with your team credentials' : 'Autonomous Cost Guardrail Console'}</div>
        
        <input class="lock-input" type="password" id="lock-pw" placeholder="${supabaseClient ? 'Password' : 'Enter Operator Password'}" />
        <button class="lock-btn" id="lock-submit">Unlock Console &rarr;</button>
        <div class="lock-error" id="lock-err">Invalid password. Check config.js</div>
        <div class="lock-footer">Protected AWS Session &bull; 256-bit Scoped IAM</div>
      </div>
    `;
    document.body.appendChild(overlay);

    const input = document.getElementById('lock-pw');
    const btn = document.getElementById('lock-submit');
    const errMsg = document.getElementById('lock-err');

    async function attempt() {
      const val = input.value.trim();
      if (!val) return;

      btn.disabled = true;
      btn.innerText = 'Verifying...';

      if (supabaseClient) {
        // Supabase flow
        const { error } = await supabaseClient.auth.signInWithPassword({
          email: 'operator@fusecloud.dev',
          password: val
        });
        if (error) {
          errMsg.innerText = error.message;
          errMsg.style.display = 'block';
          btn.disabled = false;
          btn.innerText = 'Unlock Console →';
        } else {
          overlay.remove();
          addLogoutButton();
        }
      } else {
        // Standalone operator password fallback
        if (demoLogin(val)) {
          overlay.remove();
          addLogoutButton();
        } else {
          errMsg.style.display = 'block';
          btn.disabled = false;
          btn.innerText = 'Unlock Console →';
          input.value = '';
          input.focus();
        }
      }
    }

    btn.addEventListener('click', attempt);
    input.addEventListener('keydown', e => { if (e.key === 'Enter') attempt(); });
    setTimeout(() => input.focus(), 100);
  }

  function addLogoutButton() {
    const navRight = document.querySelector('.nav-right');
    if (!navRight || document.getElementById('fuse-signout-btn')) return;
    const btn = document.createElement('button');
    btn.id = 'fuse-signout-btn';
    btn.textContent = 'Sign Out';
    btn.className = 'btn';
    btn.style.cssText = 'background:var(--bg-canvas, #f8fafc);border:1px solid var(--border-light, #e2e8f0);color:var(--text-secondary, #475569);padding:6px 12px;font-size:12px;cursor:pointer;font-weight:600;border-radius:6px;';
    btn.addEventListener('click', logout);
    navRight.appendChild(btn);
  }

  async function init() {
    const authed = await checkAuth();
    if (!authed) {
      showLockScreen();
    } else {
      addLogoutButton();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.fuseAuth = {
    logout,
    checkAuth,
    getSupabase: () => supabaseClient
  };
})();
