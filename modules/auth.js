// Auth — OAuth Token-Management für Gmail

const Auth = (() => {
  const TOKEN_KEY  = 'sb_tokens';
  const CONFIG_KEY = 'sb_config';

  const GMAIL_CLIENT_ID = '820791360039-hrugig7qhl75kjl9usgs6ie8u10ghhpb.apps.googleusercontent.com';

  // ── Config ───────────────────────────────────────────────────────────────────
  function getConfig() {
    const base = { gmailClientId: GMAIL_CLIENT_ID };
    try { return Object.assign(base, JSON.parse(localStorage.getItem(CONFIG_KEY) || '{}')); }
    catch { return base; }
  }

  function setConfig(key, value) {
    const c = getConfig();
    c[key] = value;
    localStorage.setItem(CONFIG_KEY, JSON.stringify(c));
  }

  // ── Token Storage ────────────────────────────────────────────────────────────
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

  // ── OAuth Callback ───────────────────────────────────────────────────────────
  // Wird aufgerufen wenn die Seite nach OAuth-Redirect geladen wird.
  // Läuft sowohl im Popup als auch im Hauptfenster.
  function handleCallback() {
    const hash = window.location.hash;
    if (!hash || !hash.includes('access_token')) return null;

    const params    = new URLSearchParams(hash.replace(/^#/, ''));
    const token     = params.get('access_token');
    const state     = params.get('state');
    const expiresIn = parseInt(params.get('expires_in') || '3600', 10);

    if (token && state) {
      saveToken(state, token, expiresIn);
      history.replaceState(null, '', window.location.pathname);

      // Im Popup: Hauptfenster aktualisieren und Popup schließen
      if (window.opener && !window.opener.closed) {
        try { window.opener.Mail.init(); } catch (_) {}
        window.close();
      }

      return state;
    }
    return null;
  }

  // ── Gmail OAuth — öffnet Popup statt Redirect ────────────────────────────────
  function connectGmail() {
    const clientId = getConfig().gmailClientId?.trim() || GMAIL_CLIENT_ID;

    const params = new URLSearchParams({
      client_id:     clientId,
      redirect_uri:  window.location.origin + window.location.pathname,
      response_type: 'token',
      scope:         'https://www.googleapis.com/auth/gmail.readonly',
      state:         'gmail',
      prompt:        'select_account',
    });

    const url    = `https://accounts.google.com/o/oauth2/v2/auth?${params}`;
    const popup  = window.open(url, 'gmail-auth', 'width=520,height=640,left=200,top=80');

    // Fallback: wenn Popup geblockt → normaler Redirect
    if (!popup || popup.closed) {
      window.location.href = url;
      return;
    }

    // Polling — nach Popup-Close Mail neu laden falls Token gespeichert wurde
    const poll = setInterval(() => {
      try {
        if (popup.closed) {
          clearInterval(poll);
          if (isConnected('gmail')) Mail.init();
        }
      } catch (_) { clearInterval(poll); }
    }, 500);
  }

  return { handleCallback, connectGmail, getToken, disconnect, isConnected, getConfig, setConfig };
})();
