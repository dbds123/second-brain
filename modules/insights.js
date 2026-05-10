// Insights — Wheel of Life

const Insights = (() => {
  const BEREICHE = [
    'Academics','Career','Health & Body','Finance','Relationships','Growth & Skills','Fun & Joy','Mind & Spirit'
  ];

  function ladeDaten() {
    const d = Store.get('insights');
    if (!d.bereiche || d.bereiche.length !== 8) {
      return { bereiche: [7, 6, 8, 5, 7, 8, 6, 7] };
    }
    return { bereiche: d.bereiche.map(b => typeof b === 'number' ? b : b.wert) };
  }

  function speichern(werte) {
    Store.set('insights', { bereiche: werte });
  }

  // SVG-Polygon aus 8 Werten berechnen
  function polygon(werte, cx, cy, maxR) {
    return werte.map((v, i) => {
      const a = (i / 8) * Math.PI * 2 - Math.PI / 2;
      const r = (v / 10) * maxR;
      return `${cx + Math.cos(a) * r},${cy + Math.sin(a) * r}`;
    }).join(' ');
  }

  function axisEnd(i, cx, cy, r) {
    const a = (i / 8) * Math.PI * 2 - Math.PI / 2;
    return { x: cx + Math.cos(a) * r, y: cy + Math.sin(a) * r };
  }

  function labelPos(i, cx, cy) {
    const a = (i / 8) * Math.PI * 2 - Math.PI / 2;
    const r = 190;
    return { x: cx + Math.cos(a) * r, y: cy + Math.sin(a) * r };
  }

  function render(el) {
    const { bereiche } = ladeDaten();
    const cx = 200, cy = 200;

    const achsen = BEREICHE.map((_,i) => {
      const e = axisEnd(i, cx, cy, 160);
      return `<line x1="${cx}" y1="${cy}" x2="${e.x}" y2="${e.y}" stroke="rgba(255,255,255,0.05)" stroke-width="1"/>`;
    }).join('');

    const labels = BEREICHE.map((b,i) => {
      const p = labelPos(i, cx, cy);
      const anchor = p.x < cx - 5 ? 'end' : p.x > cx + 5 ? 'start' : 'middle';
      const shortLabel = b.split(' ')[0].toUpperCase();
      return `<text x="${p.x}" y="${p.y+4}" text-anchor="${anchor}" fill="rgba(255,255,255,0.5)" font-family="Geist Mono" font-size="9">${shortLabel}</text>`;
    }).join('');

    const ringe = [40,80,120,160].map(r => `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="1"/>`).join('');

    const poly = polygon(bereiche, cx, cy, 160);

    const punkte = bereiche.map((v,i) => {
      const a = (i / 8) * Math.PI * 2 - Math.PI / 2;
      const r = (v / 10) * 160;
      return `<circle cx="${cx + Math.cos(a)*r}" cy="${cy + Math.sin(a)*r}" r="4" fill="#fafafa"/>`;
    }).join('');

    const legRows = BEREICHE.map((b,i) => `
      <div class="wheel-leg-row" data-idx="${i}">
        <div class="wheel-leg-name">${b}</div>
        <div class="wheel-leg-bar">
          <div class="wheel-leg-fill" style="width:${bereiche[i]*10}%"></div>
        </div>
        <div class="wheel-leg-val">${bereiche[i].toFixed(1)}</div>
      </div>
    `).join('');

    el.innerHTML = `
      <div class="card wheel-card">
        <div class="wheel-svg-wrap">
          <svg viewBox="0 0 400 400" id="wheel-svg">
            ${ringe}
            ${achsen}
            <polygon points="${poly}" fill="rgba(255,255,255,0.08)" stroke="#fafafa" stroke-width="2" stroke-linejoin="round"/>
            ${punkte}
            ${labels}
          </svg>
        </div>
        <div class="wheel-legend">${legRows}</div>
      </div>
    `;

    // Klick auf Legende → Wert toggeln (einfacher Increment-Cycle 1–10)
    el.querySelectorAll('.wheel-leg-row').forEach(row => {
      row.addEventListener('click', () => {
        const i = parseInt(row.dataset.idx);
        bereiche[i] = bereiche[i] >= 10 ? 1 : bereiche[i] + 1;
        speichern(bereiche);
        render(el);
      });
    });
  }

  return {
    init() {
      const el = document.getElementById('insights-container');
      if (el) render(el);

      // Monatsname
      const m = document.getElementById('insights-month');
      if (m) {
        const jetzt = new Date();
        m.textContent = jetzt.toLocaleDateString('de-DE', { month:'long', year:'numeric' }) + '.';
      }
    }
  };
})();
