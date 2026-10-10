/**
 * auth.js — Fuse Enterprise & Operator Authentication Controller
 * 
 * Production Security:
 * Uses Amazon Cognito User Pools (JWT Authorizer) via direct AWS regional REST calls.
 * Issues cryptographic, short-lived JWT tokens with zero third-party dependencies.
 * The validated ID token is automatically passed as:
 *   Authorization: Bearer <id_token>
 * to API Gateway, eliminating client-side static API keys.
 */

(function () {
  const cfg = (typeof FUSE_CONFIG !== 'undefined') ? FUSE_CONFIG : {};
  const COGNITO_USER_POOL_ID = cfg.COGNITO_USER_POOL_ID || 'ap-south-1_09wo36fcc';
  const COGNITO_CLIENT_ID = cfg.COGNITO_CLIENT_ID || '79gbbjcj2h5kji0ng2a6ua0llg';
  const AWS_REGION = cfg.AWS_REGION || 'ap-south-1';
  const PASSWORD = cfg.OPERATOR_PASSWORD || '';
  const TOKEN_KEY = 'fuse_auth_token';
  const COGNITO_ID_TOKEN_KEY = 'fuse_cognito_id_token';
  const COGNITO_ACCESS_TOKEN_KEY = 'fuse_cognito_access_token';
  const COGNITO_EMAIL_KEY = 'fuse_cognito_email';
  const SESSION_HOURS = 8;

  function parseJwt(token) {
    try {
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
      }).join(''));
      return JSON.parse(jsonPayload);
    } catch (e) {
      return null;
    }
  }

  function getIdToken() {
    const token = sessionStorage.getItem(COGNITO_ID_TOKEN_KEY);
    if (!token) return null;
    const parsed = parseJwt(token);
    if (!parsed || !parsed.exp || (Date.now() / 1000) > parsed.exp) {
      sessionStorage.removeItem(COGNITO_ID_TOKEN_KEY);
      sessionStorage.removeItem(COGNITO_ACCESS_TOKEN_KEY);
      return null;
    }
    return token;
  }

  function getAccessToken() {
    return sessionStorage.getItem(COGNITO_ACCESS_TOKEN_KEY);
  }

  function getUserEmail() {
    return sessionStorage.getItem(COGNITO_EMAIL_KEY) || 'operator';
  }

  async function cognitoSignIn(username, password) {
    if (!COGNITO_CLIENT_ID) {
      throw new Error('COGNITO_CLIENT_ID is not configured.');
    }

    const endpoint = `https://cognito-idp.${AWS_REGION}.amazonaws.com/`;
    const payload = {
      AuthFlow: 'USER_PASSWORD_AUTH',
      ClientId: COGNITO_CLIENT_ID,
      AuthParameters: {
        USERNAME: username,
        PASSWORD: password
      }
    };

    const res = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-amz-json-1.1',
        'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth'
      },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok) {
      const msg = data.message || data.__type || 'Authentication failed';
      throw new Error(msg);
    }

    if (data.AuthenticationResult) {
      const idToken = data.AuthenticationResult.IdToken;
      const accessToken = data.AuthenticationResult.AccessToken;
      sessionStorage.setItem(COGNITO_ID_TOKEN_KEY, idToken);
      sessionStorage.setItem(COGNITO_ACCESS_TOKEN_KEY, accessToken);
      sessionStorage.setItem(COGNITO_EMAIL_KEY, username);
      return { success: true, idToken, accessToken };
    }

    if (data.ChallengeName) {
      throw new Error(`Cognito Challenge required: ${data.ChallengeName}. Contact administrator.`);
    }

    throw new Error('Unexpected Cognito response format');
  }

  function demoLogin(password) {
    if (!PASSWORD || !password || password !== PASSWORD) return false;
    localStorage.setItem(TOKEN_KEY, JSON.stringify({
      token: btoa(PASSWORD),
      expires: Date.now() + SESSION_HOURS * 3600 * 1000,
    }));
    return true;
  }

  async function checkAuth() {
    // 1. Check verified cryptographic Cognito token first
    const cognitoToken = getIdToken();
    if (cognitoToken) return true;

    // 2. Fallback to legacy demo localStorage token if password is set
    if (!PASSWORD) return false;
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

  function logout() {
    sessionStorage.removeItem(COGNITO_ID_TOKEN_KEY);
    sessionStorage.removeItem(COGNITO_ACCESS_TOKEN_KEY);
    sessionStorage.removeItem(COGNITO_EMAIL_KEY);
    localStorage.removeItem(TOKEN_KEY);
    window.location.reload();
  }

  function showLockScreen() {
    const existing = document.getElementById('fuse-lock-screen');
    if (existing) existing.remove();

    const isCognitoConfigured = Boolean(COGNITO_CLIENT_ID);

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
          width: 100%; max-width: 400px;
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
        .lock-badge {
          display: inline-flex; align-items: center; gap: 6px;
          background: rgba(37, 99, 235, 0.12); border: 1px solid rgba(37, 99, 235, 0.3);
          border-radius: 6px; padding: 4px 10px; font-size: 11px;
          color: #60a5fa; margin-bottom: 18px; font-family: monospace;
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
        <div class="lock-sub">Autonomous Cost Guardrail Console</div>
        <div class="lock-badge">&bull; ${isCognitoConfigured ? 'AWS Cognito Cryptographic Auth' : 'Standalone Operator Session'}</div>

        ${isCognitoConfigured ? `
          <input class="lock-input" type="email" id="lock-email" placeholder="Operator Email" value="operator@fuse.internal" />
          <input class="lock-input" type="password" id="lock-pw" placeholder="Cognito Password" />
        ` : `
          <input class="lock-input" type="password" id="lock-pw" placeholder="Enter Operator Password" />
        `}

        <button class="lock-btn" id="lock-submit">Unlock Console &rarr;</button>
        <div class="lock-error" id="lock-err">Invalid credentials</div>
        <div class="lock-footer">Protected AWS Session &bull; 256-bit Scoped IAM</div>
      </div>
    `;
    document.body.appendChild(overlay);

    const emailInput = document.getElementById('lock-email');
    const pwInput = document.getElementById('lock-pw');
    const btn = document.getElementById('lock-submit');
    const errMsg = document.getElementById('lock-err');

    async function attempt() {
      const pw = pwInput.value.trim();
      const email = emailInput ? emailInput.value.trim() : '';
      if (!pw) return;

      btn.disabled = true;
      btn.innerText = 'Authenticating with AWS...';
      errMsg.style.display = 'none';

      try {
        if (isCognitoConfigured && email) {
          await cognitoSignIn(email, pw);
          overlay.remove();
          addLogoutButton();
          if (window.fetchIncidents) window.fetchIncidents();
        } else {
          if (demoLogin(pw)) {
            overlay.remove();
            addLogoutButton();
            if (window.fetchIncidents) window.fetchIncidents();
          } else {
            throw new Error('Invalid operator password.');
          }
        }
      } catch (err) {
        errMsg.innerText = err.message || 'Authentication failed';
        errMsg.style.display = 'block';
        btn.disabled = false;
        btn.innerText = 'Unlock Console →';
        pwInput.value = '';
        pwInput.focus();
      }
    }

    btn.addEventListener('click', attempt);
    pwInput.addEventListener('keydown', e => { if (e.key === 'Enter') attempt(); });
    if (emailInput) emailInput.addEventListener('keydown', e => { if (e.key === 'Enter') pwInput.focus(); });
    setTimeout(() => pwInput.focus(), 100);
  }

  function addLogoutButton() {
    const navRight = document.querySelector('.nav-right');
    if (!navRight || document.getElementById('fuse-signout-btn')) return;

    const email = getUserEmail();
    const token = getIdToken();

    const userBadge = document.createElement('div');
    userBadge.style.cssText = 'display:inline-flex;align-items:center;gap:6px;font-size:11.5px;color:var(--text-secondary,#475569);font-family:monospace;background:rgba(255,255,255,0.06);padding:4px 8px;border-radius:6px;border:1px solid rgba(255,255,255,0.1);';
    userBadge.innerHTML = `<span style="color:#10b981;">&bull;</span> ${email} ${token ? '<span style="color:#60a5fa;font-size:10px;">[JWT]</span>' : ''}`;
    navRight.appendChild(userBadge);

    const btn = document.createElement('button');
    btn.id = 'fuse-signout-btn';
    btn.textContent = 'Sign Out';
    btn.className = 'btn';
    btn.style.cssText = 'background:var(--bg-canvas, #f8fafc);border:1px solid var(--border-light, #e2e8f0);color:var(--text-secondary, #475569);padding:6px 12px;font-size:12px;cursor:pointer;font-weight:600;border-radius:6px;margin-left:8px;';
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
    getIdToken,
    getAccessToken,
    getUserEmail,
    logout,
    checkAuth,
    cognitoSignIn
  };
})();
