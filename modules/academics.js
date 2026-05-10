// Academics Modul — Mathe Master, horizontaler Modul-Editor, Seminar-Support

const Academics = (() => {
  function uid() { return Date.now().toString(36) + Math.random().toString(36).slice(2,5); }

  const STD_MODULE = [
    {
      id: uid(), code: 'SEM-ST', name: 'Seminar Statistik / Stochastik',
      cp: 4, prog: 25, note: null, status: 'aktiv', typ: 'seminar',
      klausur: null, thema: '', betreuer: '', vortrag: null
    },
    {
      id: uid(), code: 'MA-1', name: 'Modul — zum Umbenennen klicken',
      cp: 9, prog: 30, note: null, status: 'aktiv', typ: 'vorlesung',
      klausur: null, thema: '', betreuer: '', vortrag: null
    },
    {
      id: uid(), code: 'MA-2', name: 'Modul — zum Umbenennen klicken',
      cp: 9, prog: 20, note: null, status: 'aktiv', typ: 'vorlesung',
      klausur: null, thema: '', betreuer: '', vortrag: null
    },
  ];

  const STD_TODOS = [
    { id: uid(), text: 'Seminar-Thema festlegen',       modul: 'SEM-ST', faellig: '2026-05-15', erledigt: false },
    { id: uid(), text: 'Literaturrecherche beginnen',   modul: 'SEM-ST', faellig: '2026-05-22', erledigt: false },
    { id: uid(), text: 'Erstes Treffen mit Betreuer',   modul: 'SEM-ST', faellig: '2026-05-20', erledigt: false },
  ];

  let daten = Store.get('academics');
  if (!Array.isArray(daten.module) || daten.module.length === 0) {
    daten = { module: STD_MODULE, todos: STD_TODOS };
    Store.set('academics', daten);
  }
  // Migration: alte Module ohne typ/thema/betreuer/vortrag ergänzen
  daten.module.forEach(m => {
    if (!m.typ)      m.typ      = 'vorlesung';
    if (!m.thema)    m.thema    = '';
    if (!m.betreuer) m.betreuer = '';
    if (m.vortrag === undefined) m.vortrag = null;
  });

  let gewaehlteId = null; // aktuell geöffnetes Modul im Editor

  function speichern() { Store.set('academics', daten); }

  function schnitt() {
    const b = daten.module.filter(m => m.note !== null);
    if (!b.length) return null;
    return (b.reduce((s,m) => s + m.note * m.cp, 0) / b.reduce((s,m) => s + m.cp, 0)).toFixed(2);
  }
  function cpGes() { return daten.module.filter(m => m.status === 'bestanden').reduce((s,m) => s+m.cp, 0); }
  function tagesBis(str) {
    if (!str) return null;
    const h = new Date(); h.setHours(0,0,0,0);
    const z = new Date(str); z.setHours(0,0,0,0);
    return Math.round((z-h)/86400000);
  }
  function datDE(str) {
    if (!str) return '—';
    return new Date(str).toLocaleDateString('de-DE', { day:'numeric', month:'short' });
  }
  function noteKlasse(n) {
    if (n === null) return 'grade-pending';
    if (n <= 1.7)   return 'grade-good';
    if (n <= 2.3)   return 'grade-ok';
    return 'grade-warn';
  }

  // ── Stat-Grid ──────────────────────────────────────────────────────────────
  function renderStats() {
    const sn  = schnitt();
    const cp  = cpGes();
    const pct = Math.round(cp / 120 * 100); // Master = 120 CP
    const next = daten.module
      .filter(m => m.klausur && tagesBis(m.klausur) >= 0)
      .sort((a,b) => new Date(a.klausur) - new Date(b.klausur))[0];
    const aktiv = daten.module.filter(m => m.status === 'aktiv').length;

    return `
      <div class="stat-grid stat-grid-4" style="margin-bottom:14px">
        <div class="stat-card">
          <div class="sc-label">Schnitt aktuell</div>
          <div class="sc-val">${sn ?? '—'}</div>
          <div class="sc-meta">${sn ? 'gewichtet nach CP' : 'Noch keine Noten'}</div>
          <div class="sc-bar"><div class="sc-bar-fill" style="width:${sn ? Math.round((3-Math.min(sn,3))/2*100) : 0}%"></div></div>
        </div>
        <div class="stat-card">
          <div class="sc-label">CP gesammelt</div>
          <div class="sc-val">${cp}<span class="acc"> / 120</span></div>
          <div class="sc-meta">${pct}% des Masters</div>
          <div class="sc-bar"><div class="sc-bar-fill" style="width:${Math.min(pct,100)}%"></div></div>
        </div>
        <div class="stat-card">
          <div class="sc-label">Module aktiv</div>
          <div class="sc-val">${aktiv}</div>
          <div class="sc-meta">${daten.module.filter(m=>m.typ==='seminar').length} Seminar(e)</div>
          <div class="sc-bar"><div class="sc-bar-fill" style="width:100%"></div></div>
        </div>
        <div class="stat-card">
          <div class="sc-label">Nächste Klausur</div>
          <div class="sc-val">${next ? tagesBis(next.klausur)+'<span class="acc">d</span>' : '—'}</div>
          <div class="sc-meta">${next ? next.code+' · '+datDE(next.klausur) : 'Keine geplant'}</div>
          ${next ? `<div class="sc-bar"><div class="sc-bar-fill" style="width:${Math.max(5,100-tagesBis(next.klausur))}%"></div></div>` : ''}
        </div>
      </div>
    `;
  }

  // ── Horizontaler Modul-Editor ──────────────────────────────────────────────
  function renderEditor() {
    const m = daten.module.find(x => x.id === gewaehlteId);
    if (!m) {
      return `
        <div class="modul-editor" id="modul-editor">
          <div class="editor-hint">Klicke ein Modul an um es zu bearbeiten</div>
        </div>
      `;
    }

    const seminarFelder = m.typ === 'seminar' ? `
      <div class="editor-row" style="padding-top:12px;border-top:1px solid var(--border);margin-top:4px">
        <div class="ef" style="flex:3">
          <label>Seminar-Thema</label>
          <input class="ef-input" data-f="thema" value="${m.thema}" placeholder="Thema des Vortrags...">
        </div>
        <div class="ef" style="flex:1.5">
          <label>Betreuer</label>
          <input class="ef-input" data-f="betreuer" value="${m.betreuer}" placeholder="Prof. Dr. ...">
        </div>
        <div class="ef" style="flex:1">
          <label>Vortragsdatum</label>
          <input class="ef-input" data-f="vortrag" type="date" value="${m.vortrag ?? ''}">
        </div>
      </div>
    ` : '';

    return `
      <div class="modul-editor active" id="modul-editor" data-id="${m.id}">
        <div class="editor-row">
          <div class="ef" style="flex:0 0 80px">
            <label>Code</label>
            <input class="ef-input mono" data-f="code" value="${m.code}">
          </div>
          <div class="ef" style="flex:3">
            <label>Name</label>
            <input class="ef-input" data-f="name" value="${m.name}">
          </div>
          <div class="ef" style="flex:0 0 50px">
            <label>CP</label>
            <input class="ef-input mono" data-f="cp" type="number" value="${m.cp}" min="1" max="30">
          </div>
          <div class="ef" style="flex:0 0 100px">
            <label>Typ</label>
            <select class="ef-input" data-f="typ">
              <option value="vorlesung"  ${m.typ==='vorlesung'  ? 'selected':''}>Vorlesung</option>
              <option value="seminar"    ${m.typ==='seminar'    ? 'selected':''}>Seminar</option>
              <option value="praktikum"  ${m.typ==='praktikum'  ? 'selected':''}>Praktikum</option>
              <option value="projekt"    ${m.typ==='projekt'    ? 'selected':''}>Projekt</option>
            </select>
          </div>
          <div class="ef" style="flex:0 0 110px">
            <label>Status</label>
            <select class="ef-input" data-f="status">
              <option value="aktiv"     ${m.status==='aktiv'     ? 'selected':''}>Aktiv</option>
              <option value="bestanden" ${m.status==='bestanden' ? 'selected':''}>Bestanden</option>
              <option value="offen"     ${m.status==='offen'     ? 'selected':''}>Offen</option>
            </select>
          </div>
          <div class="ef" style="flex:0 0 60px">
            <label>Note</label>
            <input class="ef-input mono ${noteKlasse(m.note)}" data-f="note" type="number"
                   value="${m.note ?? ''}" placeholder="—" min="1" max="5" step="0.1"
                   style="color:inherit">
          </div>
          <div class="ef" style="flex:0 0 130px">
            <label>${m.typ === 'seminar' ? 'Abgabe' : 'Klausur'}</label>
            <input class="ef-input" data-f="klausur" type="date" value="${m.klausur ?? ''}">
          </div>
          <div class="ef" style="flex:0 0 60px">
            <label>Fortschritt</label>
            <input class="ef-input mono" data-f="prog" type="number"
                   value="${m.prog}" min="0" max="100" style="width:100%">
          </div>
          <button class="editor-close" id="editor-close">✕</button>
        </div>
        ${seminarFelder}
      </div>
    `;
  }

  // ── Modul-Liste (kompakt, klickbar) ───────────────────────────────────────
  function renderModulListe() {
    const typBadge = { vorlesung:'VL', seminar:'SEM', praktikum:'PR', projekt:'PJ' };

    const zeilen = daten.module.map(m => {
      const aktiv   = m.id === gewaehlteId;
      const tage    = tagesBis(m.klausur);
      const klInfo  = tage !== null
        ? `<span class="modul-row-datum ${tage<=21?'bald':''}">${tage}d · ${datDE(m.klausur)}</span>`
        : '';

      return `
        <div class="modul-row-neu ${aktiv ? 'aktiv' : ''}" data-id="${m.id}">
          <span class="modul-typ-badge">${typBadge[m.typ] ?? 'VL'}</span>
          <span class="modul-row-code mono">${m.code}</span>
          <span class="modul-row-name">${m.name}</span>
          <span class="modul-row-cp mono">${m.cp} CP</span>
          <div class="modul-row-prog">
            <div class="module-prog-bar"><div class="module-prog-fill" style="width:${m.prog}%"></div></div>
            <span class="module-prog-pct">${m.prog}%</span>
          </div>
          <span class="modul-row-note ${noteKlasse(m.note)}">${m.note ?? '—'}</span>
          ${klInfo}
          <button class="del-btn" data-id="${m.id}">×</button>
        </div>
      `;
    }).join('');

    return `
      <div class="card modules-card" style="margin-bottom:14px">
        <div class="modules-head">
          <div>
            <div class="row-title">Module · Master Mathematik · Sem. 1</div>
            <div class="row-meta">${daten.module.length} Module · ${daten.module.reduce((s,m)=>s+m.cp,0)} CP · Klicken zum Bearbeiten</div>
          </div>
          <button class="ghost-btn" id="add-modul-btn">+ Modul</button>
        </div>
        <div class="modul-liste" id="modul-liste">${zeilen}</div>
      </div>
    `;
  }

  // ── Todos ─────────────────────────────────────────────────────────────────
  function renderTodos() {
    const sortiert = [...daten.todos].sort((a,b) => {
      if (a.erledigt !== b.erledigt) return a.erledigt ? 1 : -1;
      return new Date(a.faellig||'9999') - new Date(b.faellig||'9999');
    });

    const items = sortiert.map(t => {
      const tage   = tagesBis(t.faellig);
      const urgent = !t.erledigt && tage !== null && tage <= 2;
      const zeitText = t.erledigt ? 'erledigt'
        : tage === 0 ? 'heute' : tage === 1 ? 'morgen' : datDE(t.faellig);
      return `
        <div class="todo-item" data-id="${t.id}">
          <div class="todo-check ${t.erledigt ? 'done' : ''}"></div>
          <div class="todo-text ${t.erledigt ? 'done' : ''}">${t.text}</div>
          <div class="todo-tag">${t.modul}</div>
          <div class="todo-due ${urgent ? 'urgent' : ''}">${zeitText}</div>
        </div>
      `;
    }).join('');

    const offen = daten.todos.filter(t=>!t.erledigt).length;
    return `
      <div class="card todo-card">
        <div class="todo-head">
          <div>
            <div class="row-title">Aufgaben</div>
            <div class="row-meta">${offen} offen · ${daten.todos.length - offen} erledigt</div>
          </div>
          <button class="ghost-btn" id="add-todo-btn">+ Aufgabe</button>
        </div>
        <div class="todo-list-inner">${items || '<div style="padding:16px 24px;color:var(--muted);font-size:0.82rem">Keine Aufgaben.</div>'}</div>
        <div class="todo-add-row hidden" id="todo-add-row">
          <input class="ghost-input" id="ti-text"  placeholder="Aufgabe..." style="flex:2">
          <input class="ghost-input sm" id="ti-modul" placeholder="Modul">
          <input class="ghost-input md" id="ti-datum" type="date">
          <button class="ghost-btn" id="ti-save">↵ Speichern</button>
          <button class="ghost-btn" id="ti-cancel">✕</button>
        </div>
      </div>
    `;
  }

  // ── Grade Chart (SVG) ─────────────────────────────────────────────────────
  function renderGradeChart() {
    const sn = parseFloat(schnitt()) || null;
    if (!sn) return '';

    const yFor = n => 20 + (n - 1.0) / 2.5 * 170;
    const pts  = [{ x:0, n:sn }]; // Nur Sem 1 bisher
    const future = [{ x:400, n: Math.max(1.0, sn-0.1) }, { x:800, n: Math.max(1.0, sn-0.2) }];
    const line = `M 0,${yFor(pts[0].n)}`;
    const area = `M 0,${yFor(pts[0].n)} L 0,200 Z`;
    const fLine = `M 0,${yFor(pts[0].n)} L ${future[0].x},${yFor(future[0].n)} L ${future[1].x},${yFor(future[1].n)}`;

    return `
      <div class="card grade-chart-card">
        <div class="gcc-head">
          <div>
            <div class="gcc-title">Notenverlauf</div>
            <div class="gcc-sub">Master Mathematik · Semester 1 → Abschluss</div>
          </div>
          <div style="text-align:right">
            <div class="gcc-current">${sn}</div>
            <div class="gcc-current-label">Aktuell</div>
          </div>
        </div>
        <svg class="gcc-svg" viewBox="0 0 800 200" preserveAspectRatio="none">
          <line x1="0" y1="${yFor(2.0)}" x2="800" y2="${yFor(2.0)}" stroke="rgba(255,255,255,0.05)" stroke-width="1"/>
          <line x1="0" y1="${yFor(2.5)}" x2="800" y2="${yFor(2.5)}" stroke="rgba(255,255,255,0.05)" stroke-width="1"/>
          <path d="${fLine}" fill="none" stroke="rgba(255,255,255,0.4)" stroke-width="1.5" stroke-dasharray="4,4" stroke-linecap="round"/>
          <circle cx="0" cy="${yFor(pts[0].n)}" r="5" fill="#fafafa" stroke="#0c0c10" stroke-width="2"/>
          <text x="6" y="${yFor(2.0)+4}" fill="rgba(255,255,255,0.4)" font-family="Geist Mono" font-size="10">2,0</text>
          <text x="6" y="${yFor(2.5)+4}" fill="rgba(255,255,255,0.4)" font-family="Geist Mono" font-size="10">2,5</text>
          <line x1="0" y1="0" x2="0" y2="200" stroke="rgba(255,255,255,0.15)" stroke-dasharray="2,3"/>
          <text x="8" y="14" fill="rgba(255,255,255,0.4)" font-family="Geist Mono" font-size="9">JETZT</text>
        </svg>
        <div class="gcc-axis-labels">
          <span>Sem 1</span><span>Sem 2</span><span>Sem 3</span><span>Sem 4 →</span><span>Abschluss</span>
        </div>
      </div>
    `;
  }

  // ── Events ────────────────────────────────────────────────────────────────
  function bindEvents(el) {
    // Modul-Zeile anklicken → Editor öffnen
    el.querySelectorAll('.modul-row-neu').forEach(row => {
      row.addEventListener('click', e => {
        if (e.target.classList.contains('del-btn')) return;
        const id = row.dataset.id;
        gewaehlteId = gewaehlteId === id ? null : id;
        aktualisieren();
      });
    });

    // Editor: Felder speichern bei Change
    const editor = el.querySelector('#modul-editor');
    if (editor) {
      editor.querySelectorAll('.ef-input').forEach(inp => {
        const save = () => {
          const id = editor.dataset.id;
          if (!id) return;
          const m = daten.module.find(x => x.id === id);
          if (!m) return;
          let v = inp.value;
          const f = inp.dataset.f;
          if (f === 'cp' || f === 'prog') v = parseInt(v) || 0;
          if (f === 'note')    v = v !== '' ? parseFloat(v) : null;
          if (f === 'klausur' || f === 'vortrag') v = v || null;
          m[f] = v;
          speichern();
          // Nur die Liste + Stats updaten, nicht den Editor (Fokus bleibt)
          renderListeUndStats(el);
        };
        inp.addEventListener('change', save);
        inp.addEventListener('keydown', e => { if (e.key === 'Enter') inp.blur(); });
      });

      // Editor schließen
      el.querySelector('#editor-close')?.addEventListener('click', () => {
        gewaehlteId = null;
        aktualisieren();
      });
    }

    // Modul löschen
    el.querySelectorAll('.del-btn').forEach(b => {
      b.addEventListener('click', e => {
        e.stopPropagation();
        daten.module = daten.module.filter(m => m.id !== e.target.dataset.id);
        if (gewaehlteId === e.target.dataset.id) gewaehlteId = null;
        speichern(); aktualisieren();
      });
    });

    // Modul hinzufügen
    el.querySelector('#add-modul-btn')?.addEventListener('click', () => {
      const neu = { id:uid(), code:'NEU', name:'Neues Modul', cp:6, prog:0, note:null, status:'aktiv', typ:'vorlesung', klausur:null, thema:'', betreuer:'', vortrag:null };
      daten.module.push(neu);
      gewaehlteId = neu.id;
      speichern(); aktualisieren();
      setTimeout(() => el.querySelector(`#modul-editor .ef-input[data-f="name"]`)?.focus(), 50);
    });

    // Todo toggle
    el.querySelectorAll('.todo-item').forEach(item => {
      item.addEventListener('click', () => {
        const t = daten.todos.find(t => t.id === item.dataset.id);
        if (!t) return;
        t.erledigt = !t.erledigt;
        speichern();
        item.querySelector('.todo-check')?.classList.toggle('done', t.erledigt);
        item.querySelector('.todo-text')?.classList.toggle('done', t.erledigt);
        setTimeout(() => aktualisieren(), 300);
      });
    });

    // Todo Formular
    const addRow = el.querySelector('#todo-add-row');
    el.querySelector('#add-todo-btn')?.addEventListener('click', () => {
      addRow.classList.toggle('hidden');
      if (!addRow.classList.contains('hidden')) el.querySelector('#ti-text')?.focus();
    });
    el.querySelector('#ti-cancel')?.addEventListener('click', () => addRow.classList.add('hidden'));
    const saveTodo = () => {
      const text = el.querySelector('#ti-text')?.value?.trim();
      if (!text) return;
      daten.todos.push({ id:uid(), text, modul: el.querySelector('#ti-modul')?.value?.trim()||'—', faellig: el.querySelector('#ti-datum')?.value||null, erledigt:false });
      speichern(); aktualisieren();
    };
    el.querySelector('#ti-save')?.addEventListener('click', saveTodo);
    el.querySelector('#ti-text')?.addEventListener('keydown', e => { if (e.key==='Enter') saveTodo(); });
  }

  // Stats + Liste ohne Editor neu rendern (Editor-Fokus bleibt erhalten)
  function renderListeUndStats(el) {
    el.querySelector('.stat-grid')?.closest('.stat-grid')?.parentElement
      ?.querySelectorAll('.stat-grid')[0]?.replaceWith(
        Object.assign(document.createElement('div'), { innerHTML: renderStats() }).firstElementChild
      );
    const liste = el.querySelector('#modul-liste');
    if (liste) {
      const tmp = document.createElement('div');
      tmp.innerHTML = renderModulListe();
      const neu = tmp.querySelector('#modul-liste');
      if (neu) {
        liste.innerHTML = neu.innerHTML;
        // Events neu binden nur für Liste
        el.querySelectorAll('.modul-row-neu').forEach(row => {
          row.addEventListener('click', e => {
            if (e.target.classList.contains('del-btn')) return;
            const id = row.dataset.id;
            gewaehlteId = gewaehlteId === id ? null : id;
            aktualisieren();
          });
        });
        el.querySelectorAll('.del-btn').forEach(b => {
          b.addEventListener('click', e => {
            e.stopPropagation();
            daten.module = daten.module.filter(m => m.id !== e.target.dataset.id);
            if (gewaehlteId === e.target.dataset.id) gewaehlteId = null;
            speichern(); aktualisieren();
          });
        });
      }
    }
  }

  function aktualisieren() {
    const el = document.getElementById('academics-container');
    if (el) render(el);
  }

  function render(el) {
    el.innerHTML =
      renderStats() +
      renderEditor() +
      renderModulListe() +
      renderTodos() +
      renderGradeChart();
    bindEvents(el);
  }

  return {
    init() {
      const el = document.getElementById('academics-container');
      if (el) render(el);
    }
  };
})();
