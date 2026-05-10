// JARVIS Background — portiert & erweitert
// Pulsierender Kern, Ringe, Hex, Radar-Sweep, orbitierende Partikel

(function () {
  const canvas = document.getElementById('jarvisCanvas');
  const ctx = canvas.getContext('2d');
  let W, H, cx, cy;

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width  = W * dpr;
    canvas.height = H * dpr;
    canvas.style.width  = W + 'px';
    canvas.style.height = H + 'px';
    ctx.scale(dpr, dpr);
    cx = W / 2;
    cy = H / 2;
  }

  resize();
  window.addEventListener('resize', () => {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    resize();
  });

  // Maus-Parallax (smooth lerp)
  let mx = 0, my = 0, tmx = 0, tmy = 0;
  document.addEventListener('mousemove', e => {
    tmx = (e.clientX / W - 0.5) * 30;
    tmy = (e.clientY / H - 0.5) * 30;
  });

  let scrollY = 0;
  window.addEventListener('scroll', () => { scrollY = window.scrollY; }, { passive: true });

  const t0 = performance.now();

  // Partikel kreisen um Zentrum
  const particles = [];
  for (let i = 0; i < 60; i++) {
    particles.push({
      angle:   Math.random() * Math.PI * 2,
      radius:  80 + Math.random() * 280,
      speed:   (0.05 + Math.random() * 0.2) * (Math.random() < 0.5 ? 1 : -1),
      size:    0.8 + Math.random() * 1.6,
      opacity: 0.2 + Math.random() * 0.5
    });
  }

  const TICK_COUNT = 72;

  function draw() {
    const t = (performance.now() - t0) / 1000;

    // Sanftes Maus-Tracking
    mx += (tmx - mx) * 0.05;
    my += (tmy - my) * 0.05;

    // Scroll-Fortschritt
    const docH = Math.max(1, document.body.scrollHeight - window.innerHeight);
    const sp = Math.min(scrollY / docH, 1);

    ctx.clearRect(0, 0, W, H);

    // Zentrum verschiebt sich mit Maus + Scroll
    const lcx = cx + mx + sp * 200;
    const lcy = cy + my * 0.5 - sp * 50;
    const ss  = 1 - sp * 0.4;   // scale bei Scroll

    // ── Pulsierender Kern ──
    const pulse = 0.5 + Math.sin(t * 1.6) * 0.5;
    ctx.fillStyle = `rgba(255,255,255,${0.7 + pulse * 0.3})`;
    ctx.beginPath();
    ctx.arc(lcx, lcy, (3 + pulse * 1.5) * ss, 0, Math.PI * 2);
    ctx.fill();

    // Weiches Glühen
    const grd = ctx.createRadialGradient(lcx, lcy, 0, lcx, lcy, 80 * ss);
    grd.addColorStop(0, 'rgba(255,255,255,0.12)');
    grd.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = grd;
    ctx.beginPath();
    ctx.arc(lcx, lcy, 80 * ss, 0, Math.PI * 2);
    ctx.fill();

    // ── Ring 1: segmentiert, rotierend ──
    const r1 = 70 * ss;
    ctx.strokeStyle = 'rgba(255,255,255,0.5)';
    ctx.lineWidth = 1;
    for (let i = 0; i < 8; i++) {
      const a = (i / 8) * Math.PI * 2 + t * 0.5;
      ctx.beginPath();
      ctx.arc(lcx, lcy, r1, a, a + Math.PI * 2 / 8 * 0.7);
      ctx.stroke();
    }

    // Tick-Marks um Ring 1
    const tickR = r1 + 12;
    for (let i = 0; i < TICK_COUNT; i++) {
      const a     = (i / TICK_COUNT) * Math.PI * 2;
      const isLng = i % 6 === 0;
      const len   = isLng ? 6 : 3;
      ctx.strokeStyle = isLng ? 'rgba(255,255,255,0.4)' : 'rgba(255,255,255,0.15)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(lcx + Math.cos(a) * tickR,       lcy + Math.sin(a) * tickR);
      ctx.lineTo(lcx + Math.cos(a) * (tickR+len), lcy + Math.sin(a) * (tickR+len));
      ctx.stroke();
    }

    // ── Ring 2: glatt ──
    const r2 = 130 * ss;
    ctx.strokeStyle = 'rgba(255,255,255,0.12)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(lcx, lcy, r2, 0, Math.PI * 2);
    ctx.stroke();

    // ── Ring 3: 3 rotierende Bögen mit End-Punkt ──
    const r3 = 180 * ss;
    ctx.lineWidth = 1.5;
    for (let i = 0; i < 3; i++) {
      const s = (i / 3) * Math.PI * 2 - t * 0.3;
      ctx.strokeStyle = `rgba(255,255,255,${0.35 - i * 0.05})`;
      ctx.beginPath();
      ctx.arc(lcx, lcy, r3, s, s + Math.PI / 4);
      ctx.stroke();
      const ex = lcx + Math.cos(s + Math.PI / 4) * r3;
      const ey = lcy + Math.sin(s + Math.PI / 4) * r3;
      ctx.fillStyle = 'rgba(255,255,255,0.5)';
      ctx.beginPath();
      ctx.arc(ex, ey, 2.5, 0, Math.PI * 2);
      ctx.fill();
    }

    // ── Hexagon (langsam rotierend) ──
    const hexR = 155 * ss;
    const hexRot = t * 0.1;
    ctx.strokeStyle = 'rgba(255,255,255,0.18)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i <= 6; i++) {
      const a  = i * Math.PI / 3 + hexRot;
      const px = lcx + Math.cos(a) * hexR;
      const py = lcy + Math.sin(a) * hexR;
      i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
    }
    ctx.stroke();
    for (let i = 0; i < 6; i++) {
      const a = i * Math.PI / 3 + hexRot;
      ctx.fillStyle = 'rgba(255,255,255,0.4)';
      ctx.beginPath();
      ctx.arc(lcx + Math.cos(a) * hexR, lcy + Math.sin(a) * hexR, 2, 0, Math.PI * 2);
      ctx.fill();
    }

    // ── Ring 4: gestrichelt ──
    const r4 = 240 * ss;
    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 6]);
    ctx.beginPath();
    ctx.arc(lcx, lcy, r4, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);

    // ── Ring 5: äußere Ticks, gegenläufig ──
    const r5 = 290 * ss;
    const t5Rot = -t * 0.15;
    for (let i = 0; i < 48; i++) {
      const a = (i / 48) * Math.PI * 2 + t5Rot;
      ctx.strokeStyle = 'rgba(255,255,255,0.1)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(lcx + Math.cos(a) * r5,     lcy + Math.sin(a) * r5);
      ctx.lineTo(lcx + Math.cos(a) * (r5+8), lcy + Math.sin(a) * (r5+8));
      ctx.stroke();
    }

    // ── Orbitierende Partikel ──
    particles.forEach(p => {
      p.angle += p.speed * 0.01;
      const px = lcx + Math.cos(p.angle) * p.radius * ss;
      const py = lcy + Math.sin(p.angle) * p.radius * ss;
      ctx.fillStyle = `rgba(255,255,255,${p.opacity})`;
      ctx.beginPath();
      ctx.arc(px, py, p.size, 0, Math.PI * 2);
      ctx.fill();
    });

    // ── Radar-Sweep (konisch wenn unterstützt) ──
    const sweepAngle = t * 0.6;
    if (ctx.createConicGradient) {
      const swg = ctx.createConicGradient(sweepAngle, lcx, lcy);
      swg.addColorStop(0,    'rgba(255,255,255,0.18)');
      swg.addColorStop(0.08, 'rgba(255,255,255,0)');
      swg.addColorStop(1,    'rgba(255,255,255,0)');
      ctx.fillStyle = swg;
      ctx.beginPath();
      ctx.arc(lcx, lcy, 290 * ss, 0, Math.PI * 2);
      ctx.fill();
    }

    // ── Kreuzvisier ──
    const cross = 14;
    ctx.strokeStyle = 'rgba(255,255,255,0.25)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(lcx - cross - 4, lcy); ctx.lineTo(lcx - 6, lcy);
    ctx.moveTo(lcx + 6, lcy);         ctx.lineTo(lcx + cross + 4, lcy);
    ctx.moveTo(lcx, lcy - cross - 4); ctx.lineTo(lcx, lcy - 6);
    ctx.moveTo(lcx, lcy + 6);         ctx.lineTo(lcx, lcy + cross + 4);
    ctx.stroke();

    requestAnimationFrame(draw);
  }

  draw();
})();
