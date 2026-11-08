# Lagebild Messgerät – MM-Version

Hervorgegangen aus Ralphs „Lagebild Lite“ ([Original](https://bssragu.github.io/lagebild/), Repo `BSSRAGU/lagebild`). Das iPhone ist ein reines Messinstrument, der Mac zeigt die Daten an und wertet sie aus. Es gibt keine Animationen, keine Auswertung auf dem Gerät, keinen Token und keine Cloud. Befunde zum Original stehen in `research/eingang/ralph-lagebild-lite.md`.

```
iPhone (Messgerät)  ──WLAN, HTTPS──>  Mac: server.py  ──>  Anzeige im Browser, daten/, auswertung.py
```

## Aufbau

| Teil | Dateien | Aufgabe |
|---|---|---|
| Messgerät (PWA) | `index.html`, `sw.js`, `manifest.webmanifest`, `icon-*.png` | Kommt vom Mac. Hat die Modi Kontakt, Sonar, Puls und Flug. Schickt jede Sekunde neue Zeilen für die Live-Anzeige und beim Stopp die ganze Aufzeichnung. Jede Aufzeichnung bleibt in der App gespeichert (IndexedDB), bis der Mac sie bestätigt; Ausstehendes wird nachgeschickt. Hält während der Aufnahme den Bildschirm wach. |
| Anzeige | `anzeige.html`, `plot.js` | Zeigt oben die laufende Messung (letzte 30 s) und unten jede gespeicherte Aufzeichnung komplett mit Auswertung. |
| Server | `server.py` | Liefert App und Anzeige aus, speichert `daten/<id>.json`, wertet sofort aus (`daten/<id>.txt`). |
| Auswertung | `auswertung.py` | Atemrate (Sonar), Puls (Grünkanal), Atmung und Puls aus dem Bewegungssensor, per DFT auf den echten Zeitstempeln. Änderungen gelten ohne Neustart. Von Hand: `python3 auswertung.py <datei>`. |
| Zertifikat | `zertifikat.sh` | Eigene CA, beschränkt auf lokale Adressen, dazu das HTTPS-Zertifikat für den Mac. |

## Einrichtung (einmalig)

1. **Zertifikat erzeugen:** `./zertifikat.sh` ausführen.
2. **Zertifikat aufs iPhone:** `cert/lagebild-ca.cer` per AirDrop schicken und unter Einstellungen → „Profil geladen“ installieren. Danach unter Einstellungen → Allgemein → Info → Zertifikatsvertrauenseinstellungen „Lagebild Test-CA“ einschalten. Safari gibt Mikrofon, Kamera und Bewegungssensor nur über HTTPS frei.
3. **Server starten:** `python3 server.py`. Fragt die Mac-Firewall nach eingehenden Verbindungen, mit „Erlauben“ bestätigen.
4. **iPhone:** In Safari `https://<Mac-Name>.local:8443/` öffnen und über Teilen → „Zum Home-Bildschirm“ als App ablegen.
5. **Anzeige auf dem Mac:** `https://localhost:8443/anzeige` öffnen.

iPhone und Mac müssen im selben WLAN sein.

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

- **Aufzeichnung** (`daten/<id>.json`, auch der Export aus der App): `{id, app, format, mode, start, end, ua, audio_hz, reference, columns, streams}`.
- **Schnittstelle:**
  - `POST /api/live` mit `{session, meta | chunk | final}` speist nur die Live-Anzeige und bleibt im Speicher.
  - `POST /api/aufnahme` überträgt die ganze Aufzeichnung.
  - `GET /api/aufnahmen` liefert die Liste der Aufzeichnungen, `GET /api/aufnahmen/<id>[.txt]` eine einzelne Aufzeichnung bzw. ihre Auswertung.
