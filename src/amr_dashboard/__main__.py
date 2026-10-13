"""Allow ``python -m amr_dashboard`` to launch the prototype."""

from __future__ import annotations

import argparse

from amr_dashboard.app import run


def main() -> None:
    parser = argparse.ArgumentParser(description="AMR LKS operator dashboard (Phase 1 prototype)")
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="port (default 8080)")
    parser.add_argument("--reload", action="store_true", help="auto-reload on file changes")
    args = parser.parse_args()
    run(host=args.host, port=args.port, reload=args.reload)


if __name__ in {"__main__", "__mp_main__"}:
    main()
