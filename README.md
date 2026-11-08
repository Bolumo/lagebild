# Lagebild Lite – MM-Version

Kopie von Ralphs Prototyp ([Original](https://bssragu.github.io/lagebild/), Repo `BSSRAGU/lagebild`), Branch `mm-version`. Ziel: die Signale verstehen und gegen Referenzen messen. Befunde zum Original: `research/eingang/ralph-lagebild-lite.md`.

## Was anders ist als im Original

- **Rohdaten-Aufzeichnung je Modus** (Tab „Protokoll“ → „Aufzeichnungen“), Export als JSON über das Teilen-Menü (AirDrop an den Mac).
- **Referenzwert** pro Messung (z. B. „Polar H10 62/min“), wird beim Beenden mitgespeichert.
- **Live-Versand an den Mac**, wenn die Seite vom Mac-Server kommt (`server.py`): Daten landen alle 3 s in `daten/<session>.jsonl`.
- Prozentwert im Protokoll heißt jetzt ehrlich „Signalstärke“, keine Trefferquote.
- Ohne WebGL (z. B. Blockierungsmodus) läuft die App ohne 3D-Grafik weiter, statt komplett auszufallen.

## Starten

**Online (iPhone, ohne Mac):** https://bolumo.github.io/lagebild/ (GitHub Pages, Branch `mm-version`). Aufzeichnen und Exportieren funktionieren dort, der Live-Versand an den Mac nicht.

**Mit Mac-Server (Live-Versand):**

```sh
python3 server.py        # Mac selbst: http://localhost:8443
./zertifikat.sh          # einmalig fürs iPhone (HTTPS); Anleitung steht im Skript
```

Das iPhone muss im selben WLAN sein. Safari gibt Mikrofon, Kamera und Bewegungssensor nur über HTTPS frei – deshalb das eigene Zertifikat. `cert/` und `daten/` stehen in `.gitignore`.

## Datenformat

Eine Aufzeichnung = ein Modus von Start bis Stopp. Jede Zeile beginnt mit `ms` seit Start; Spaltennamen stehen in `columns`.

| Modus | Strom | Spalten | Rate (ca.) |
|---|---|---|---|
| kontakt | `accel` | ms, ax, ay, az (m/s²), mit_schwerkraft | 60–100 Hz (nur iPhone) |
| kontakt | `pegel` | ms, Vibration (Std.), Pegel 20–80 Hz, Pegel 100–4.000 Hz (dB) | 10 Hz |
| sonar | `iq` | ms, I, Q (19-kHz-Echo, demoduliert) | 11,7 Hz |
| sonar | `pegel` | ms, Trägerpegel (dB), Seitenband-Verhältnis | 6–7 Hz |
| puls | `rgb` | ms, Videozeit (s), mittleres R, G, B der Bildmitte | Bildrate des Displays (Duplikate über `video_s` erkennbar) |
| flug | `ton` | ms, stärkster Ton (Hz), Prominenz (dB), tonal (0/1) | 3,3 Hz |
| flug | `spek` | ms, Spektrum 40–400 Hz in dB, je 1,465 Hz | 3,3 Hz |

Export-Datei: `{app, format, mode, start, end, ua, reference, columns, streams, events}`. Live-Datei (`.jsonl`): eine Zeile `meta`, dann `chunk`-Zeilen, am Ende `final` mit Referenz und Ereignissen; jede Zeile mit Empfangszeit des Macs.
