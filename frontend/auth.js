/**
 * auth.js — Fuse Operator Console Auth Gate
 * Simple localStorage session gate. Not production Cognito — demo grade.
 */

(function () {
  const cfg = (typeof FUSE_CONFIG !== 'undefined') ? FUSE_CONFIG : {};
  const PASSWORD = cfg.OPERATOR_PASSWORD || 'fuse-operator-2024';
  const TOKEN_KEY = 'fuse_auth_token';
  const SESSION_HOURS = 8;

  function isAuthed() {
    try {
      const raw = localStorage.getItem(TOKEN_KEY);
      if (!raw) return false;
      const { token, expires } = JSON.parse(raw);
      if (Date.now() > expires) {
        localStorage.removeItem(TOKEN_KEY);
        return false;
      }
      return token === btoa(PASSWORD);
    } catch { return false; }
  }

  function login(password) {
    if (password !== PASSWORD) return false;
    localStorage.setItem(TOKEN_KEY, JSON.stringify({
      token: btoa(PASSWORD),
      expires: Date.now() + SESSION_HOURS * 3600 * 1000,
    }));
    return true;
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    window.location.reload();
  }

  function showLockScreen() {
    const overlay = document.createElement('div');
    overlay.id = 'fuse-lock-screen';
    overlay.innerHTML = `
      <style>
        #fuse-lock-screen {
          position: fixed; inset: 0; z-index: 9999;
          background: #0a0a0b;
          display: flex; align-items: center; justify-content: center;
          font-family: 'Inter', system-ui, sans-serif;
        }
        .lock-card {
          background: #141416;
          border: 1px solid #27272a;
          border-radius: 12px;
          padding: 40px 48px;
          width: 100%; max-width: 380px;
          text-align: center;
        }
        .lock-logo {
          font-size: 22px; font-weight: 800; letter-spacing: 0.15em;
          color: #fff; margin-bottom: 8px;
        }
        .lock-sub {
          font-size: 12px; color: #71717a; margin-bottom: 32px;
        }
        .lock-input {
          width: 100%; box-sizing: border-box;
          padding: 10px 14px;
          background: #1c1c1e; border: 1px solid #3f3f46;
          border-radius: 8px; color: #fff; font-size: 14px;
          outline: none; margin-bottom: 12px;
        }
        .lock-input:focus { border-color: #6366f1; }
        .lock-btn {
          width: 100%; padding: 10px;
          background: #6366f1; border: none; border-radius: 8px;
          color: #fff; font-size: 14px; font-weight: 600;
          cursor: pointer; transition: background 0.2s;
        }
        .lock-btn:hover { background: #4f46e5; }
        .lock-error {
          color: #ef4444; font-size: 12px; margin-top: 8px;
          display: none;
        }
      </style>
      <div class="lock-card">
        <div class="lock-logo">FUSE</div>
        <div class="lock-sub">Cost Guardrail — Operator Console</div>
        <input class="lock-input" type="password" id="lock-pw" placeholder="Operator password" />
        <button class="lock-btn" id="lock-submit">Unlock Console</button>
        <div class="lock-error" id="lock-err">Incorrect password</div>
      </div>
    `;
    document.body.appendChild(overlay);

    const input = document.getElementById('lock-pw');
    const btn = document.getElementById('lock-submit');
    const errMsg = document.getElementById('lock-err');

    function attempt() {
      if (login(input.value)) {
        overlay.remove();
      } else {
        errMsg.style.display = 'block';
        input.value = '';
        input.focus();
      }
    }

    btn.addEventListener('click', attempt);
    input.addEventListener('keydown', e => { if (e.key === 'Enter') attempt(); });
    setTimeout(() => input.focus(), 100);
  }

  function addLogoutButton() {
    // Find nav or header and inject logout
    const nav = document.querySelector('nav, .nav-bar, header, .top-bar');
    if (!nav) return;
    const btn = document.createElement('button');
    btn.textContent = 'Sign Out';
    btn.style.cssText = 'background:none;border:1px solid #3f3f46;color:#71717a;padding:4px 12px;border-radius:6px;font-size:12px;cursor:pointer;margin-left:auto;';
    btn.addEventListener('click', logout);
    nav.appendChild(btn);
  }

  // Run on DOM ready
  function init() {
    if (!isAuthed()) {
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

  // Expose logout globally
  window.fuseLogout = logout;
})();
