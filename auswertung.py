#!/usr/bin/env python3
"""Wertet eine Lagebild-Aufzeichnung aus.

    python3 auswertung.py daten/<session>.jsonl     # Live-Datei vom Mac-Server
    python3 auswertung.py <export>.json             # Export aus der App

server.py ruft das automatisch auf, sobald eine Aufzeichnung beendet ist,
und legt das Ergebnis als daten/<session>.txt ab.

Raten werden per DFT direkt auf den echten Zeitstempeln geschätzt (die
Abtastung im Browser schwankt). „Deutlichkeit“ = Leistung der Spitze geteilt
durch den Median im Band; unter ~5 ist die Spitze kaum vom Rauschen zu trennen.
"""
import json
import math
import sys
from pathlib import Path

ATMUNG = (0.1, 0.7, 0.002)  # Hz von, bis, Schritt  (6–42 /min)
PULS = (0.7, 3.0, 0.005)    # Hz                     (42–180 /min)
EINSCHWINGEN_S = 2.0        # Anfang verwerfen (Start von Ton, Kamera, Sensoren)


def laden(pfad):
    p = Path(pfad)
    if p.suffix != ".jsonl":
        d = json.loads(p.read_text(encoding="utf-8"))
        return d, d.get("streams", {}), d.get("events", [])
    meta, streams, events = {}, {}, []
    for line in p.read_text(encoding="utf-8").splitlines():
        msg = json.loads(line)
        if "meta" in msg and (msg.get("final") or not meta):
            meta = msg["meta"]  # die finale Meta enthält Ende und Referenz
        for name, rows in (msg.get("chunk") or {}).items():
            streams.setdefault(name, []).extend(rows)
        if msg.get("final"):
            events = msg.get("events") or []
    for rows in streams.values():
        rows.sort(key=lambda r: r[0])
    return meta, streams, events


def entrenden(t, x):
    n = len(t)
    mt, mx = sum(t) / n, sum(x) / n
    stt = sum((ti - mt) ** 2 for ti in t) or 1.0
    k = sum((ti - mt) * (xi - mx) for ti, xi in zip(t, x)) / stt
    return [xi - mx - k * (ti - mt) for ti, xi in zip(t, x)]


def spitzen(t, x, band):
    """Die drei stärksten Spitzen im Band: [(Hz, Deutlichkeit), …]."""
    fmin, fmax, df = band
    x = entrenden(t, x)
    fs, ps = [], []
    f = fmin
    while f <= fmax + 1e-9:
        w = 2 * math.pi * f
        re = sum(xi * math.cos(w * ti) for ti, xi in zip(t, x))
        im = sum(xi * math.sin(w * ti) for ti, xi in zip(t, x))
        fs.append(f)
        ps.append(re * re + im * im)
        f += df
    med = sorted(ps)[len(ps) // 2] or 1e-30
    lokal = [i for i in range(1, len(ps) - 1) if ps[i] >= ps[i - 1] and ps[i] >= ps[i + 1]]
    lokal.sort(key=lambda i: -ps[i])
    abstand = 3 / max(t[-1] - t[0], 1e-9)  # Nebenkeulen der Hauptspitze überspringen
    gewaehlt = []
    for i in lokal:
        if all(abs(fs[i] - fs[j]) > abstand for j in gewaehlt):
            gewaehlt.append(i)
        if len(gewaehlt) == 3:
            break
    return [(fs[i], ps[i] / med) for i in gewaehlt]


def spitzen_text(sp, einheit="/min"):
    if not sp:
        return "keine Spitze"
    return " · ".join(f"{f * 60:.1f}{einheit} (Deutlichkeit {d:.0f})" for f, d in sp)


def ab_einschwingen(rows, i_t=0, skala=1000.0):
    return [r for r in rows if r[i_t] / skala >= EINSCHWINGEN_S]


def strom_info(name, rows):
    if len(rows) < 2:
        return f"{name}: {len(rows)} Zeilen"
    ms = [r[0] for r in rows]
    dauer = (ms[-1] - ms[0]) / 1000
    luecke = max(b - a for a, b in zip(ms, ms[1:]))
    return f"{name}: {len(rows)} Zeilen, {dauer:.1f} s, {len(rows) / max(dauer, 1e-9):.1f} Hz, größte Lücke {luecke} ms"


def sonar(streams):
    rows = ab_einschwingen(streams.get("iq", []))
    if len(rows) < 30:
        return ["Sonar: zu wenig I/Q-Daten"], None
    t = [r[0] / 1000 for r in rows]
    i = entrenden(t, [r[1] for r in rows])
    q = entrenden(t, [r[2] for r in rows])
    sii = sum(v * v for v in i)
    sqq = sum(v * v for v in q)
    siq = sum(a * b for a, b in zip(i, q))
    th = 0.5 * math.atan2(2 * siq, sii - sqq)  # Hauptachse der Echo-Bewegung
    x = [a * math.cos(th) + b * math.sin(th) for a, b in zip(i, q)]
    statisch = math.hypot(sum(r[1] for r in rows) / len(rows), sum(r[2] for r in rows) / len(rows))
    bewegt = math.sqrt((sii + sqq) / len(rows))
    sp = spitzen(t, x, ATMUNG)
    return [
        f"Sonar Atmung: {spitzen_text(sp)}",
        f"  bewegter Echo-Anteil {bewegt / (statisch or 1e-30) * 100:.2f} % des statischen Signals",
    ], (f"Atmung {sp[0][0] * 60:.1f}/min" if sp else None)


def puls(streams):
    rows, letzte = [], None
    for r in streams.get("rgb", []):  # nur neue Kamerabilder (Duplikate über video_s)
        if r[1] != letzte:
            rows.append(r)
            letzte = r[1]
    rows = ab_einschwingen(rows, i_t=1, skala=1.0)
    if len(rows) < 60:
        return ["Puls: zu wenig Kamerabilder"], None
    t = [r[1] for r in rows]
    dauer = t[-1] - t[0]
    mg = sum(r[3] for r in rows) / len(rows)
    sp = spitzen(t, [r[3] / (mg or 1) for r in rows], PULS)
    return [
        f"Puls (Grünkanal): {spitzen_text(sp)}",
        f"  {len(rows)} echte Bilder in {dauer:.1f} s = {len(rows) / max(dauer, 1e-9):.1f} fps, "
        f"mittleres RGB {sum(r[2] for r in rows) / len(rows):.0f}/{mg:.0f}/{sum(r[4] for r in rows) / len(rows):.0f}",
    ], (f"Puls {sp[0][0] * 60:.1f}/min" if sp else None)


def kontakt(streams):
    rows = ab_einschwingen(streams.get("accel", []))
    if len(rows) < 100:
        return ["Kontakt: zu wenig Beschleunigungsdaten (nur iPhone liefert sie)"], None
    # auf 20 Hz mitteln, das reicht bis 3 Hz und spart Rechenzeit
    fach = {}
    for r in rows:
        fach.setdefault(r[0] // 50, []).append(r)
    blk = [[sum(c) / len(c) for c in zip(*v)] for _, v in sorted(fach.items())]
    t = [b[0] / 1000 for b in blk]
    zeilen, kurz = [], []
    for name, band in (("Atmung", ATMUNG), ("Puls", PULS)):
        best = max(((ax, spitzen(t, [b[k] for b in blk], band)) for ax, k in (("x", 1), ("y", 2), ("z", 3))),
                   key=lambda e: e[1][0][1] if e[1] else 0)
        zeilen.append(f"Kontakt {name} (beste Achse {best[0]}): {spitzen_text(best[1])}")
        if best[1]:
            kurz.append(f"{name} {best[1][0][0] * 60:.1f}/min")
    if rows[0][4]:
        zeilen.append("  Achtung: Gerät liefert nur Beschleunigung mit Schwerkraft")
    return zeilen, ", ".join(kurz) or None


def flug(streams):
    ton = streams.get("ton", [])
    if not ton:
        return ["Flug: keine Daten"], None
    tonal = [r for r in ton if r[3]]
    if not tonal:
        return [f"Flug: {len(ton)} Fenster, kein tonales Signal"], "kein Ton"
    f = sorted(r[1] for r in tonal)
    return [f"Flug: {len(tonal)}/{len(ton)} Fenster tonal, Spitze median {f[len(f) // 2]:.1f} Hz "
            f"(von {f[0]:.1f} bis {f[-1]:.1f} Hz)"], f"Ton median {f[len(f) // 2]:.1f} Hz"


def auswerten(pfad):
    meta, streams, events = laden(pfad)
    mode = meta.get("mode", "?")
    zeilen = [f"Aufzeichnung {Path(pfad).stem}",
              f"Modus {mode} · {meta.get('start', '?')} bis {meta.get('end', '?')}",
              f"Referenz: {meta.get('reference') or '(keine eingetragen)'}"]
    zeilen += ["  " + strom_info(k, v) for k, v in streams.items()]
    fn = {"sonar": sonar, "puls": puls, "kontakt": kontakt, "flug": flug}.get(mode)
    kurz = None
    if fn:
        erg, kurz = fn(streams)
        zeilen += erg
    for e in events:
        zeilen.append("  Ereignis: " + json.dumps(e, ensure_ascii=False)[:200])
    ref = meta.get("reference") or "keine Referenz"
    return "\n".join(zeilen), f"{mode}: {kurz or 'kein Ergebnis'} | Referenz: {ref}"


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        print(auswerten(arg)[0], end="\n\n")
