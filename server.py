#!/usr/bin/env python3
"""Mac-Server für das Lagebild-Messgerät.

    ./zertifikat.sh      # einmalig, Anleitung im Skript
    python3 server.py

- iPhone (gleiches WLAN): https://<Mac-Name>.local:8443/       → Messgerät
- Mac:                    https://localhost:8443/anzeige       → Anzeige (live + alle Aufzeichnungen)

Das Messgerät schickt jede Sekunde neue Zeilen (nur für die Live-Anzeige, im
Speicher) und beim Stopp die ganze Aufzeichnung. Die landet in daten/<id>.json und
wird sofort mit auswertung.py ausgewertet (daten/<id>.txt).
"""
import http.server
import importlib
import json
import re
import ssl
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import auswertung

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "daten"
CERT, KEY = ROOT / "cert" / "server.pem", ROOT / "cert" / "server-key.pem"
PORT = 8443
MAX_BODY = 50 * 1024 * 1024
DATEIEN = {"/": "index.html", "/index.html": "index.html", "/anzeige": "anzeige.html", "/sw.js": "sw.js",
           "/manifest.webmanifest": "manifest.webmanifest", "/plot.js": "plot.js",
           "/icon-180.png": "icon-180.png", "/icon-192.png": "icon-192.png", "/icon-512.png": "icon-512.png"}
TYPEN = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
         ".webmanifest": "application/manifest+json", ".png": "image/png"}

LOCK = threading.Lock()
LIVE, NR = [], 0  # [(nr, nachricht)] für die Live-Anzeige, nur im Speicher
LIVE_MAX = 900


def live_add(msg):
    global NR
    with LOCK:
        NR += 1
        LIVE.append((NR, msg))
        del LIVE[:-LIVE_MAX]


def sauber(s):
    return re.sub(r"[^A-Za-z0-9_-]", "", str(s))[:80]


def liste():
    """Alle Aufzeichnungen, neueste zuerst: Kopfdaten plus Kurzergebnis der Auswertung."""
    out = []
    for p in sorted(DATA.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        txt = p.with_suffix(".txt")
        out.append({"id": p.stem, "mode": d.get("mode"), "start": d.get("start"), "end": d.get("end"),
                    "reference": d.get("reference", ""), "kurz": txt.read_text(encoding="utf-8").split("\n")[-2] if txt.exists() else ""})
    return out


def auswerten(rid):
    try:
        importlib.reload(auswertung)  # Änderungen an auswertung.py gelten ohne Neustart
        text, kurz = auswertung.auswerten(DATA / f"{rid}.json")
        (DATA / f"{rid}.txt").write_text(text + "\n" + kurz + "\n", encoding="utf-8")
        live_add({"auswertung": rid, "kurz": kurz})
        print(f"AUSWERTUNG {rid}: {kurz}", flush=True)
    except Exception as e:  # Auswertung darf den Empfang nie stören
        print(f"AUSWERTUNG-FEHLER {rid}: {e!r}", flush=True)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        if url.path in DATEIEN:
            f = ROOT / DATEIEN[url.path]
            return self._send(200, f.read_bytes(), TYPEN[f.suffix])
        if url.path == "/api/ping":
            return self._json({"ok": True})
        if url.path == "/api/live":
            seit = int(parse_qs(url.query).get("seit", ["0"])[0] or 0)
            with LOCK:
                neu = [m for m in LIVE if m[0] > seit][:300]
            return self._json({"msgs": neu})
        if url.path == "/api/aufnahmen":
            return self._json(liste())
        m = re.fullmatch(r"/api/aufnahmen/([A-Za-z0-9_-]+)(\.txt)?", url.path)
        if m and (DATA / f"{m[1]}.json").exists():
            if m[2]:
                txt = DATA / f"{m[1]}.txt"
                return self._send(200, txt.read_bytes() if txt.exists() else b"", "text/plain; charset=utf-8")
            return self._send(200, (DATA / f"{m[1]}.json").read_bytes(), "application/json")
        self._send(404, b"nicht gefunden", "text/plain; charset=utf-8")

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        if path not in ("/api/live", "/api/aufnahme") or not 0 < length <= MAX_BODY:
            return self._send(400, b"falsche Anfrage", "text/plain; charset=utf-8")
        try:
            msg = json.loads(self.rfile.read(length))
        except ValueError:
            return self._send(400, b"kein JSON", "text/plain; charset=utf-8")
        if path == "/api/live":
            msg["session"] = sauber(msg.get("session"))
            live_add(msg)
            if "meta" in msg and not msg.get("final"):
                print(f"START {msg['session']}", flush=True)
            return self._json({"ok": True})
        rid = sauber(msg.get("id")) or "ohne-id"
        DATA.mkdir(exist_ok=True)
        (DATA / f"{rid}.json").write_text(json.dumps(msg, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        self._json({"ok": True})
        threading.Thread(target=auswerten, args=(rid,)).start()

    def log_message(self, *args):  # Zugriffsprotokoll aus
        pass

    def _json(self, obj):
        self._send(200, json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode(), "application/json")

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main():
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    scheme = "http"
    if CERT.exists() and KEY.exists():
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(CERT, KEY)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        scheme = "https"
    else:
        print("Ohne Zertifikat (./zertifikat.sh) geht nur der Mac selbst, nicht das iPhone.", flush=True)
    print(f"Server läuft · Anzeige: {scheme}://localhost:{PORT}/anzeige", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
