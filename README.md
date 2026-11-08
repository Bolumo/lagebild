# Lagebild Messgerät – MM-Version

Hervorgegangen aus Ralphs „Lagebild Lite“ ([Original](https://bssragu.github.io/lagebild/), Repo `BSSRAGU/lagebild`). Diese Version ist ein reines Messinstrument. Das iPhone nimmt Rohdaten auf und sendet sie. Auswertung und Anzeige laufen auf dem Mac. Es gibt keine Animationen und keine Auswertung auf dem Gerät, damit sich Fähigkeiten sauber auf dem Mac entwickeln lassen, ohne die App anzufassen.

Befunde zum Original: `research/eingang/ralph-lagebild-lite.md`.

## Aufbau

| Teil | Dateien | Aufgabe |
|---|---|---|
| Messgerät (PWA) | `index.html`, `sw.js`, `manifest.webmanifest`, `icon-*.png` | Läuft unter https://bolumo.github.io/lagebild/. Modi: Kontakt, Sonar, Puls, Flug. Sendet jede Sekunde an den Hub und archiviert jede Aufzeichnung beim Stopp auf GitHub. Hält den Bildschirm während der Aufnahme wach. |
| Ansicht | `ansicht.html`, `plot.js` | Zeigt archivierte Aufzeichnungen vollständig unter https://bolumo.github.io/lagebild/ansicht.html, auf jedem Gerät, ohne Hub und ohne Tunnel. Neue Aufzeichnungen erscheinen wenige Sekunden nach dem Stopp. Braucht einen Token mit Lesezugriff auf `lagebild-daten`. |
| Mac-Hub | `server.py`, `live.html` | Empfängt die Daten, speichert sie (`daten/<session>.jsonl`), zeigt sie live und wertet nach dem Stopp aus. |
| Auswertung | `auswertung.py` | Schätzt die Atemrate (Sonar), den Puls (Grünkanal) und Atmung/Puls aus dem Bewegungssensor per DFT auf den echten Zeitstempeln. Gilt nach jeder Änderung sofort, ohne Neustart. Von Hand: `python3 auswertung.py <datei>`. |
| Archiv abholen | `github_abholen.py` | Holt Aufzeichnungen aus `Bolumo/lagebild-daten`, die ohne Hub entstanden sind, und wertet sie aus. |

## Einrichtung

1. **iPhone:** Die Seite in Safari öffnen und über Teilen → „Zum Home-Bildschirm“ als App ablegen. Dort unter „Einstellungen“ den GitHub-Token eintragen: fine-grained, nur Repo `lagebild-daten`, Berechtigung „Contents: Read and write“. Der Token bleibt auf dem Gerät. Die Home-Bildschirm-App hat einen eigenen Speicher, darum dort einmal neu eintragen.
2. **Mac:** `python3 server.py <https-adresse>` starten. Der Hub lauscht nur auf `127.0.0.1:8443` und erzeugt bei jedem Start einen neuen Zugangsschlüssel. Er trägt die Adresse und den Schlüssel in `live.json` im Daten-Repo ein. Die App liest diese Datei mit ihrem Token und verbindet sich selbst.
3. **Live-Ansicht:** Die Adresse mit `?k=…` aus der Ausgabe des Hubs im Browser öffnen. Ohne Schlüssel liefert der Hub keine Daten.

**Offen:** Das iPhone braucht eine HTTPS-Adresse, unter der es den Hub erreicht. Die Seite läuft über HTTPS, deshalb blockiert Safari Anfragen an `http://` im LAN. Welcher Weg dafür genommen wird, ist noch nicht entschieden.

## Datenformat (format 2)

Eine Aufzeichnung umfasst einen Modus von Start bis Stopp. Jede Zeile beginnt mit `ms` seit dem Start. Die Spaltennamen stehen in `columns`.

| Modus | Strom | Spalten | Rate (ca.) |
|---|---|---|---|
| kontakt | `accel` | ms, ax, ay, az (m/s²), mit_schwerkraft, rot_alpha, rot_beta, rot_gamma (°/s) | 60–100 Hz |
| kontakt | `pegel` | ms, Pegel 20–80 Hz, Pegel 100–4.000 Hz (dB) | 10 Hz |
| sonar | `iq` | ms, I, Q (19-kHz-Echo, je 4.096 Samples demoduliert) | 11,7 Hz |
| sonar | `pegel` | ms, Trägerpegel (dB), Seitenband-Verhältnis | 6–7 Hz |
| puls | `rgb` | ms, Bildzeit (s), mittleres R, G, B der Bildmitte | ein Wert je Kamerabild |
| flug | `ton` | ms, stärkster Ton 60–300 Hz, Prominenz (dB), tonal (0/1) | 3,3 Hz |
| flug | `spek` | ms, Spektrum ab 40 Hz in dB, Bin = `audio_hz`/32768 | 3,3 Hz |

- **Archiv und Export:** `{app, format, mode, start, end, ua, audio_hz, reference, columns, streams}`.
- **Live:** `POST /api/ingest` als `text/plain`, damit der Browser keine CORS-Vorabanfrage schickt. Die Nachrichten haben die Form `{k, session, meta | chunk | final}`.
- **Live-Datei** (`daten/<session>.jsonl`): eine Nachricht pro Zeile, jeweils mit der Empfangszeit des Macs.
- **Live-Ansicht:** fragt `GET /api/live?k=…&seit=<nr>` zweimal pro Sekunde ab.
