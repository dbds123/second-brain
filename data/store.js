// Datenspeicher — localStorage-Wrapper mit sauberer Datenstruktur
// Schlüssel-Präfix: sb_ (second-brain)

const Store = {
  // Standard-Daten für jedes Modul
  defaults: {
    academics: {
      module: [],
      todos: []
    },
    athletics: {
      wochenplan: {},
      logs: [],
      oneRM: { bench: 0, squat: 0, deadlift: 0 },
      block: { name: 'Hypertrophie Block A', woche: 3, gesamtWochen: 8 }
    },
    insights: {
      bereiche: [
        { id: 'academics',     label: 'Academics',      wert: 5, kommentar: '' },
        { id: 'career',        label: 'Career',          wert: 5, kommentar: '' },
        { id: 'health',        label: 'Health & Body',   wert: 5, kommentar: '' },
        { id: 'finance',       label: 'Finance',         wert: 5, kommentar: '' },
        { id: 'relationships', label: 'Relationships',   wert: 5, kommentar: '' },
        { id: 'growth',        label: 'Growth',          wert: 5, kommentar: '' },
        { id: 'fun',           label: 'Fun & Joy',       wert: 5, kommentar: '' },
        { id: 'mind',          label: 'Mind & Spirit',   wert: 5, kommentar: '' }
      ],
      verlauf: []
    }
  },

  // Daten lesen — gibt Default zurück wenn noch nichts gespeichert
  get(schluessel) {
    try {
      const roh = localStorage.getItem(`sb_${schluessel}`);
      if (!roh) return JSON.parse(JSON.stringify(this.defaults[schluessel] || {}));
      return JSON.parse(roh);
    } catch (e) {
      console.warn(`[Store] get(${schluessel}) fehlgeschlagen:`, e);
      return JSON.parse(JSON.stringify(this.defaults[schluessel] || {}));
    }
  },

  // Daten schreiben
  set(schluessel, wert) {
    try {
      localStorage.setItem(`sb_${schluessel}`, JSON.stringify(wert));
    } catch (e) {
      console.error(`[Store] set(${schluessel}) fehlgeschlagen:`, e);
    }
  },

  // Daten aktualisieren (Callback-Pattern für immutable updates)
  update(schluessel, callback) {
    const aktuell = this.get(schluessel);
    const aktualisiert = callback(aktuell);
    this.set(schluessel, aktualisiert);
    return aktualisiert;
  },

  // Einzelnen Schlüssel oder alles zurücksetzen (für Debugging)
  reset(schluessel) {
    if (schluessel) {
      localStorage.removeItem(`sb_${schluessel}`);
    } else {
      Object.keys(this.defaults).forEach(k => localStorage.removeItem(`sb_${k}`));
    }
    console.log('[Store] Reset:', schluessel || 'alles');
  }
};
