"""Read-only STM32 listener: replay/file mode only (no hardware in this phase).

This module turns a *source of bytes* into decoded STM32 frames plus a bounded,
inspectable record for offline analysis. It is split into two strictly separated
parts:

- **Replay (implemented, tested):** :func:`replay_bytes` / :func:`replay_file`
  and :class:`Stm32Listener`, which consume byte chunks and never touch a device.
- **Serial (NOT implemented):** :class:`SerialTransport` is a placeholder that
  refuses to open a port. There is no runnable path to hardware, so a device can
  never be opened by accident.

Reset warning (documented here, NOT solved)
-------------------------------------------
Opening ``/dev/ttyACM0`` (a CDC-ACM port) can assert DTR/RTS and **reset the
STM32 board**; a reset may move actuators. The stock SDK sets ``rts=False`` and
``dtr=False`` *before* ``open()`` to reduce this, but that is **not a guarantee** —
some firmware still resets on open. Do not open the port without owner approval,
with the robot secured (wheels off the ground / arm restrained) and the E-stop
ready.

Scope discipline
----------------
Frames whose payload format is not proven are recorded as **unrecognized**
(``decoded is None``): their bytes are kept but never forced into a guessed shape.
No encoder, polling, request/response or extra decoding is implemented without
source evidence. The IMU/battery/button formats come from the stock Hiwonder SDK
and may NOT match the school's ROBO JX firmware — mismatch must be recorded, not
assumed away.
"""

from __future__ import annotations

import time
from collections import Counter, deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from amr_core.robot.stm32_protocol import (
    BatteryReading,
    ButtonEvent,
    FrameDecoder,
    ImuReading,
    Stm32Function,
    decode_payload,
)

DEFAULT_MAX_RECORDS = 1000


def function_name(function: int) -> str:
    """Human-readable name for a function byte (``UNKNOWN(0x..)`` if unknown)."""
    try:
        return Stm32Function(function).name
    except ValueError:
        return f"UNKNOWN(0x{function & 0xFF:02x})"


@dataclass(frozen=True)
class RawRecord:
    """A raw byte chunk as it arrived (for offline re-analysis)."""

    index: int
    timestamp_s: float
    data: bytes


@dataclass(frozen=True)
class FrameRecord:
    """One decoded frame plus its provenance.

    ``decoded`` is a typed reading for a *proven* payload format, otherwise
    ``None`` (unrecognized). ``function_name`` is informational only.
    """

    index: int
    timestamp_s: float
    function: int
    function_name: str
    payload: bytes
    decoded: ImuReading | BatteryReading | ButtonEvent | None

    @property
    def recognized(self) -> bool:
        """True only when the payload was decoded into a known shape."""
        return self.decoded is not None


@dataclass
class ListenerStats:
    """Counters for a :class:`Stm32Listener`."""

    chunks_in: int = 0
    bytes_in: int = 0
    frames_ok: int = 0
    crc_errors: int = 0
    length_errors: int = 0
    resyncs: int = 0
    overflows: int = 0
    unrecognized_frames: int = 0
    records_dropped: int = 0


class Stm32Listener:
    """Consume byte chunks, decode frames, and keep a bounded record.

    No I/O: it only processes the bytes handed to :meth:`feed`. Buffering is
    bounded twice — the parser caps its internal buffer, and the recorded raw
    chunks / frames are capped at ``max_records`` (oldest are dropped).
    """

    def __init__(
        self,
        *,
        max_buffer_bytes: int = 4096,
        max_records: int = DEFAULT_MAX_RECORDS,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if max_records <= 0:
            raise ValueError("max_records must be >= 1")
        self._clock = clock if clock is not None else time.monotonic
        self._decoder = FrameDecoder(max_buffer_bytes=max_buffer_bytes)
        self._max_records = max_records
        self._raw: deque[RawRecord] = deque(maxlen=max_records)
        self._frames: deque[FrameRecord] = deque(maxlen=max_records)
        self._functions_seen: Counter[int] = Counter()
        self._counters = ListenerStats()
        self._frame_index = 0

    # -- ingestion ----------------------------------------------------------- #

    def feed(
        self, data: bytes | bytearray, *, timestamp_s: float | None = None
    ) -> list[FrameRecord]:
        """Consume *data*, record it, and return any frames that completed."""
        if not data:
            return []

        timestamp = self._clock() if timestamp_s is None else timestamp_s
        self._counters.chunks_in += 1
        self._counters.bytes_in += len(data)
        if len(self._raw) == self._raw.maxlen:
            self._counters.records_dropped += 1
        self._raw.append(
            RawRecord(index=self._counters.chunks_in, timestamp_s=timestamp, data=bytes(data))
        )

        records: list[FrameRecord] = []
        for frame in self._decoder.feed(data):
            decoded = decode_payload(frame)
            self._functions_seen[frame.function] += 1
            if decoded is None:
                self._counters.unrecognized_frames += 1
            if len(self._frames) == self._frames.maxlen:
                self._counters.records_dropped += 1
            self._frame_index += 1
            record = FrameRecord(
                index=self._frame_index,
                timestamp_s=timestamp,
                function=frame.function,
                function_name=function_name(frame.function),
                payload=frame.payload,
                decoded=decoded,
            )
            self._frames.append(record)
            records.append(record)
        return records

    # -- inspection ---------------------------------------------------------- #

    @property
    def pending(self) -> bytes:
        """Bytes buffered by the parser but not yet part of a complete frame."""
        return self._decoder.pending

    def records(self) -> tuple[FrameRecord, ...]:
        return tuple(self._frames)

    def raw_records(self) -> tuple[RawRecord, ...]:
        return tuple(self._raw)

    def stats(self) -> ListenerStats:
        """A snapshot combining listener counters and parser counters."""
        parser = self._decoder.stats
        return ListenerStats(
            chunks_in=self._counters.chunks_in,
            bytes_in=self._counters.bytes_in,
            frames_ok=parser.frames_ok,
            crc_errors=parser.crc_errors,
            length_errors=parser.length_errors,
            resyncs=parser.resyncs,
            overflows=parser.overflows,
            unrecognized_frames=self._counters.unrecognized_frames,
            records_dropped=self._counters.records_dropped,
        )

    def summary(self) -> dict:
        """A plain dict for offline analysis / logging."""
        stats = self.stats()
        return {
            "chunks_in": stats.chunks_in,
            "bytes_in": stats.bytes_in,
            "frames_ok": stats.frames_ok,
            "crc_errors": stats.crc_errors,
            "length_errors": stats.length_errors,
            "resyncs": stats.resyncs,
            "overflows": stats.overflows,
            "unrecognized_frames": stats.unrecognized_frames,
            "records_dropped": stats.records_dropped,
            "functions_seen": {
                function_name(func): count
                for func, count in sorted(self._functions_seen.items())
            },
        }


# --------------------------------------------------------------------------- #
# Replay mode (no hardware)
# --------------------------------------------------------------------------- #

def replay_bytes(
    data: bytes | bytearray,
    *,
    chunk_size: int = 0,
    listener: Stm32Listener | None = None,
) -> Stm32Listener:
    """Feed *data* through a listener. ``chunk_size > 0`` feeds it in pieces.

    This is a pure, in-memory operation — it never opens or writes a port.
    """
    listener = listener if listener is not None else Stm32Listener()
    if chunk_size and chunk_size > 0:
        for start in range(0, len(data), chunk_size):
            listener.feed(data[start : start + chunk_size])
    else:
        listener.feed(data)
    return listener


def replay_file(
    path: str | Path,
    *,
    chunk_size: int = 0,
    listener: Stm32Listener | None = None,
) -> Stm32Listener:
    """Replay the bytes of a local file (e.g. a captured stream). No serial I/O."""
    data = Path(path).read_bytes()
    return replay_bytes(data, chunk_size=chunk_size, listener=listener)


# --------------------------------------------------------------------------- #
# Serial transport — deliberately NOT implemented (no accidental hardware path)
# --------------------------------------------------------------------------- #

class SerialTransportDisabled(RuntimeError):
    """Raised when a serial transport is requested but not enabled."""


class SerialTransport:
    """Placeholder for a FUTURE, supervised, read-only serial transport.

    It is intentionally inert: :meth:`open` always raises, so there is no code
    path that can open ``/dev/ttyACM0`` by accident. A real transport must only be
    added after owner approval, with the robot secured and the E-stop ready, and
    it must remember that setting ``dtr``/``rts`` false before ``open()`` reduces
    — but does not guarantee against — an STM32 reset.
    """

    def __init__(self, device: str, *, baud: int = 1_000_000) -> None:
        self.device = device
        self.baud = baud

    @staticmethod
    def available() -> bool:
        """Always False: no serial transport exists in this phase."""
        return False

    def open(self) -> None:
        raise SerialTransportDisabled(
            "serial transport is intentionally not implemented in this phase; "
            "use replay mode (replay_bytes/replay_file). Opening /dev/ttyACM0 may "
            "reset the STM32 board."
        )

    def read(self, size: int = 1) -> bytes:  # pragma: no cover - never reached
        raise SerialTransportDisabled("serial transport is disabled")
