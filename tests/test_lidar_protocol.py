"""Tests for the LD19 / STL-19P packet protocol (pure, no hardware)."""

from __future__ import annotations

import pytest

from amr_core.lidar.protocol import (
    HEADER,
    PACKET_LEN,
    POINTS_PER_PACKET,
    LidarProtocolError,
    build_packet,
    crc8,
    decode_packet,
)


def _packet(**overrides) -> bytes:
    fields = {
        "speed_dps": 3580,
        "start_angle_deg": 0.0,
        "end_angle_deg": 11.0,
        "timestamp_ms": 0,
        "measurements": [(100 + i, i) for i in range(POINTS_PER_PACKET)],
    }
    fields.update(overrides)
    return build_packet(**fields)


# --- CRC-8 ----------------------------------------------------------------- #

def test_crc8_matches_fixed_vectors() -> None:
    # Poly 0x4D, init 0x00, no reflection, no final xor.
    assert crc8(b"") == 0x00
    assert crc8(b"123456789") == 0xC3
    assert crc8(bytes(range(10))) == 0xA5


def test_crc8_validates_packet_prefix() -> None:
    packet = _packet()
    assert crc8(packet[:46]) == packet[46]


# --- build / decode round trip --------------------------------------------- #

def test_packet_length_and_header() -> None:
    packet = _packet()
    assert len(packet) == PACKET_LEN
    assert packet[:2] == HEADER


def test_decode_round_trip_fields() -> None:
    packet = _packet(speed_dps=3580, start_angle_deg=12.34, end_angle_deg=45.67, timestamp_ms=999)
    decoded = decode_packet(packet)
    assert decoded.speed_dps == 3580
    assert decoded.start_angle_deg == pytest.approx(12.34)
    assert decoded.end_angle_deg == pytest.approx(45.67)
    assert decoded.timestamp_ms == 999
    assert len(decoded.measurements) == POINTS_PER_PACKET
    assert decoded.measurements[0] == (100, 0)


def test_decode_reads_twelve_points_not_six() -> None:
    # The task brief said six points; the device/script say twelve.
    decoded = decode_packet(_packet())
    assert len(decoded.measurements) == 12
    assert len(decoded.points()) == 12


# --- angle interpolation ---------------------------------------------------- #

def test_point_angles_interpolate_between_start_and_end() -> None:
    decoded = decode_packet(_packet(start_angle_deg=0.0, end_angle_deg=11.0))
    angles = [p.angle_deg for p in decoded.points()]
    assert angles[0] == pytest.approx(0.0)
    assert angles[-1] == pytest.approx(11.0)
    # Evenly spaced by (end - start) / (points - 1).
    assert angles[1] == pytest.approx(1.0)


def test_point_angles_wrap_across_360() -> None:
    decoded = decode_packet(_packet(start_angle_deg=350.0, end_angle_deg=10.0))
    angles = [p.angle_deg for p in decoded.points()]
    assert angles[0] == pytest.approx(350.0)
    assert angles[-1] == pytest.approx(10.0)
    assert all(0.0 <= a < 360.0 for a in angles)
    # The sweep crosses 0 deg between 359.x and 0.x.
    assert any(a > 350.0 for a in angles)
    assert any(a < 10.0 for a in angles)


def test_zero_distance_is_invalid_not_free_space() -> None:
    decoded = decode_packet(_packet(measurements=[(0, 0)] * POINTS_PER_PACKET))
    for point in decoded.points():
        assert point.distance_mm == 0
        assert not point.valid


# --- validation failures ---------------------------------------------------- #

def test_wrong_length_raises() -> None:
    with pytest.raises(LidarProtocolError) as excinfo:
        decode_packet(b"\x54\x2c\x00")
    assert excinfo.value.kind == "length"


def test_bad_header_raises() -> None:
    packet = bytearray(_packet())
    packet[0] = 0x00
    with pytest.raises(LidarProtocolError) as excinfo:
        decode_packet(bytes(packet))
    assert excinfo.value.kind == "header"


def test_bad_verlen_raises() -> None:
    packet = bytearray(_packet())
    packet[1] = 0x21  # low 5 bits = 1 point, not 12; byte 0 stays 0x54
    with pytest.raises(LidarProtocolError) as excinfo:
        decode_packet(bytes(packet))
    assert excinfo.value.kind == "verlen"


def test_crc_mismatch_raises() -> None:
    packet = bytearray(_packet())
    packet[46] ^= 0xFF
    with pytest.raises(LidarProtocolError) as excinfo:
        decode_packet(bytes(packet))
    assert excinfo.value.kind == "crc"
