#!/usr/bin/env python3
"""Messserver für Lagebild (MM-Version).

Liefert index.html aus und speichert die Rohdaten, die die Seite live schickt,
als JSON-Lines unter daten/<session>.jsonl.

    python3 server.py

Ohne Zertifikat läuft er per HTTP – das reicht für den Mac selbst
(http://localhost:8443, localhost gilt im Browser als sicher).
Fürs iPhone braucht es HTTPS: erst ./zertifikat.sh ausführen.
"""
import http.server
import importlib
import json
import re
import ssl
import threading
from datetime import datetime, timezone
from pathlib import Path

import auswertung

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "daten"
CERT = ROOT / "cert" / "server.pem"
KEY = ROOT / "cert" / "server-key.pem"
PORT = 8443
MAX_BODY = 20 * 1024 * 1024
LOCK = threading.Lock()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._send(200, (ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/ping":
            print(f"VERBUNDEN {self.client_address[0]}", flush=True)
            self._send(200, b'{"ok":true}', "application/json")
        else:  # nichts anderes ausliefern, schon gar nicht cert/ oder daten/
            self._send(404, b"nicht gefunden", "text/plain; charset=utf-8")

    def do_POST(self):
        if self.path.split("?")[0] != "/api/ingest":
            return self._send(404, b"nicht gefunden", "text/plain; charset=utf-8")
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 < length <= MAX_BODY:
            return self._send(413, b"leer oder zu gross", "text/plain; charset=utf-8")
        try:
            msg = json.loads(self.rfile.read(length))
        except ValueError:
            return self._send(400, b"kein JSON", "text/plain; charset=utf-8")
        session = re.sub(r"[^A-Za-z0-9_-]", "", str(msg.get("session", "")))[:80] or "ohne-id"
        msg["empfangen"] = datetime.now(timezone.utc).isoformat()
        DATA.mkdir(exist_ok=True)
        with LOCK, (DATA / f"{session}.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(msg, ensure_ascii=False, separators=(",", ":")) + "\n")
        self._send(200, b'{"ok":true}', "application/json")
        if "meta" in msg and not msg.get("final"):
            print(f"START {session}", flush=True)
        if msg.get("final"):  # kurz warten: der letzte Datenblock kann knapp nach "final" ankommen
            threading.Timer(1.5, auswerten, args=(session,)).start()

    def log_message(self, *args):  # Zugriffsprotokoll aus: die Ausgabe zeigt nur Auswertungen
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def auswerten(session):
    """Schreibt daten/<session>.txt und meldet eine Zeile auf der Konsole."""
    try:
        importlib.reload(auswertung)  # Änderungen an auswertung.py gelten ohne Neustart
        text, kurz = auswertung.auswerten(DATA / f"{session}.jsonl")
        (DATA / f"{session}.txt").write_text(text + "\n", encoding="utf-8")
        print(f"AUSWERTUNG {session}: {kurz}", flush=True)
    except Exception as e:  # Auswertung darf den Empfang nie stören
        print(f"AUSWERTUNG-FEHLER {session}: {e!r}", flush=True)


def main():
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    scheme = "http"
    if CERT.exists() and KEY.exists():
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(CERT, KEY)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        scheme = "https"
    print(f"Lagebild-Server: {scheme}://localhost:{PORT}/  ·  Daten nach {DATA}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
