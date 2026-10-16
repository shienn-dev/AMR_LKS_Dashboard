"""Real LiDAR (LD19 / STL-19P) integration for the AMR dashboard.

This package is *backend only*: it performs serial I/O and packet decoding and
publishes immutable scan snapshots. It contains no NiceGUI/UI code and imports
no UI dependency, so it can run (and be tested) without the dashboard.

Nothing here requires ROS 2. The protocol layer is pure Python with no third
party dependency; only :mod:`amr_core.lidar.reader` needs ``pyserial``, and it
imports it lazily so the rest of the application still works when ``pyserial``
is not installed (it then reports a clear "unavailable" status).

Design goals (see the task brief):
- serial reading happens on a dedicated background thread, never the UI thread;
- a consistent, immutable snapshot is published so the UI never reads a
  half-updated scan;
- one 47-byte packet is *not* a full revolution: points from many packets are
  accumulated and arranged by angle;
- zero/invalid distances are preserved as invalid, never treated as free space;
- the same serial port is never opened by two readers in one process.
"""

from __future__ import annotations

from amr_core.lidar.config import LidarConfig
from amr_core.lidar.protocol import (
    ANGLE_STEP_DIVISOR,
    HEADER,
    PACKET_LEN,
    POINTS_PER_PACKET,
    LidarPacket,
    LidarPoint,
    LidarProtocolError,
    build_packet,
    crc8,
    decode_packet,
)
from amr_core.lidar.reader import LidarReader, LidarStats, LidarStatus
from amr_core.lidar.scan import ScanAccumulator, ScanPoint, ScanSnapshot

__all__ = [
    "ANGLE_STEP_DIVISOR",
    "HEADER",
    "PACKET_LEN",
    "POINTS_PER_PACKET",
    "LidarConfig",
    "LidarPacket",
    "LidarPoint",
    "LidarProtocolError",
    "LidarReader",
    "LidarStats",
    "LidarStatus",
    "ScanAccumulator",
    "ScanPoint",
    "ScanSnapshot",
    "build_packet",
    "crc8",
    "decode_packet",
]
