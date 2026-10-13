"""Smoke-test the dashboard: start the NiceGUI server, fetch '/', then exit.

Run:  python scripts/smoke_dashboard.py
Exits with code 0 if the main page returns HTTP 200, otherwise 1.
"""

from __future__ import annotations

import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nicegui import app, ui  # noqa: E402

import amr_dashboard.app as dashboard  # noqa: E402,F401  (registers the page)

HOST = "127.0.0.1"
PORT = 8077
OK_STATUS = 200


def _fetch_when_ready() -> None:
    url = f"http://{HOST}:{PORT}/"
    status = 0
    for _ in range(40):
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:  # noqa: S310
                status = resp.status
                break
        except Exception:  # noqa: BLE001
            time.sleep(0.25)
    print(f"SMOKE: GET / -> HTTP {status}")
    os._exit(0 if status == OK_STATUS else 1)


def main() -> None:
    app.on_startup(lambda: threading.Thread(target=_fetch_when_ready, daemon=True).start())
    ui.run(host=HOST, port=PORT, title="smoke", reload=False, show=False)


if __name__ in {"__main__", "__mp_main__"}:
    main()
