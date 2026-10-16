"""Integration test: the real NiceGUI server runs exactly one advancement loop.

This starts the actual application server in a subprocess and probes it. It
verifies the *lifecycle*, which unit tests with a fake scheduler cannot:

- the app-scope loop advances with NO browser connected;
- requesting the page over HTTP does not create additional loops;
- the loop is stopped on shutdown.

It is stdlib-only and bounded in time. It drives the real server process; it is
NOT a browser E2E test.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROBE_PORT = 8058

# Runs inside the server process: starts the real app, hits "/" a few times
# (simulating clients), then reports the runtime/loop counters and shuts down.
# NOTE: a plain string (not an f-string) so the embedded code's braces are not
# interpolated by this module; the repo path and port are substituted below.
_PROBE_TEMPLATE = textwrap.dedent(
    """
    import json, os, sys, threading, time, urllib.request
    sys.path.insert(0, r"__REPO_SRC__")
    from nicegui import ui
    import amr_dashboard.app as dash          # registers pages + on_startup/on_shutdown
    from amr_dashboard import runtime as rt

    OUT = {}

    def run():
        ui.run(host="127.0.0.1", port=__PORT__, reload=False, show=False,
               uvicorn_logging_level="error")

    def get(path):
        try:
            with urllib.request.urlopen("http://127.0.0.1:__PORT__" + path, timeout=2) as r:
                return r.status
        except Exception:
            return 0

    def probe():
        time.sleep(3.0)
        a = rt.get_runtime().ticks
        loop_before = rt.get_server_loop()
        statuses = [get("/") for _ in range(4)]
        time.sleep(1.0)
        b = rt.get_runtime().ticks
        loop_after = rt.get_server_loop()
        OUT["ticks_t1"] = a
        OUT["ticks_t2"] = b
        OUT["advanced"] = b > a
        OUT["http_ok"] = all(s == 200 for s in statuses)
        OUT["same_loop_object"] = loop_before is loop_after
        OUT["advance_count_before_shutdown"] = loop_after.advance_count
        OUT["running_before_shutdown"] = loop_after.running
        print("PROBEJSON " + json.dumps(OUT), flush=True)
        os._exit(0)

    threading.Thread(target=probe, daemon=True).start()
    run()
    """
)

PROBE = _PROBE_TEMPLATE.replace("__REPO_SRC__", str(REPO / "src")).replace(
    "__PORT__", str(PROBE_PORT)
)


def _run_probe() -> dict:
    env = dict(os.environ)
    # NiceGUI enters a special test mode when it sees pytest's env var; the
    # subprocess must run as a normal server.
    env.pop("PYTEST_CURRENT_TEST", None)
    proc = subprocess.run(
        [sys.executable, "-c", PROBE],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    merged: dict = {}
    for line in proc.stdout.splitlines():
        if line.startswith("PROBEJSON "):
            merged.update(json.loads(line[len("PROBEJSON "):]))
    if not merged:
        raise AssertionError(
            f"probe did not report; stdout=\n{proc.stdout}\nstderr=\n{proc.stderr}"
        )
    return merged


def test_server_loop_advances_without_any_browser() -> None:
    result = _run_probe()
    assert result["running_before_shutdown"] is True
    assert result["advanced"] is True
    assert result["ticks_t2"] > result["ticks_t1"]


def test_page_requests_do_not_add_a_second_loop() -> None:
    result = _run_probe()
    # Hitting the page 4x must not replace or multiply the loop.
    assert result["http_ok"] is True
    assert result["same_loop_object"] is True
