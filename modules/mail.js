// Mail — Gmail + Microsoft Graph Integration

const Mail = (() => {

  // ── Zeit formatieren ─────────────────────────────────────────────────────────
  function zeitFormatieren(ts) {
    const now  = Date.now();
    const diff = now - new Date(ts).getTime();
    const min  = Math.floor(diff / 60_000);
    const h    = Math.floor(diff / 3_600_000);
    const d    = Math.floor(diff / 86_400_000);
    if (min < 2)  return 'gerade';
    if (min < 60) return `${min}m`;
    if (h < 24)   return `${h}h`;
    if (d === 1)  return 'gestern';
    return `${d}d`;
  }

  function escHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  // ── Gmail API ────────────────────────────────────────────────────────────────
  async function fetchGmailMessages(token) {
    const base    = 'https://gmail.googleapis.com/gmail/v1/users/me';
    const headers = { Authorization: `Bearer ${token}` };

    const listRes = await fetch(
      `${base}/messages?maxResults=12&labelIds=INBOX`, { headers }
    );
    if (!listRes.ok) throw new Error(`Gmail: ${listRes.status}`);
    const listData = await listRes.json();
    const ids = (listData.messages || []).map(m => m.id);

    const mails = await Promise.all(ids.map(async id => {
      const r = await fetch(
        `${base}/messages/${id}?format=metadata` +
        `&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date`,
        { headers }
      );
      if (!r.ok) return null;
      const d   = await r.json();
      const get = name => (d.payload?.headers || []).find(h => h.name === name)?.value || '';
      const fromRaw = get('From');
      const m       = fromRaw.match(/^"?([^"<]+?)"?\s*(?:<.*>)?$/);
      return {
        id,
        absender: m ? m[1].trim() : fromRaw,
        betreff:  get('Subject') || '(kein Betreff)',
        zeit:     zeitFormatieren(parseInt(d.internalDate, 10)),
        gelesen:  !(d.labelIds || []).includes('UNREAD'),
        wichtig:  (d.labelIds || []).includes('IMPORTANT'),
      };
    }));

    return mails.filter(Boolean);
  }

  // ── Microsoft Graph API ──────────────────────────────────────────────────────
  async function fetchMicrosoftMessages(token) {
    const url = 'https://graph.microsoft.com/v1.0/me/mailFolders/Inbox/messages'
      + '?$top=12&$select=from,subject,receivedDateTime,isRead,importance'
      + '&$orderby=receivedDateTime desc';
    const r = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
    if (!r.ok) throw new Error(`Microsoft Graph: ${r.status}`);
    const data = await r.json();

    return (data.value || []).map(m => ({
      id:       m.id,
      absender: m.from?.emailAddress?.name || m.from?.emailAddress?.address || '?',
      betreff:  m.subject || '(kein Betreff)',
      zeit:     zeitFormatieren(m.receivedDateTime),
      gelesen:  m.isRead,
      wichtig:  m.importance === 'high',
    }));
  }

  // ── Mail-Item HTML ───────────────────────────────────────────────────────────
  function mailItemHTML(m) {
    const flagClass = m.wichtig ? 'flag-warn' : (m.gelesen ? 'flag-ok' : 'flag-neu');
    return `
      <div class="mail-item${m.gelesen ? '' : ' ungelesen'}">
        <div class="mail-flag ${flagClass}"></div>
        <div class="mail-body">
          <div class="mail-sender${m.gelesen ? ' read' : ''}">${escHtml(m.absender)}</div>
          <div class="mail-subject">${escHtml(m.betreff)}</div>
        </div>
        <div class="mail-zeit">${m.zeit}</div>
      </div>`;
  }

  // ── Konto-Karte ───────────────────────────────────────────────────────────────
  function kontoKarteHTML(name, badge, mails, fehler) {
    if (fehler) {
      return `
        <div class="card mail-account">
          <div class="mail-head">
            <div class="mail-head-left">
              <div class="mail-badge">${badge}</div>
              <div>
                <div class="mail-name">${name}</div>
                <div class="mail-addr error-text">Verbindungsfehler</div>
              </div>
            </div>
          </div>
          <div class="mail-error-msg">${escHtml(fehler)}</div>
        </div>`;
    }

    const ungelesen = mails.filter(m => !m.gelesen).length;
    const wichtig   = mails.filter(m => m.wichtig).length;

    return `
      <div class="card mail-account">
        <div class="mail-head">
          <div class="mail-head-left">
            <div class="mail-badge">${badge}</div>
            <div>
              <div class="mail-name">${name}</div>
              <div class="mail-addr">${ungelesen} ungelesen</div>
            </div>
          </div>
          <div class="mail-stats">
            <div class="mail-stat">
              <div class="mail-stat-val">${ungelesen}</div>
              <div class="mail-stat-label">Neu</div>
            </div>
            <div class="mail-stat">
              <div class="mail-stat-val${wichtig ? ' important' : ''}">${wichtig}</div>
              <div class="mail-stat-label">Wichtig</div>
            </div>
          </div>
        </div>
        <div class="mail-list">${mails.map(mailItemHTML).join('')}</div>
        <div class="row-foot">
          <span>${mails.length} Nachrichten geladen</span>
          <span class="row-action">Aktualisieren →</span>
        </div>
      </div>`;
  }

  // ── Connect-Panel ─────────────────────────────────────────────────────────────
  function connectPanelHTML() {
    const cfg = Auth.getConfig();
    const gOk = Auth.isConnected('gmail');
    const mOk = Auth.isConnected('microsoft');

    return `
      <div class="mail-connect-panel">

        <div class="connect-card${gOk ? ' connected' : ''}">
          <div class="connect-card-head">
            <div class="connect-provider">
              <div class="mail-badge" style="width:28px;height:28px;font-size:12px">G</div>
              <span class="connect-provider-label">Gmail</span>
            </div>
            <span class="connect-status-dot ${gOk ? 'ok' : 'off'}">
              ${gOk ? '● Verbunden' : '○ Getrennt'}
            </span>
          </div>
          ${gOk
            ? `<button class="connect-btn danger" id="btn-gmail-disconnect">Verbindung trennen</button>`
            : `<div class="connect-input-row">
                 <input class="connect-input" id="input-gmail-id" type="text"
                   placeholder="Google OAuth Client ID (aus Google Cloud Console)"
                   value="${escHtml(cfg.gmailClientId || '')}">
               </div>
               <div class="connect-actions">
                 <button class="connect-btn secondary" id="btn-gmail-save">ID speichern</button>
                 <button class="connect-btn primary" id="btn-gmail-connect">Mit Gmail verbinden →</button>
               </div>`
          }
        </div>

        <div class="connect-card${mOk ? ' connected' : ''}">
          <div class="connect-card-head">
            <div class="connect-provider">
              <div class="mail-badge" style="width:28px;height:28px;font-size:12px;background:rgba(0,120,212,0.3)">M</div>
              <span class="connect-provider-label">RWTH Mail (Microsoft 365)</span>
            </div>
            <span class="connect-status-dot ${mOk ? 'ok' : 'off'}">
              ${mOk ? '● Verbunden' : '○ Getrennt'}
            </span>
          </div>
          ${mOk
            ? `<button class="connect-btn danger" id="btn-ms-disconnect">Verbindung trennen</button>`
            : `<div class="connect-input-row">
                 <input class="connect-input" id="input-ms-id" type="text"
                   placeholder="Azure App (Client) ID"
                   value="${escHtml(cfg.msClientId || '')}">
               </div>
               <div class="connect-actions">
                 <button class="connect-btn secondary" id="btn-ms-save">ID speichern</button>
                 <button class="connect-btn primary" id="btn-ms-connect">Mit RWTH verbinden →</button>
               </div>`
          }
        </div>

      </div>`;
  }

  // ── Connect-Panel Events ──────────────────────────────────────────────────────
  function bindConnectPanel(container) {
    const q = id => container.querySelector(id);

    q('#btn-gmail-save')?.addEventListener('click', () => {
      const v = q('#input-gmail-id')?.value?.trim();
      if (v) Auth.setConfig('gmailClientId', v);
    });

    q('#btn-gmail-connect')?.addEventListener('click', () => {
      const v = q('#input-gmail-id')?.value?.trim();
      if (v) Auth.setConfig('gmailClientId', v);
      Auth.connectGmail();
    });

    q('#btn-gmail-disconnect')?.addEventListener('click', () => {
      Auth.disconnect('gmail');
      init();
    });

    q('#btn-ms-save')?.addEventListener('click', () => {
      const v = q('#input-ms-id')?.value?.trim();
      if (v) Auth.setConfig('msClientId', v);
    });

    q('#btn-ms-connect')?.addEventListener('click', () => {
      const v = q('#input-ms-id')?.value?.trim();
      if (v) Auth.setConfig('msClientId', v);
      Auth.connectMicrosoft();
    });

    q('#btn-ms-disconnect')?.addEventListener('click', () => {
      Auth.disconnect('microsoft');
      init();
    });
  }

  // ── Render ────────────────────────────────────────────────────────────────────
  async function render(container) {
    const gOk = Auth.isConnected('gmail');
    const mOk = Auth.isConnected('microsoft');

    // Settings-Panel immer oben wenn ein Konto fehlt
    let html = (!gOk || !mOk) ? connectPanelHTML() : '';
    html += '<div class="mail-grid" id="mail-grid"></div>';
    container.innerHTML = html;

    if (!gOk && !mOk) {
      bindConnectPanel(container);
      return;
    }

    if (!gOk || !mOk) bindConnectPanel(container);

    const grid = container.querySelector('#mail-grid');
    grid.innerHTML = '<div class="mail-skeleton">Lade Mails…</div>';

    const [gmailRes, msRes] = await Promise.allSettled([
      gOk ? fetchGmailMessages(Auth.getToken('gmail'))       : Promise.resolve(null),
      mOk ? fetchMicrosoftMessages(Auth.getToken('microsoft')): Promise.resolve(null),
    ]);

    let cards = '';

    if (gOk) {
      cards += gmailRes.status === 'fulfilled' && gmailRes.value
        ? kontoKarteHTML('Gmail', 'G', gmailRes.value, null)
        : kontoKarteHTML('Gmail', 'G', [], gmailRes.reason?.message || 'Fehler');
    }

    if (mOk) {
      cards += msRes.status === 'fulfilled' && msRes.value
        ? kontoKarteHTML('RWTH Mail', 'M', msRes.value, null)
        : kontoKarteHTML('RWTH Mail', 'M', [], msRes.reason?.message || 'Fehler');
    }

    grid.innerHTML = cards;

    // Sync-Meta
    const meta = document.getElementById('mail-sync-meta');
    if (meta) {
      const count = [gOk, mOk].filter(Boolean).length;
      const now = new Date();
      meta.textContent = `${count} Kont${count === 1 ? 'o' : 'en'} · `
        + `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
    }
  }

  // ── Init ──────────────────────────────────────────────────────────────────────
  function init() {
    const el = document.getElementById('mails-container');
    if (el) render(el);
  }

  return { init };
})();
