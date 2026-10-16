"""Allow ``python -m amr_dashboard`` to launch the prototype."""

from __future__ import annotations

import argparse

from amr_core.lidar.config import LidarConfig
from amr_dashboard.app import run


def main() -> None:
    parser = argparse.ArgumentParser(description="AMR LKS operator dashboard (Phase 1 prototype)")
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="port (default 8080)")
    parser.add_argument("--reload", action="store_true", help="auto-reload on file changes")

    # Live LiDAR options. Defaults come from the environment (AMR_LIDAR_PORT,
    # AMR_LIDAR_BAUD, AMR_LIDAR_ENABLED); these flags override them. The port is
    # changeable without editing code.
    lidar = parser.add_argument_group("LiDAR")
    lidar.add_argument(
        "--lidar-port",
        default=None,
        help="serial port of the LiDAR (default: $AMR_LIDAR_PORT or /dev/ttyUSB0)",
    )
    lidar.add_argument(
        "--lidar-baud",
        type=int,
        default=None,
        help="LiDAR baud rate (default: $AMR_LIDAR_BAUD or 230400)",
    )
    lidar.add_argument(
        "--no-lidar",
        action="store_true",
        help="do not open the LiDAR serial port",
    )
    args = parser.parse_args()

    config = LidarConfig.from_env()
    config = config.with_overrides(
        port=args.lidar_port,
        baud=args.lidar_baud,
        enabled=False if args.no_lidar else None,
    )

    run(host=args.host, port=args.port, reload=args.reload, lidar_config=config)


if __name__ in {"__main__", "__mp_main__"}:
    main()
