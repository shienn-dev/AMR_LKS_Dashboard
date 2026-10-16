"""Tests for scan accumulation and consistent snapshots."""

from __future__ import annotations

from amr_core.lidar.protocol import POINTS_PER_PACKET, build_packet, decode_packet
from amr_core.lidar.scan import ScanAccumulator


def _packet(start_deg: float, end_deg: float, distance_mm: int = 1000):
    return decode_packet(
        build_packet(
            speed_dps=3580,
            start_angle_deg=start_deg,
            end_angle_deg=end_deg,
            timestamp_ms=0,
            measurements=[(distance_mm, 1)] * POINTS_PER_PACKET,
        )
    )


def test_single_packet_is_not_a_full_revolution() -> None:
    acc = ScanAccumulator(buckets=360)
    acc.add_packet(_packet(0.0, 11.0))
    snapshot = acc.snapshot()
    assert not snapshot.complete
    assert snapshot.coverage_fraction < 0.1
    # Only the 12 buckets the packet covers hold data.
    assert len(snapshot.points) == 12


def test_many_packets_fill_a_full_revolution() -> None:
    acc = ScanAccumulator(buckets=360)
    # 36 packets x 12 deg = 432 deg > one revolution.
    for k in range(36):
        start = (k * 12) % 360
        acc.add_packet(_packet(start, (start + 11) % 360))
    snapshot = acc.snapshot()
    assert snapshot.complete
    assert snapshot.coverage_fraction == 1.0
    assert len(snapshot.points) == 360
    # A 360 -> 0 wrap was observed.
    assert snapshot.revolutions >= 1


def test_points_are_arranged_by_angle_with_wrap() -> None:
    acc = ScanAccumulator(buckets=360)
    acc.add_packet(_packet(350.0, 1.0))
    angles = sorted(p.angle_deg for p in acc.snapshot().points)
    assert angles[0] < 5.0            # low angles from the wrap
    assert angles[-1] > 345.0         # high angles
    assert all(0.0 <= a < 360.0 for a in angles)


def test_snapshot_uses_latest_reading_per_bucket() -> None:
    acc = ScanAccumulator(buckets=360)
    acc.add_packet(_packet(0.0, 0.0, distance_mm=1000))
    acc.add_packet(_packet(0.0, 0.0, distance_mm=2000))
    points = [p for p in acc.snapshot().points if int(p.angle_deg) == 0]
    assert points and points[0].distance_mm == 2000


def test_zero_distance_kept_as_invalid() -> None:
    acc = ScanAccumulator(buckets=360)
    acc.add_packet(_packet(0.0, 11.0, distance_mm=0))
    snapshot = acc.snapshot()
    assert snapshot.invalid_count == 12
    assert snapshot.valid_points == ()


def test_snapshot_is_immutable_and_isolated() -> None:
    acc = ScanAccumulator(buckets=360)
    acc.add_packet(_packet(0.0, 11.0))
    first = acc.snapshot()
    count = len(first.points)

    # Mutating the accumulator afterwards must not change the old snapshot.
    acc.reset()
    assert len(first.points) == count
    assert acc.snapshot().points == ()
    assert isinstance(first.points, tuple)
