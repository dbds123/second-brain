// Auth — OAuth Token-Management für Gmail + Microsoft Graph

const Auth = (() => {
  const TOKEN_KEY  = 'sb_tokens';
  const CONFIG_KEY = 'sb_config';

  // ── Config (Client IDs) ──────────────────────────────────────────────────
  function getConfig() {
    try { return JSON.parse(localStorage.getItem(CONFIG_KEY) || '{}'); }
    catch { return {}; }
  }

  function setConfig(key, value) {
    const c = getConfig();
    c[key] = value;
    localStorage.setItem(CONFIG_KEY, JSON.stringify(c));
  }

  // ── Token Storage ────────────────────────────────────────────────────────
  function allTokens() {
    try { return JSON.parse(localStorage.getItem(TOKEN_KEY) || '{}'); }
    catch { return {}; }
  }

  function saveToken(provider, token, expiresIn) {
    const all = allTokens();
    all[provider] = { token, expiry: Date.now() + expiresIn * 1000 - 60_000 };
    localStorage.setItem(TOKEN_KEY, JSON.stringify(all));
  }

  function getToken(provider) {
    const t = allTokens()[provider];
    if (!t) return null;
    if (Date.now() > t.expiry) { disconnect(provider); return null; }
    return t.token;
  }

  function disconnect(provider) {
    const all = allTokens();
    delete all[provider];
    localStorage.setItem(TOKEN_KEY, JSON.stringify(all));
  }

  function isConnected(provider) { return !!getToken(provider); }

  // ── OAuth Callback (Token aus URL-Hash lesen nach Redirect) ──────────────
  function handleCallback() {
    const hash = window.location.hash;
    if (!hash || !hash.includes('access_token')) return null;

    const params = new URLSearchParams(hash.replace(/^#/, ''));
    const token     = params.get('access_token');
    const state     = params.get('state');
    const expiresIn = parseInt(params.get('expires_in') || '3600', 10);

    if (token && state) {
      saveToken(state, token, expiresIn);
      history.replaceState(null, '', window.location.pathname);
      return state; // 'gmail' oder 'microsoft'
    }
    return null;
  }

  // ── Gmail OAuth Redirect ─────────────────────────────────────────────────
  function connectGmail() {
    const clientId = getConfig().gmailClientId?.trim();
    if (!clientId) { alert('Bitte zuerst die Gmail Client ID eintragen.'); return; }

    const params = new URLSearchParams({
      client_id:     clientId,
      redirect_uri:  window.location.origin + '/',
      response_type: 'token',
      scope:         'https://www.googleapis.com/auth/gmail.readonly',
      state:         'gmail',
      prompt:        'select_account'
    });
    window.location.href = `https://accounts.google.com/o/oauth2/v2/auth?${params}`;
  }

  // ── Microsoft OAuth Redirect (Implicit, benötigt Azure App-Config) ───────
  function connectMicrosoft() {
    const clientId = getConfig().msClientId?.trim();
    if (!clientId) { alert('Bitte zuerst die Microsoft Client ID eintragen.'); return; }

    const params = new URLSearchParams({
      client_id:     clientId,
      redirect_uri:  window.location.origin + '/',
      response_type: 'token',
      scope:         'https://graph.microsoft.com/Mail.Read',
      state:         'microsoft',
      response_mode: 'fragment',
      prompt:        'select_account'
    });
    window.location.href = `https://login.microsoftonline.com/common/oauth2/v2.0/authorize?${params}`;
  }

  return { handleCallback, connectGmail, connectMicrosoft, getToken, disconnect, isConnected, getConfig, setConfig };
})();
