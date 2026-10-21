"""STM32 robot-controller serial protocol: pure frame codec.

The chassis/arm/IMU controller is an STM32 board on ``/dev/ttyACM0`` (USB
``1a86:55d4``). This module decodes the **byte stream the board sends** and
encodes the **frames the board accepts**. It never opens a port, never writes a
byte and never commands the robot by itself: it is a pure function of the bytes
handed to it by the caller.

Frame layout (agreed by the shipped Hiwonder "LanderAsli" SDK and the upstream
``Hiwonder/LanderPi`` SDK)::

    offset  size  field
    0       1     sync 0xAA
    1       1     sync 0x55
    2       1     function code
    3       1     payload length N (0..255)
    4       N     payload
    4+N     1     CRC-8 over bytes [function, length, payload] (i.e. bytes 2..3+N)

CRC-8 is **reflected / LSB-first**, polynomial ``0x8C`` (the reflection of
``0x31``, i.e. CRC-8/MAXIM-DOW), init ``0x00``, no final xor. This reproduces the
256-entry table in the shipped SDK exactly (verified byte-for-byte) and the
standard check value ``crc8(b"123456789") == 0xA1``.

Verification status (important)
-------------------------------
- Frame / CRC / motor format: **verified in the stock Lander software** (two
  independent SDK copies agree).
- Communication with the **school robot's** (ROBO JX-modified) firmware:
  **NOT verified**. This module only parses; it does not prove the school board
  speaks this protocol, and it must not be used to send anything yet.

Decoded payloads (only formats that are actually known)
-------------------------------------------------------
- ``IMU`` (func 7): 6 little-endian float32 = ax, ay, az, gx, gy, gz. Units and
  scaling are **not** documented by the SDK (returned raw); treat as uncalibrated.
- ``SYS`` (func 0) battery: only subtype ``payload[0] == 0x04`` is known ->
  little-endian uint16. ``set_battery_level`` maps 10.5 V to 0x2904 (= 10500), so
  the raw unit is *probably* millivolts — **uncertain**. Other SYS subtypes are
  not decoded.
- ``KEY`` (func 6): 2 bytes = key id, key event (see ``KEY_EVENT_*``).

Every other function (LED=1, BUZZER=2, PWM_SERVO=4, BUS_SERVO=5,
GAMEPAD=8, SBUS=9, OLED=10) is recognised by *number* but its payload is
**not decoded** here, because its exact layout is uncertain — the raw payload
is returned and no interpretation is invented. No encoder-feedback function is
known to exist in either SDK.

``MOTOR`` (func 3) is the one function that is **encoded** here (see
:func:`build_motor_frame`): its layout is confirmed on this robot's board
(motor ids 1..4, speed in rps), and the board accepts it. It is still never
*decoded*, because the board does not echo motor frames back.

Version note: the shipped SDK has ``PACKET_FUNC_NONE = 11`` and no RGB function;
the upstream SDK adds ``RGB = 11`` with ``NONE = 12``. This decoder does not
depend on that boundary — it accepts any function byte and only interprets the
ones it knows.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum

SYNC1 = 0xAA
SYNC2 = 0x55
# Header (2) + function (1) + length (1) + CRC (1); a zero-length frame is 5 bytes.
MIN_FRAME_BYTES = 5
# The length field is one byte, so 255 is the structural maximum.
MAX_PAYLOAD_LEN = 255
# Defensive cap on the decoder's internal buffer (bounds memory on garbage input).
DEFAULT_MAX_BUFFER_BYTES = 4096
# Reflected CRC-8 polynomial (reflection of 0x31).
CRC8_POLY_REFLECTED = 0x8C


class Stm32Function(IntEnum):
    """Function codes seen in the two stock SDKs.

    Only the ones with a *known* payload format are decoded (see the module
    docstring). ``RGB``/``NONE`` are version-dependent and deliberately omitted.
    """

    SYS = 0
    LED = 1
    BUZZER = 2
    MOTOR = 3
    PWM_SERVO = 4
    BUS_SERVO = 5
    KEY = 6
    IMU = 7
    GAMEPAD = 8
    SBUS = 9
    OLED = 10


# CRC-8 table, copied verbatim from the shipped Hiwonder "LanderAsli" SDK
# (arm_pc/ros_robot_controller_sdk.py). tests/test_stm32_protocol.py re-derives it
# from the reflected polynomial 0x8C to prove it is not a hand-typed assumption.
CRC8_TABLE: tuple[int, ...] = (
    0, 94, 188, 226, 97, 63, 221, 131, 194, 156, 126, 32, 163, 253, 31, 65,
    157, 195, 33, 127, 252, 162, 64, 30, 95, 1, 227, 189, 62, 96, 130, 220,
    35, 125, 159, 193, 66, 28, 254, 160, 225, 191, 93, 3, 128, 222, 60, 98,
    190, 224, 2, 92, 223, 129, 99, 61, 124, 34, 192, 158, 29, 67, 161, 255,
    70, 24, 250, 164, 39, 121, 155, 197, 132, 218, 56, 102, 229, 187, 89, 7,
    219, 133, 103, 57, 186, 228, 6, 88, 25, 71, 165, 251, 120, 38, 196, 154,
    101, 59, 217, 135, 4, 90, 184, 230, 167, 249, 27, 69, 198, 152, 122, 36,
    248, 166, 68, 26, 153, 199, 37, 123, 58, 100, 134, 216, 91, 5, 231, 185,
    140, 210, 48, 110, 237, 179, 81, 15, 78, 16, 242, 172, 47, 113, 147, 205,
    17, 79, 173, 243, 112, 46, 204, 146, 211, 141, 111, 49, 178, 236, 14, 80,
    175, 241, 19, 77, 206, 144, 114, 44, 109, 51, 209, 143, 12, 82, 176, 238,
    50, 108, 142, 208, 83, 13, 239, 177, 240, 174, 76, 18, 145, 207, 45, 115,
    202, 148, 118, 40, 171, 245, 23, 73, 8, 86, 180, 234, 105, 55, 213, 139,
    87, 9, 235, 181, 54, 104, 138, 212, 149, 203, 41, 119, 244, 170, 72, 22,
    233, 183, 85, 11, 136, 214, 52, 106, 43, 117, 151, 201, 74, 20, 246, 168,
    116, 42, 200, 150, 21, 75, 169, 247, 182, 232, 10, 84, 215, 137, 107, 53,
)


def crc8(data: bytes | bytearray) -> int:
    """CRC-8 (reflected, poly 0x8C, init 0) over *data*.

    Matches the shipped SDK's ``checksum_crc8`` and the standard CRC-8/MAXIM-DOW
    check value ``crc8(b"123456789") == 0xA1``.
    """
    check = 0
    for byte in data:
        check = CRC8_TABLE[check ^ byte]
    return check & 0xFF


# Button ("KEY") event bits, from PacketReportKeyEvents in the shipped SDK.
KEY_EVENT_PRESSED = 0x01
KEY_EVENT_LONGPRESS = 0x02
KEY_EVENT_LONGPRESS_REPEAT = 0x04
KEY_EVENT_RELEASE_FROM_LP = 0x08
KEY_EVENT_RELEASE_FROM_SP = 0x10
KEY_EVENT_CLICK = 0x20
KEY_EVENT_DOUBLE_CLICK = 0x40
KEY_EVENT_TRIPLE_CLICK = 0x80

# Battery is a SYS sub-message; only this subtype is known.
SYS_BATTERY_SUBTYPE = 0x04
IMU_PAYLOAD_LEN = 24  # 6 x float32


@dataclass(frozen=True)
class Stm32Frame:
    """One validated frame (CRC already checked)."""

    function: int
    payload: bytes
    raw: bytes


@dataclass(frozen=True)
class ImuReading:
    """Decoded IMU payload (raw, uncalibrated floats; units not documented)."""

    ax: float
    ay: float
    az: float
    gx: float
    gy: float
    gz: float


@dataclass(frozen=True)
class BatteryReading:
    """Decoded SYS battery sub-message (raw uint16; unit uncertain)."""

    raw: int


@dataclass(frozen=True)
class ButtonEvent:
    """Decoded KEY payload: which key, and its event bit."""

    key_id: int
    event: int


@dataclass
class DecoderStats:
    """Counters for a :class:`FrameDecoder`."""

    bytes_fed: int = 0
    frames_ok: int = 0
    crc_errors: int = 0
    length_errors: int = 0
    resyncs: int = 0
    overflows: int = 0


def decode_imu(payload: bytes) -> ImuReading | None:
    """Decode an IMU (func 7) payload; returns None if the length is wrong."""
    if len(payload) != IMU_PAYLOAD_LEN:
        return None
    return ImuReading(*struct.unpack("<6f", payload))


def decode_battery(payload: bytes) -> BatteryReading | None:
    """Decode a SYS (func 0) battery payload; None for other SYS subtypes."""
    if len(payload) < 3 or payload[0] != SYS_BATTERY_SUBTYPE:
        return None
    return BatteryReading(raw=struct.unpack("<H", payload[1:3])[0])


def decode_button(payload: bytes) -> ButtonEvent | None:
    """Decode a KEY (func 6) payload; None if too short."""
    if len(payload) < 2:
        return None
    return ButtonEvent(key_id=payload[0], event=payload[1])


def decode_payload(frame: Stm32Frame) -> ImuReading | BatteryReading | ButtonEvent | None:
    """Dispatch a frame to the right payload decoder.

    Returns None for functions whose payload format is not known (no guessing).
    """
    if frame.function == Stm32Function.IMU:
        return decode_imu(frame.payload)
    if frame.function == Stm32Function.SYS:
        return decode_battery(frame.payload)
    if frame.function == Stm32Function.KEY:
        return decode_button(frame.payload)
    return None


def build_frame(function: int, payload: bytes = b"") -> bytes:
    """Encode one frame (for tests/tools only; this module never sends it)."""
    if len(payload) > MAX_PAYLOAD_LEN:
        raise ValueError(f"payload too long: {len(payload)} > {MAX_PAYLOAD_LEN}")
    frame = bytearray([SYNC1, SYNC2, function & 0xFF, len(payload)])
    frame.extend(payload)
    frame.append(crc8(frame[2:]))
    return bytes(frame)


def build_motor_frame(speeds: list[tuple[int, float]]) -> bytes:
    """Encode one func-3 MOTOR frame: ``[0x01, n, (id-1, rps) x n]``.

    ``speeds`` is a list of ``(motor_id, rps)`` pairs. The speed is a float32 in
    revolutions per second (rps), little endian. Motor ids are 1..4 and are sent
    as ``id - 1``.

    This is the **single** motor-frame encoder in the repository: the
    supervised wheel test (:mod:`scripts.wheel_test`) and the dashboard's
    serial chassis adapter both use it, so the two can never disagree about
    the bytes that reach the board.
    """
    payload = bytearray([0x01, len(speeds)])
    for motor_id, rps in speeds:
        if not 1 <= motor_id <= 4:
            raise ValueError(f"motor id must be 1..4, got {motor_id}")
        payload.extend(struct.pack("<Bf", motor_id - 1, float(rps)))
    return build_frame(Stm32Function.MOTOR, bytes(payload))


class FrameDecoder:
    """Incremental, resynchronising decoder for the STM32 frame stream.

    Feed arbitrary byte chunks to :meth:`feed`; it returns the frames that became
    complete. It handles partial data across calls, several frames in one chunk,
    a bad second sync byte, an over-long declared length, CRC failures and
    resynchronisation after a corrupt frame, and it bounds its internal buffer so
    garbage cannot grow memory without limit.
    """

    def __init__(
        self,
        *,
        max_payload_len: int = MAX_PAYLOAD_LEN,
        max_buffer_bytes: int = DEFAULT_MAX_BUFFER_BYTES,
    ) -> None:
        if max_payload_len < 0:
            raise ValueError("max_payload_len must be >= 0")
        if max_buffer_bytes < MIN_FRAME_BYTES:
            raise ValueError("max_buffer_bytes must be at least MIN_FRAME_BYTES")
        self.max_payload_len = max_payload_len
        self.max_buffer_bytes = max_buffer_bytes
        self._buffer = bytearray()
        self.stats = DecoderStats()

    @property
    def pending(self) -> bytes:
        """Bytes buffered but not yet part of a complete frame."""
        return bytes(self._buffer)

    def reset(self) -> None:
        """Drop buffered bytes (keeps the counters)."""
        self._buffer.clear()

    def _trim(self) -> None:
        overflow = len(self._buffer) - self.max_buffer_bytes
        if overflow > 0:
            del self._buffer[:overflow]
            self.stats.overflows += 1

    def feed(self, data: bytes | bytearray) -> list[Stm32Frame]:
        """Consume *data* and return every frame that is now complete."""
        if data:
            self._buffer.extend(data)
            self.stats.bytes_fed += len(data)
            self._trim()

        frames: list[Stm32Frame] = []
        while True:
            start = self._buffer.find(SYNC1)
            if start < 0:
                # Nothing that can begin a frame: discard it all.
                self._buffer.clear()
                break
            if start > 0:
                del self._buffer[:start]
                self.stats.resyncs += 1
            if len(self._buffer) < 2:
                break  # need the second sync byte
            if self._buffer[1] != SYNC2:
                # A lone 0xAA: drop it and look for the next candidate.
                del self._buffer[0]
                self.stats.resyncs += 1
                continue
            if len(self._buffer) < 4:
                break  # need function + length
            length = self._buffer[3]
            if length > self.max_payload_len:
                self.stats.length_errors += 1
                del self._buffer[0]
                continue
            total = MIN_FRAME_BYTES + length
            if len(self._buffer) < total:
                break  # wait for the rest of this frame
            candidate = bytes(self._buffer[:total])
            if crc8(candidate[2:-1]) != candidate[-1]:
                self.stats.crc_errors += 1
                del self._buffer[0]
                continue
            frames.append(
                Stm32Frame(
                    function=candidate[2],
                    payload=candidate[4:-1],
                    raw=candidate,
                )
            )
            self.stats.frames_ok += 1
            del self._buffer[:total]

        return frames
