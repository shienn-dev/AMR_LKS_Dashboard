"""Tests for the LiDAR dashboard panel (SVG rendering) and runtime singleton."""

from __future__ import annotations

import pytest

from amr_core.lidar.protocol import POINTS_PER_PACKET, build_packet, decode_packet
from amr_core.lidar.scan import ScanAccumulator
from amr_dashboard import lidar_panel, lidar_runtime


def _snapshot(packets: int = 3):
    acc = ScanAccumulator(buckets=360)
    for k in range(packets):
        start = (k * 12) % 360
        packet = decode_packet(
            build_packet(
                speed_dps=3580,
                start_angle_deg=float(start),
                end_angle_deg=float((start + 11) % 360),
                timestamp_ms=0,
                measurements=[(1000, 1)] * POINTS_PER_PACKET,
            )
        )
        acc.add_packet(packet)
    return acc.snapshot()


def test_render_scan_svg_is_well_formed() -> None:
    svg = lidar_panel.render_scan_svg(_snapshot())
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    assert "circle" in svg  # at least the background ring
    # One dot per valid point (plus background/rings/crosshair lines).
    assert svg.count("<circle") > len(_snapshot().points)


def test_render_scan_svg_rejects_bad_arguments() -> None:
    snapshot = _snapshot()
    with pytest.raises(ValueError):
        lidar_panel.render_scan_svg(snapshot, size=0)
    with pytest.raises(ValueError):
        lidar_panel.render_scan_svg(snapshot, max_range_mm=0)


def test_render_scan_svg_skips_invalid_points() -> None:
    acc = ScanAccumulator(buckets=360)
    packet = decode_packet(
        build_packet(
            speed_dps=3580,
            start_angle_deg=0.0,
            end_angle_deg=11.0,
            timestamp_ms=0,
            measurements=[(0, 0)] * POINTS_PER_PACKET,  # all invalid
        )
    )
    acc.add_packet(packet)
    svg = lidar_panel.render_scan_svg(acc.snapshot())
    # Background + 4 range rings only: no data dots.
    assert svg.count("<circle") == 5


def test_runtime_exposes_a_single_shared_reader() -> None:
    lidar_runtime.reset_lidar_runtime()
    try:
        first = lidar_runtime.get_lidar_reader()
        second = lidar_runtime.get_lidar_reader()
        assert first is second  # one reader per process -> one port owner
    finally:
        lidar_runtime.reset_lidar_runtime()


def test_runtime_configure_replaces_config_before_use() -> None:
    from amr_core.lidar.config import LidarConfig

    lidar_runtime.reset_lidar_runtime()
    try:
        lidar_runtime.configure(LidarConfig(port="/dev/ttyUSB9", enabled=False))
        reader = lidar_runtime.get_lidar_reader()
        assert reader.config.port == "/dev/ttyUSB9"
        assert reader.config.enabled is False
        # Disabled config means start_lidar() does not open the port.
        assert lidar_runtime.start_lidar() is False
    finally:
        lidar_runtime.reset_lidar_runtime()
