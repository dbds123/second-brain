// Athletics Modul

const Athletics = (() => {
  const TAGE = ['Mo','Di','Mi','Do','Fr','Sa','So'];

  // Heutigen Wochentag bestimmen (0=Mo ... 6=So)
  function heuteIdx() { return (new Date().getDay() + 6) % 7; }

  // Plan für diese Woche (Mock)
  const woche = [
    { status:'done'  },
    { status:'done'  },
    { status:'rest'  },
    { status:'done'  },
    { status:'done'  },
    { status:'today' },
    { status:'rest'  },
  ];
  // Heutigen Tag korrekt markieren
  woche.forEach((d,i) => { if (i === heuteIdx()) d.status = 'today'; });

  const oneRM  = Store.get('athletics').oneRM || { bench:82, squat:120, deadlift:140 };
  const block  = Store.get('athletics').block  || { name:'Strength Block', woche:6, gesamtWochen:8 };

  const heutigesTraining = [
    { name:'Bench Press',       sets:'5 × 5', gewicht:'70kg' },
    { name:'Overhead Press',    sets:'4 × 6', gewicht:'45kg' },
    { name:'Incline Dumbbell',  sets:'3 × 10', gewicht:'22kg' },
    { name:'Lateral Raises',    sets:'3 × 12', gewicht:'' },
    { name:'Triceps Pushdown',  sets:'3 × 12', gewicht:'' },
  ];

  function render(el) {
    const done = woche.filter(d => d.status === 'done').length;

    const dayDivs = woche.map((d, i) => `
      <div class="ath-day ${d.status}" data-idx="${i}">
        <div class="ath-day-name">${TAGE[i]}</div>
        <div class="ath-day-icon">${d.status==='done' ? '●' : d.status==='today' ? '→' : '○'}</div>
      </div>
    `).join('');

    const workoutRows = heutigesTraining.map(u => `
      <div class="workout-row">
        <span>${u.name}</span>
        <span>${u.sets}${u.gewicht ? ' @ '+u.gewicht : ''}</span>
      </div>
    `).join('');

    el.innerHTML = `
      <div class="athletics-grid">

        <div class="card athletics-card">
          <div style="display:flex;justify-content:space-between;align-items:flex-end">
            <div>
              <div class="row-title">Diese Woche</div>
              <div class="row-meta" style="margin-top:4px">${done} / 5 Sessions absolviert</div>
            </div>
            <div style="font-family:'Geist Mono';font-size:0.7rem;color:var(--muted)">${block.name} · Woche ${block.woche}/${block.gesamtWochen}</div>
          </div>
          <div class="ath-week">${dayDivs}</div>
          <div class="ath-stats">
            <div class="ath-stat-mini">
              <div class="ath-stat-mini-val">${oneRM.bench}<span style="font-size:0.7rem;color:var(--muted)">kg</span></div>
              <div class="ath-stat-mini-label">Bench 1RM</div>
            </div>
            <div class="ath-stat-mini">
              <div class="ath-stat-mini-val">${oneRM.deadlift}<span style="font-size:0.7rem;color:var(--muted)">kg</span></div>
              <div class="ath-stat-mini-label">Deadlift 1RM</div>
            </div>
            <div class="ath-stat-mini">
              <div class="ath-stat-mini-val">${oneRM.squat}<span style="font-size:0.7rem;color:var(--muted)">kg</span></div>
              <div class="ath-stat-mini-label">Squat 1RM</div>
            </div>
          </div>
        </div>

        <div class="card athletics-card">
          <div>
            <div class="row-title">Heute · Push Day</div>
            <div class="row-meta" style="margin-top:4px">~75 Min · ${heutigesTraining.length} Übungen</div>
          </div>
          <div style="margin-top:20px;display:flex;flex-direction:column;gap:8px">
            ${workoutRows}
          </div>
        </div>

      </div>
    `;

    // Day-Toggle
    el.querySelectorAll('.ath-day').forEach(d => {
      d.addEventListener('click', () => {
        if (d.classList.contains('today')) return;
        const idx = parseInt(d.dataset.idx);
        woche[idx].status = woche[idx].status === 'done' ? '' : 'done';
        render(el);
      });
    });
  }

  return {
    init() {
      const el = document.getElementById('athletics-container');
      if (el) render(el);

      // Section header dynamisch
      const t = document.getElementById('ath-block-title');
      const m = document.getElementById('ath-block-meta');
      if (t) t.innerHTML = `${block.name} — <strong>Woche ${block.woche}.</strong>`;
      if (m) m.textContent = `Woche ${block.woche} von ${block.gesamtWochen} · Push / Pull / Legs`;
    }
  };
})();
