"""Read the physical LiDAR for a few seconds and print a summary.

This is a diagnostics / verification tool (it is NOT part of the dashboard). It
uses the same backend reader as the dashboard, so a successful run here means
the integration path works against the real device.

Usage::

    python scripts/lidar_probe.py                 # 5 s, /dev/ttyUSB0 @ 230400
    python scripts/lidar_probe.py --seconds 10
    python scripts/lidar_probe.py --port /dev/ttyUSB1 --baud 230400

Exit codes: 0 = valid packets received, 2 = no valid packets, 3 = reader
unavailable (e.g. pyserial missing).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from amr_core.lidar.config import LidarConfig  # noqa: E402
from amr_core.lidar.reader import LidarReader  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="LiDAR read probe")
    parser.add_argument("--port", default=None, help="serial port (default from env)")
    parser.add_argument("--baud", type=int, default=None, help="baud rate")
    parser.add_argument("--seconds", type=float, default=5.0, help="read duration")
    args = parser.parse_args()

    config = LidarConfig.from_env().with_overrides(port=args.port, baud=args.baud)
    reader = LidarReader(config)

    print(f"Reading {config.port} @ {config.baud} baud for {args.seconds:g} s ...")
    if not reader.start():
        print("UNAVAILABLE: the reader could not start (is pyserial installed?)")
        return 3

    try:
        time.sleep(args.seconds)
    except KeyboardInterrupt:
        print("interrupted")
    finally:
        reader.stop()

    stats = reader.stats()
    snapshot = reader.snapshot()
    print("--- reader stats ---")
    print(f"status          : {stats.status.value}")
    print(f"packets ok      : {stats.packets_ok}")
    print(f"packets/s       : {stats.packets_per_s:.0f}")
    print(f"CRC failures    : {stats.crc_failures}")
    print(f"sync failures   : {stats.sync_failures}")
    print(f"bytes read      : {stats.bytes_read}")
    print(f"reconnects      : {stats.reconnects}")
    print(f"last error      : {stats.last_error or '-'}")
    print("--- scan snapshot ---")
    print(f"points          : {len(snapshot.points)} / {snapshot.buckets}")
    print(f"coverage        : {snapshot.coverage_fraction:.0%}")
    print(f"revolutions     : {snapshot.revolutions}")
    print(f"invalid (0 mm)  : {snapshot.invalid_count}")
    for point in snapshot.valid_points[:5]:
        print(f"  angle {point.angle_deg:6.2f} deg  distance {point.distance_mm:5d} mm")
    for note in reader.recent_notes()[-5:]:
        print(f"note: {note}")

    if stats.packets_ok <= 0:
        print("RESULT: no valid packets received.")
        return 2
    print("RESULT: valid LiDAR data received.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
