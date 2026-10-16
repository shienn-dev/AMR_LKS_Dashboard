"""LD19 / STL-19P packet protocol: CRC-8, decode and (test) encode.

This module is **pure Python** with no serial I/O and no third-party
dependency. The decoder is derived from the team's own verified capture script
(``~/lidar-test/test_stl19p.py``) and cross-checked against the LDROBOT
STL-19P / LD19 protocol documentation.

Packet layout (47 bytes, multi-byte fields little-endian)::

    offset  size  field
    0       1     header 0x54
    1       1     VerLen 0x2C (high 3 bits = packet type 1, low 5 bits = 12 points)
    2       2     rotation speed, degrees/second
    4       2     start angle, 0.01 degree units
    6       36    12 measurement points x 3 bytes (2-byte distance mm + 1-byte intensity)
    42      2     end angle, 0.01 degree units
    44      2     timestamp, milliseconds (wraps)
    46      1     CRC-8 over bytes 0..45, poly 0x4D, init 0x00

Discrepancy with the task brief (recorded deliberately)
-------------------------------------------------------
The brief described "six distance values, 3 bytes each". The team's own
capture script reads **twelve** values (``range(6, 42, 3)`` over 36 bytes) and
the LDROBOT datasheet also specifies 12 points per packet. The brief's "six"
is therefore incorrect for this device; this module follows the script and the
datasheet (12 points). The packet length (47) and header (``0x54 0x2C``) in the
brief are confirmed correct.

Angle interpolation (assumption, flagged)
-----------------------------------------
Per-point angles are linearly interpolated between the start and end angle.
The LDROBOT datasheet uses ``step = (end - start) / (points - 1)`` (divisor
11). Some community ports divide by ``points`` (12) instead. We use the
datasheet's ``points - 1``; this is an **assumption not yet verified against
the physical device** (see :data:`ANGLE_STEP_DIVISOR`).
"""

from __future__ import annotations

from dataclasses import dataclass

HEADER = b"\x54\x2c"
PACKET_LEN = 47
POINTS_PER_PACKET = 12
CRC_POLY = 0x4D
CRC_INIT = 0x00
_ANGLE_SCALE = 100.0
_MEASUREMENT_START = 6
_MEASUREMENT_BYTES = 3
_END_ANGLE_OFFSET = 42
_TIMESTAMP_OFFSET = 44
_CRC_OFFSET = PACKET_LEN - 1

# Divisor used to interpolate the 12 point angles. See module docstring.
ANGLE_STEP_DIVISOR = POINTS_PER_PACKET - 1


def crc8(data: bytes | bytearray) -> int:
    """CRC-8 with polynomial 0x4D and initial value 0x00.

    Matches the routine in the team's verified capture script and validates the
    first 46 bytes of every packet against byte 46.
    """
    crc = CRC_INIT
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ CRC_POLY) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


class LidarProtocolError(ValueError):
    """A packet failed validation.

    ``kind`` is a short machine-readable reason: ``"length"``, ``"header"``,
    ``"verlen"`` or ``"crc"``. The reader uses it to keep separate counters.
    """

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class LidarPoint:
    """One decoded measurement.

    ``distance_mm`` is the raw distance; ``0`` means "no valid return" and must
    never be interpreted as free space. ``intensity`` is the raw confidence
    byte from the packet.
    """

    angle_deg: float
    distance_mm: int
    intensity: int

    @property
    def valid(self) -> bool:
        """True only for a positive distance (a real return)."""
        return self.distance_mm > 0


@dataclass(frozen=True)
class LidarPacket:
    """A validated 47-byte packet, decoded into its fields.

    ``measurements`` is a tuple of ``(distance_mm, intensity)`` pairs, in the
    order they appear in the packet.
    """

    speed_dps: int
    start_angle_deg: float
    end_angle_deg: float
    timestamp_ms: int
    measurements: tuple[tuple[int, int], ...]

    def points(self) -> tuple[LidarPoint, ...]:
        """Return the per-point measurements with interpolated angles.

        Handles the 360 deg -> 0 deg wrap: when the end angle is numerically
        smaller than the start angle, 360 is added before interpolating, and
        every resulting angle is reduced modulo 360.
        """
        start = self.start_angle_deg
        end = self.end_angle_deg
        if end < start:
            end += 360.0
        step = (end - start) / ANGLE_STEP_DIVISOR
        return tuple(
            LidarPoint(
                angle_deg=(start + step * i) % 360.0,
                distance_mm=distance,
                intensity=intensity,
            )
            for i, (distance, intensity) in enumerate(self.measurements)
        )


def decode_packet(packet: bytes) -> LidarPacket:
    """Validate and decode one packet.

    Raises :class:`LidarProtocolError` if the packet is the wrong length, has a
    bad header/VerLen, or fails the CRC check. Data is only considered valid
    after it has passed every check.
    """
    if len(packet) != PACKET_LEN:
        raise LidarProtocolError(
            "length", f"expected {PACKET_LEN} bytes, got {len(packet)}"
        )
    if packet[0] != HEADER[0]:
        raise LidarProtocolError("header", f"bad header: {packet[:2].hex()}")
    if (packet[1] & 0x1F) != POINTS_PER_PACKET:
        raise LidarProtocolError(
            "verlen", f"unexpected point count in VerLen byte: 0x{packet[1]:02x}"
        )
    if crc8(packet[:_CRC_OFFSET]) != packet[_CRC_OFFSET]:
        raise LidarProtocolError("crc", "CRC-8 mismatch")

    speed_dps = int.from_bytes(packet[2:4], "little")
    start_angle_deg = int.from_bytes(packet[4:6], "little") / _ANGLE_SCALE
    end_angle_deg = int.from_bytes(
        packet[_END_ANGLE_OFFSET : _END_ANGLE_OFFSET + 2], "little"
    ) / _ANGLE_SCALE
    timestamp_ms = int.from_bytes(
        packet[_TIMESTAMP_OFFSET : _TIMESTAMP_OFFSET + 2], "little"
    )

    measurements = tuple(
        (
            int.from_bytes(
                packet[
                    _MEASUREMENT_START + _MEASUREMENT_BYTES * i :
                    _MEASUREMENT_START + _MEASUREMENT_BYTES * i + 2
                ],
                "little",
            ),
            packet[_MEASUREMENT_START + _MEASUREMENT_BYTES * i + 2],
        )
        for i in range(POINTS_PER_PACKET)
    )

    return LidarPacket(
        speed_dps=speed_dps,
        start_angle_deg=start_angle_deg,
        end_angle_deg=end_angle_deg,
        timestamp_ms=timestamp_ms,
        measurements=measurements,
    )


def build_packet(
    *,
    speed_dps: int,
    start_angle_deg: float,
    end_angle_deg: float,
    timestamp_ms: int,
    measurements: tuple[tuple[int, int], ...] | list[tuple[int, int]],
) -> bytes:
    """Encode a valid 47-byte packet (used by tests and the probe script).

    ``measurements`` is a sequence of ``(distance_mm, intensity)`` pairs; up to
    12 are used, missing points are encoded as ``(0, 0)``.
    """
    packet = bytearray(PACKET_LEN)
    packet[0] = HEADER[0]
    packet[1] = HEADER[1]
    packet[2:4] = (int(speed_dps) & 0xFFFF).to_bytes(2, "little")
    packet[4:6] = (round(start_angle_deg * _ANGLE_SCALE) & 0xFFFF).to_bytes(2, "little")
    for i in range(POINTS_PER_PACKET):
        distance, intensity = (
            measurements[i] if i < len(measurements) else (0, 0)
        )
        offset = _MEASUREMENT_START + _MEASUREMENT_BYTES * i
        packet[offset : offset + 2] = (int(distance) & 0xFFFF).to_bytes(2, "little")
        packet[offset + 2] = int(intensity) & 0xFF
    packet[_END_ANGLE_OFFSET : _END_ANGLE_OFFSET + 2] = (
        round(end_angle_deg * _ANGLE_SCALE) & 0xFFFF
    ).to_bytes(2, "little")
    packet[_TIMESTAMP_OFFSET : _TIMESTAMP_OFFSET + 2] = (
        int(timestamp_ms) & 0xFFFF
    ).to_bytes(2, "little")
    packet[_CRC_OFFSET] = crc8(packet[:_CRC_OFFSET])
    return bytes(packet)
