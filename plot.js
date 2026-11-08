/* Zeichenfunktionen für live.html (Hub, live) und ansicht.html (Archiv).
   rows = [[ms, wert1, wert2, …], …], gezeichnet wird das Zeitfenster t0…t1 (ms). */
'use strict';
const fmt = v => Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 1 ? v.toFixed(2) : v.toPrecision(3);

function leinwand(cv) {
  const w = cv.width = Math.max(1, cv.clientWidth * devicePixelRatio), h = cv.height = Math.max(1, cv.clientHeight * devicePixelRatio);
  const c = cv.getContext('2d'); c.clearRect(0, 0, w, h); return [c, w, h];
}

// Linie einer Spalte; bei mehr Punkten als Pixeln je Pixelspalte Minimum und Maximum. Gibt [min, max] zurück.
function linie(cv, rows, i, t0, t1) {
  const [c, w, h] = leinwand(cv), pts = rows.filter(r => r[0] >= t0 && Number.isFinite(r[i]));
  if (pts.length < 2) return null;
  let mn = Infinity, mx = -Infinity;
  for (const r of pts) { if (r[i] < mn) mn = r[i]; if (r[i] > mx) mx = r[i]; }
  const sp = (mx - mn) || 1, dt = (t1 - t0) || 1, X = t => (t - t0) / dt * w, Y = v => h - 2 - (v - mn) / sp * (h - 4);
  c.strokeStyle = '#4da3ff'; c.lineWidth = 1.25 * devicePixelRatio; c.beginPath();
  if (pts.length <= 2 * w) pts.forEach((r, k) => k ? c.lineTo(X(r[0]), Y(r[i])) : c.moveTo(X(r[0]), Y(r[i])));
  else {
    let px = null, lo = 0, hi = 0;
    for (const r of pts) {
      const x = Math.floor(X(r[0]));
      if (x !== px) { if (px !== null) { c.lineTo(px, Y(lo)); c.lineTo(px, Y(hi)); } else c.moveTo(x, Y(r[i])); px = x; lo = hi = r[i]; }
      else { if (r[i] < lo) lo = r[i]; if (r[i] > hi) hi = r[i]; }
    }
    c.lineTo(px, Y(lo)); c.lineTo(px, Y(hi));
  }
  c.stroke(); return [mn, mx];
}

// Spektrogramm: Zeit nach rechts, Frequenz nach oben, Farbe = Pegel relativ zum Fenster.
function spektrogramm(cv, rows, t0, t1) {
  const [c, w, h] = leinwand(cv); rows = rows.filter(r => r[0] >= t0); if (!rows.length) return;
  const n = rows[0].length - 1; let mn = Infinity, mx = -Infinity;
  for (const r of rows) for (let j = 1; j <= n; j++) { const v = r[j]; if (Number.isFinite(v)) { if (v < mn) mn = v; if (v > mx) mx = v; } }
  const img = c.createImageData(rows.length, n), sp = (mx - mn) || 1;
  rows.forEach((r, x) => {
    for (let j = 1; j <= n; j++) {
      const v = Number.isFinite(r[j]) ? (r[j] - mn) / sp : 0, o = ((n - j) * rows.length + x) * 4;
      img.data[o] = 255 * Math.min(1, v * 1.6); img.data[o + 1] = 255 * Math.max(0, v * 1.6 - .6); img.data[o + 2] = 90 * (1 - v); img.data[o + 3] = 255;
    }
  });
  const tmp = document.createElement('canvas'); tmp.width = rows.length; tmp.height = n; tmp.getContext('2d').putImageData(img, 0, 0);
  const dt = (t1 - t0) || 1, x0 = (rows[0][0] - t0) / dt * w, x1 = (rows[rows.length - 1][0] - t0) / dt * w;
  c.imageSmoothingEnabled = false; c.drawImage(tmp, x0, 0, Math.max(1, x1 - x0), h);
}
