"""Angle-bucketed accumulation of LiDAR points and immutable snapshots.

A single 47-byte packet holds only 12 points, which is a small arc, not a full
revolution. This module collects points from many packets into a fixed set of
angular buckets (default: 1 degree each) and publishes an **immutable**
:class:`ScanSnapshot` under a lock, so the UI always reads a consistent copy
and never a half-updated scan.

Zero / invalid distances are stored as-is and reported as *invalid*; they are
never converted to free space.
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass

from amr_core.lidar.protocol import LidarPacket

DEFAULT_BUCKETS = 360


@dataclass(frozen=True)
class ScanPoint:
    """One point in a snapshot (the latest reading in its angular bucket)."""

    angle_deg: float
    distance_mm: int
    intensity: int

    @property
    def valid(self) -> bool:
        """True only for a positive distance. ``0`` is 'no valid return'."""
        return self.distance_mm > 0

    def cartesian_mm(self) -> tuple[float, float]:
        """Return ``(x, y)`` in mm; angle 0 deg is +x, increasing counter-clockwise."""
        rad = math.radians(self.angle_deg)
        return (self.distance_mm * math.cos(rad), self.distance_mm * math.sin(rad))


@dataclass(frozen=True)
class ScanSnapshot:
    """An immutable view of the accumulated scan.

    ``points`` holds only buckets that have data. ``coverage_fraction`` is the
    fraction of angular buckets filled; ``complete`` is True once every bucket
    has been filled at least once (i.e. a full revolution has been observed).
    ``revolutions`` counts detected 360 -> 0 deg wraps since the last reset.
    """

    points: tuple[ScanPoint, ...]
    buckets: int
    coverage_fraction: float
    complete: bool
    revolutions: int
    stamp_s: float

    @property
    def valid_points(self) -> tuple[ScanPoint, ...]:
        return tuple(p for p in self.points if p.valid)

    @property
    def invalid_count(self) -> int:
        return sum(1 for p in self.points if not p.valid)


class ScanAccumulator:
    """Thread-safe collector of LiDAR points into angular buckets.

    The reader thread calls :meth:`add_packet`; the UI thread calls
    :meth:`snapshot`. All shared state is guarded by an internal lock.
    """

    def __init__(self, buckets: int = DEFAULT_BUCKETS, clock=time.monotonic) -> None:
        if buckets <= 0:
            raise ValueError("buckets must be positive")
        self._buckets = buckets
        self._clock = clock
        self._lock = threading.Lock()
        # None = no data yet for this bucket; otherwise an int distance in mm.
        self._distance: list[int | None] = [None] * buckets
        self._intensity: list[int] = [0] * buckets
        self._angle: list[float] = [0.0] * buckets
        self._filled = 0
        self._revolutions = 0
        self._last_bucket: int | None = None

    @property
    def buckets(self) -> int:
        return self._buckets

    def add_packet(self, packet: LidarPacket) -> None:
        """Fold one decoded packet into the accumulator (thread-safe)."""
        points = packet.points()
        if not points:
            return
        with self._lock:
            for point in points:
                index = int(point.angle_deg) % self._buckets
                if self._distance[index] is None:
                    self._filled += 1
                self._distance[index] = point.distance_mm
                self._intensity[index] = point.intensity
                self._angle[index] = point.angle_deg
            self._track_revolution(int(points[0].angle_deg) % self._buckets)

    def _track_revolution(self, first_bucket: int) -> None:
        """Count a wrap when the sweep start jumps backwards significantly."""
        previous = self._last_bucket
        if previous is not None:
            threshold = self._buckets // 4
            if first_bucket < previous and (previous - first_bucket) > threshold:
                self._revolutions += 1
        self._last_bucket = first_bucket

    def snapshot(self) -> ScanSnapshot:
        """Return a consistent, immutable copy of the current scan."""
        with self._lock:
            points = tuple(
                ScanPoint(
                    angle_deg=self._angle[i],
                    distance_mm=self._distance[i],  # type: ignore[arg-type]
                    intensity=self._intensity[i],
                )
                for i in range(self._buckets)
                if self._distance[i] is not None
            )
            filled = self._filled
            revolutions = self._revolutions
            stamp = self._clock()
        return ScanSnapshot(
            points=points,
            buckets=self._buckets,
            coverage_fraction=filled / self._buckets,
            complete=filled >= self._buckets,
            revolutions=revolutions,
            stamp_s=stamp,
        )

    def reset(self) -> None:
        """Clear all accumulated points (thread-safe)."""
        with self._lock:
            self._distance = [None] * self._buckets
            self._intensity = [0] * self._buckets
            self._angle = [0.0] * self._buckets
            self._filled = 0
            self._revolutions = 0
            self._last_bucket = None
