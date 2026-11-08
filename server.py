#!/usr/bin/env python3
"""Mac-Hub für das Lagebild-Messgerät.

    python3 server.py [ADRESSE]

- Nimmt die Rohdaten des Messgeräts entgegen (POST /api/ingest), speichert jede
  Aufzeichnung als daten/<session>.jsonl und wertet sie nach dem Stopp mit
  auswertung.py aus (daten/<session>.txt).
- Live-Ansicht im Browser: http://localhost:8443/?k=<schlüssel>
- Lauscht nur auf 127.0.0.1. Damit das iPhone den Hub erreicht, braucht es eine
  HTTPS-Adresse davor (siehe README). Wird sie als ADRESSE übergeben, trägt der
  Hub sie mit dem Schlüssel in live.json im privaten Daten-Repo ein; die App
  liest das mit ihrem Token und verbindet sich selbst.
"""
import base64
import http.server
import importlib
import json
import re
import secrets
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import auswertung

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "daten"
PORT = 8443
MAX_BODY = 20 * 1024 * 1024
REPO = "Bolumo/lagebild-daten"
KEY = secrets.token_urlsafe(16)
LIVE_MAX = 900  # Nachrichten im Speicher für die Live-Ansicht (~15 min bei 1/s)

LOCK = threading.Lock()
LIVE = []  # [(nr, nachricht)]
NR = 0


def live_add(msg):
    global NR
    with LOCK:
        NR += 1
        LIVE.append((NR, msg))
        del LIVE[:-LIVE_MAX]


class Handler(http.server.BaseHTTPRequestHandler):
    def _key_ok(self, key):
        return secrets.compare_digest(str(key or ""), KEY)

    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        if url.path in ("/", "/index.html"):
            return self._send(200, (ROOT / "live.html").read_bytes(), "text/html; charset=utf-8")
        if not self._key_ok(q.get("k", [""])[0]):
            return self._send(403, b'{"fehler":"schluessel"}', "application/json")
        if url.path == "/api/ping":
            print("VERBUNDEN Messgerät", flush=True)
            return self._send(200, b'{"ok":true}', "application/json")
        if url.path == "/api/live":
            seit = int(q.get("seit", ["0"])[0] or 0)
            with LOCK:
                neu = [m for m in LIVE if m[0] > seit][:300]
            return self._send(200, json.dumps({"msgs": neu}, separators=(",", ":")).encode(), "application/json")
        self._send(404, b"nicht gefunden", "text/plain; charset=utf-8")

    def do_POST(self):
        if urlparse(self.path).path != "/api/ingest":
            return self._send(404, b"nicht gefunden", "text/plain; charset=utf-8")
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 < length <= MAX_BODY:
            return self._send(413, b"leer oder zu gross", "text/plain; charset=utf-8")
        try:
            msg = json.loads(self.rfile.read(length))
        except ValueError:
            return self._send(400, b"kein JSON", "text/plain; charset=utf-8")
        if not self._key_ok(msg.pop("k", None)):
            return self._send(403, b'{"fehler":"schluessel"}', "application/json")
        session = re.sub(r"[^A-Za-z0-9_-]", "", str(msg.get("session", "")))[:80] or "ohne-id"
        msg["session"] = session
        msg["empfangen"] = datetime.now(timezone.utc).isoformat()
        DATA.mkdir(exist_ok=True)
        with LOCK, (DATA / f"{session}.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(msg, ensure_ascii=False, separators=(",", ":")) + "\n")
        live_add(msg)
        self._send(200, b'{"ok":true}', "application/json")
        if "meta" in msg and not msg.get("final"):
            print(f"START {session}", flush=True)
        if msg.get("final"):  # kurz warten: der letzte Datenblock kann knapp danach ankommen
            threading.Timer(1.5, auswerten, args=(session,)).start()

    def log_message(self, *args):  # Zugriffsprotokoll aus
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")  # Zugriff regelt der Schlüssel
        self.end_headers()
        self.wfile.write(body)


def auswerten(session):
    try:
        importlib.reload(auswertung)  # Änderungen an auswertung.py gelten ohne Neustart
        text, kurz = auswertung.auswerten(DATA / f"{session}.jsonl")
        (DATA / f"{session}.txt").write_text(text + "\n", encoding="utf-8")
        live_add({"session": session, "auswertung": text, "kurz": kurz})
        print(f"AUSWERTUNG {session}: {kurz}", flush=True)
    except Exception as e:  # Auswertung darf den Empfang nie stören
        print(f"AUSWERTUNG-FEHLER {session}: {e!r}", flush=True)


def live_json(url):
    """Trägt Adresse und Schlüssel in live.json im Daten-Repo ein (über die angemeldete gh-CLI)."""
    pfad = f"repos/{REPO}/contents/live.json"
    alt = subprocess.run(["gh", "api", pfad, "--jq", ".sha"], capture_output=True, text=True)
    inhalt = {"url": url.rstrip("/"), "key": KEY, "seit": datetime.now(timezone.utc).isoformat()}
    body = {"message": "Hub gestartet", "content": base64.b64encode(json.dumps(inhalt).encode()).decode()}
    if alt.returncode == 0:
        body["sha"] = alt.stdout.strip()
    r = subprocess.run(["gh", "api", "-X", "PUT", pfad, "--input", "-"], input=json.dumps(body),
                       capture_output=True, text=True)
    print("live.json aktualisiert" if r.returncode == 0 else f"LIVE-JSON-FEHLER {r.stderr.strip()[:200]}", flush=True)


def main():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Hub läuft · Live-Ansicht: http://localhost:{PORT}/?k={KEY}", flush=True)
    if len(sys.argv) > 1:
        print(f"Von außen:  {sys.argv[1].rstrip('/')}/?k={KEY}", flush=True)
        live_json(sys.argv[1])
    server.serve_forever()


if __name__ == "__main__":
    main()
