// Mail — Gmail + RWTH Bridge Integration

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
  const RAUSCH_LABELS = new Set([
    'CATEGORY_PROMOTIONS', 'CATEGORY_SOCIAL',
    'CATEGORY_FORUMS', 'CATEGORY_UPDATES',
  ]);

  async function fetchGmailMessages(token) {
    const base    = 'https://gmail.googleapis.com/gmail/v1/users/me';
    const headers = { Authorization: `Bearer ${token}` };

    const listRes = await fetch(
      `${base}/messages?maxResults=30&labelIds=INBOX`, { headers }
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
      const d      = await r.json();
      const get    = name => (d.payload?.headers || []).find(h => h.name === name)?.value || '';
      const labels = d.labelIds || [];
      const fromRaw = get('From');
      const m = fromRaw.match(/^"?([^"<]+?)"?\s*(?:<.*>)?$/);
      const gelesen  = !labels.includes('UNREAD');
      const wichtig  = labels.includes('IMPORTANT');
      const rausch   = gelesen && !wichtig && labels.some(l => RAUSCH_LABELS.has(l));
      return {
        id,
        absender: m ? m[1].trim() : fromRaw,
        betreff:  get('Subject') || '(kein Betreff)',
        zeit:     zeitFormatieren(parseInt(d.internalDate, 10)),
        gelesen, wichtig, rausch,
        href:     `https://mail.google.com/mail/#inbox/${id}`,
      };
    }));

    return mails.filter(Boolean).slice(0, 20);
  }

  // ── RWTH Mail (lokale Bridge) ─────────────────────────────────────────────────
  const RWTH_BRIDGE = 'http://localhost:3334';

  async function rwthBridgeOnline() {
    try {
      const r = await fetch(`${RWTH_BRIDGE}/ping`, { signal: AbortSignal.timeout(800) });
      return r.ok;
    } catch { return false; }
  }

  async function fetchRwthMessages() {
    const r = await fetch(`${RWTH_BRIDGE}/mails`, { signal: AbortSignal.timeout(3000) });
    if (!r.ok) throw new Error(`RWTH Bridge: ${r.status}`);
    const data = await r.json();
    if (data.error) throw new Error(data.error);
    return (data.mails || []).map(m => ({
      ...m,
      rausch: false,
      href:   'https://mail.rwth-aachen.de/',
    }));
  }

  // ── Mail-Item HTML ───────────────────────────────────────────────────────────
  function mailItemHTML(m) {
    const flagClass = m.wichtig ? 'flag-warn' : (m.gelesen ? 'flag-ok' : 'flag-neu');
    return `
      <div class="mail-item${m.gelesen ? '' : ' ungelesen'}${m.rausch ? ' mail-item--rausch' : ''}"
           data-href="${escHtml(m.href)}">
        <div class="mail-flag ${flagClass}"></div>
        <div class="mail-body">
          <div class="mail-sender${m.gelesen ? ' read' : ''}">${escHtml(m.absender)}</div>
          <div class="mail-subject">${escHtml(m.betreff)}</div>
        </div>
        <div class="mail-zeit">${m.zeit}</div>
      </div>`;
  }

  // ── Konto-Karte ───────────────────────────────────────────────────────────────
  function kontoKarteHTML(name, badge, badgeStyle, listId, mails, fehler) {
    if (fehler) {
      return `
        <div class="card mail-account">
          <div class="mail-head">
            <div class="mail-head-left">
              <div class="mail-badge" ${badgeStyle}>${badge}</div>
              <div>
                <div class="mail-name">${name}</div>
                <div class="mail-addr error-text">Verbindungsfehler</div>
              </div>
            </div>
          </div>
          <div class="mail-error-msg">${escHtml(fehler)}</div>
        </div>`;
    }

    const ungelesen  = mails.filter(m => !m.gelesen).length;
    const wichtig    = mails.filter(m => m.wichtig).length;
    const rauschAnt  = mails.filter(m => m.rausch).length;
    const sichtbar   = mails.length - rauschAnt;

    const toggleBtn = rauschAnt > 0
      ? `<span class="row-action mail-toggle" data-list="${listId}" data-count="${rauschAnt}">${rauschAnt} weitere ↓</span>`
      : `<span>${mails.length} Nachrichten</span>`;

    return `
      <div class="card mail-account">
        <div class="mail-head">
          <div class="mail-head-left">
            <div class="mail-badge" ${badgeStyle}>${badge}</div>
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
        <div class="mail-list" id="${listId}">${mails.map(mailItemHTML).join('')}</div>
        <div class="row-foot">
          <span>${sichtbar} angezeigt</span>
          ${toggleBtn}
        </div>
      </div>`;
  }

  // ── Gmail Connect-Panel ───────────────────────────────────────────────────────
  function connectPanelHTML() {
    return `
      <div class="gmail-connect-banner">
        <div class="gmail-connect-info">
          <div class="mail-badge" style="background:rgba(234,67,53,0.12);border:1px solid rgba(234,67,53,0.3);color:#ff7060">G</div>
          <div>
            <div class="gmail-connect-title">Gmail verbinden</div>
            <div class="gmail-connect-sub">Klicke um dein Google-Konto zu autorisieren</div>
          </div>
        </div>
        <button class="connect-btn primary" id="btn-gmail-connect">Mit Gmail verbinden →</button>
      </div>`;
  }

  function bindConnectPanel(container) {
    container.querySelector('#btn-gmail-connect')
      ?.addEventListener('click', () => Auth.connectGmail());
  }

  // ── RWTH Offline-Karte ────────────────────────────────────────────────────────
  function rwthOfflineKarteHTML() {
    return `
      <div class="card mail-account">
        <div class="mail-head">
          <div class="mail-head-left">
            <div class="mail-badge" style="background:rgba(0,84,159,0.15);border:1px solid rgba(0,84,159,0.3);color:#5b9be0">M</div>
            <div>
              <div class="mail-name">RWTH Mail</div>
              <div class="mail-addr">daniel.brand@rwth-aachen.de</div>
            </div>
          </div>
        </div>
        <div class="mail-offline-msg">
          <div class="mail-offline-icon">◌</div>
          <div>
            <div class="mail-offline-title">Bridge nicht aktiv</div>
            <div class="mail-offline-sub">Starte <code>python rwth_mail.py</code> im second-brain Ordner um RWTH-Mails zu laden.</div>
          </div>
        </div>
      </div>`;
  }

  // ── Event-Binding (Toggle + Mail-Klick) ─────────────────────────────────────
  function bindGrid(grid) {
    grid.addEventListener('click', e => {
      // Toggle-Button
      const toggle = e.target.closest('.mail-toggle');
      if (toggle) {
        const list     = document.getElementById(toggle.dataset.list);
        const expanded = list.classList.toggle('mail-list--expanded');
        toggle.textContent = expanded
          ? 'Weniger ↑'
          : `${toggle.dataset.count} weitere ↓`;
        return;
      }

      // Mail anklicken → öffnen
      const item = e.target.closest('.mail-item');
      if (item?.dataset.href) {
        window.open(item.dataset.href, '_blank');
      }
    });
  }

  // ── Render ────────────────────────────────────────────────────────────────────
  async function render(container) {
    const gOk = Auth.isConnected('gmail');

    let html = !gOk ? connectPanelHTML() : '';
    html += '<div class="mail-grid" id="mail-grid"></div>';
    container.innerHTML = html;

    if (!gOk) bindConnectPanel(container);

    const grid = container.querySelector('#mail-grid');
    grid.innerHTML = '<div class="mail-skeleton">Lade Mails…</div>';

    const [gmailRes, rwthOnline] = await Promise.allSettled([
      gOk ? fetchGmailMessages(Auth.getToken('gmail')) : Promise.resolve(null),
      rwthBridgeOnline(),
    ]);

    const bridgeOnline = rwthOnline.status === 'fulfilled' && rwthOnline.value;
    const [rwthRes] = await Promise.allSettled([
      bridgeOnline ? fetchRwthMessages() : Promise.resolve(null),
    ]);

    let cards = '';
    const gBadge = 'style="background:rgba(234,67,53,0.12);border:1px solid rgba(234,67,53,0.3);color:#ff7060"';
    const mBadge = 'style="background:rgba(0,84,159,0.15);border:1px solid rgba(0,84,159,0.3);color:#5b9be0"';

    if (gOk) {
      cards += gmailRes.status === 'fulfilled' && gmailRes.value
        ? kontoKarteHTML('Gmail', 'G', gBadge, 'ml-gmail', gmailRes.value, null)
        : kontoKarteHTML('Gmail', 'G', gBadge, 'ml-gmail', [], gmailRes.reason?.message || 'Fehler');
    }

    if (bridgeOnline && rwthRes.status === 'fulfilled' && rwthRes.value) {
      cards += kontoKarteHTML('RWTH Mail', 'M', mBadge, 'ml-rwth', rwthRes.value, null);
    } else if (bridgeOnline) {
      cards += kontoKarteHTML('RWTH Mail', 'M', mBadge, 'ml-rwth', [], rwthRes.reason?.message || 'Fehler');
    } else {
      cards += rwthOfflineKarteHTML();
    }

    grid.innerHTML = cards;
    bindGrid(grid);

    const meta = document.getElementById('mail-sync-meta');
    if (meta) {
      const now = new Date();
      meta.textContent = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')} · ${gOk ? 'Gmail ✓' : 'Gmail —'} · RWTH ${bridgeOnline ? '✓' : '—'}`;
    }
  }

  // ── Init ──────────────────────────────────────────────────────────────────────
  function init() {
    const el = document.getElementById('mails-container');
    if (el) render(el);
  }

  return { init };
})();
