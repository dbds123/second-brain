// Second Brain — App Init

// Begrüßung basierend auf Uhrzeit
function begruessung() {
  const h = new Date().getHours();
  if (h < 5)  return 'Späte Nacht';
  if (h < 11) return 'Guten Morgen';
  if (h < 14) return 'Guten Mittag';
  if (h < 18) return 'Guten Nachmittag';
  if (h < 22) return 'Guten Abend';
  return 'Späte Nacht';
}

// Live-Status Pill updaten
function updateStatus() {
  const d = new Date();
  const tage = ['Sonntag','Montag','Dienstag','Mittwoch','Donnerstag','Freitag','Samstag'];
  const hh = String(d.getHours()).padStart(2,'0');
  const mm = String(d.getMinutes()).padStart(2,'0');
  const el = document.getElementById('live-status');
  if (el) el.textContent = `System aktiv · ${tage[d.getDay()]} · ${hh}:${mm}`;
}

// Hero-Titel mit Tages-Kontext befüllen
function heroInit() {
  document.querySelector('.hero-greeting').textContent = begruessung();
  updateStatus();
  setInterval(updateStatus, 30_000);

  // Hero-Sub-Text aus Daten ableiten
  const acad = Store.get('academics');
  const n = acad.todos?.filter(t => !t.erledigt).length ?? 0;
  const sub = document.getElementById('hero-sub');
  if (sub) sub.textContent = `${n} offene Aufgaben. 2 Klausuren in diesem Semester. Woche 6 / 8 im Trainingsblock.`;
}

// Nav: active-Klasse + smooth scroll
function navInit() {
  const links    = document.querySelectorAll('.nav-link');
  const sections = ['hero','mails','academics','athletics','insights'];

  links.forEach(link => {
    link.addEventListener('click', e => {
      e.preventDefault();
      const target = document.getElementById(link.dataset.target);
      if (target) target.scrollIntoView({ behavior:'smooth' });

      links.forEach(l => l.classList.remove('active'));
      link.classList.add('active');
    });
  });

  // Nav-Item beim Scrollen aktualisieren
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const id = entry.target.id;
        links.forEach(l => l.classList.toggle('active', l.dataset.target === id));
      }
    });
  }, { threshold: 0.3 });

  sections.forEach(id => {
    const el = document.getElementById(id);
    if (el) observer.observe(el);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  Auth.handleCallback(); // OAuth redirect zurück — Token aus URL-Hash lesen
  heroInit();
  navInit();
  Mail.init();
  Academics.init();
  Athletics.init();
  Insights.init();
});
