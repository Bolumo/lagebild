#!/usr/bin/env python3
"""Holt neue Aufzeichnungen aus dem Daten-Repo und wertet sie aus.

Die App lädt jede beendete Aufzeichnung als aufnahmen/<id>.json nach
Bolumo/lagebild-daten. Dieses Skript prüft alle 10 s, legt Neues unter
daten/ ab, schreibt daten/<id>.txt und meldet eine Zeile pro Aufzeichnung.
Braucht ein angemeldetes `gh`.

    python3 github_abholen.py
"""
import importlib
import json
import subprocess
import time
from pathlib import Path

import auswertung

REPO = "Bolumo/lagebild-daten"
DATA = Path(__file__).resolve().parent / "daten"


def gh(*args):
    return subprocess.run(["gh", "api", *args], capture_output=True, text=True, check=True).stdout


def runde():
    try:
        liste = json.loads(gh(f"repos/{REPO}/contents/aufnahmen"))
    except subprocess.CalledProcessError as e:
        if "404" not in e.stderr:  # 404: Ordner entsteht erst mit der ersten Aufzeichnung
            print(f"ABHOLEN-FEHLER {e.stderr.strip()[:200]}", flush=True)
        return
    for f in liste:
        ziel = DATA / f["name"]
        if ziel.exists():
            continue
        ziel.write_text(gh("-H", "Accept: application/vnd.github.raw", f"repos/{REPO}/contents/{f['path']}"),
                        encoding="utf-8")
        try:
            importlib.reload(auswertung)  # Änderungen an auswertung.py gelten sofort
            text, kurz = auswertung.auswerten(ziel)
            ziel.with_suffix(".txt").write_text(text + "\n", encoding="utf-8")
            print(f"AUSWERTUNG {ziel.stem}: {kurz}", flush=True)
        except Exception as e:  # eine kaputte Datei soll das Abholen nicht beenden
            print(f"AUSWERTUNG-FEHLER {ziel.stem}: {e!r}", flush=True)


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    try:
        gh(f"repos/{REPO}")
        print(f"BEREIT {REPO}", flush=True)
    except subprocess.CalledProcessError as e:
        print(f"ABHOLEN-FEHLER {REPO} nicht erreichbar: {e.stderr.strip()[:200]}", flush=True)
    while True:
        runde()
        time.sleep(10)
