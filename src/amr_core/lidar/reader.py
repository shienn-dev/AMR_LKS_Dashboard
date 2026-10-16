"""Background LiDAR serial reader.

The reader owns one background thread that opens the serial port, streams
bytes, resynchronises on the packet header, validates the CRC, and folds valid
packets into a :class:`~amr_core.lidar.scan.ScanAccumulator`. The UI thread only
ever calls :meth:`LidarReader.snapshot` / :meth:`LidarReader.stats`, so serial
I/O never blocks rendering.

Robustness (per the task brief):

- truncated / partial packets: the parser keeps a byte buffer and only decodes
  a packet once 47 bytes are available;
- invalid header: the buffer is resynchronised to the next ``0x54 0x2C``;
- CRC failure: counted and the buffer advances one byte to re-search;
- read timeout: handled without error (normal when the stream is briefly idle);
- port unavailable / device disconnected: caught, reported, and retried with a
  backoff — the thread never dies silently;
- ``pyserial`` missing: the reader reports ``UNAVAILABLE`` instead of crashing.

``pyserial`` is imported lazily, so importing this module (and the dashboard)
works even when it is not installed.
"""

from __future__ import annotations

import importlib.util
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from amr_core.lidar.config import LidarConfig
from amr_core.lidar.protocol import HEADER, PACKET_LEN, LidarProtocolError, decode_packet
from amr_core.lidar.scan import ScanAccumulator, ScanSnapshot

_READ_CHUNK = 256
_RATE_WINDOW = 64
_MAX_NOTES = 50


class LidarStatus(str, Enum):
    """Lifecycle status of the reader."""

    STOPPED = "STOPPED"
    CONNECTING = "CONNECTING"
    RUNNING = "RUNNING"
    ERROR = "ERROR"
    UNAVAILABLE = "UNAVAILABLE"  # pyserial is not installed


class SerialLike(Protocol):
    """The small part of the pyserial API this reader uses (for test doubles)."""

    def read(self, size: int = ...) -> bytes: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class LidarStats:
    """An immutable snapshot of the reader's counters and status."""

    status: LidarStatus
    port: str
    baud: int
    packets_ok: int
    crc_failures: int
    sync_failures: int
    bytes_read: int
    reconnects: int
    packets_per_s: float
    last_packet_s: float | None
    last_error: str

    @property
    def connected(self) -> bool:
        return self.status is LidarStatus.RUNNING


class LidarReader:
    """Owns the serial port and a background parsing thread.

    A single instance must own a given port; the application keeps one reader
    alive for the process (see ``amr_dashboard.lidar_runtime``) so the same port
    is never opened twice.
    """

    def __init__(
        self,
        config: LidarConfig | None = None,
        *,
        serial_factory: Callable[[str, int], SerialLike] | None = None,
        accumulator: ScanAccumulator | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config or LidarConfig()
        self._serial_factory = serial_factory
        self._accumulator = accumulator or ScanAccumulator(buckets=self.config.buckets)
        self._clock = clock
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._status = LidarStatus.STOPPED
        self._packets_ok = 0
        self._crc_failures = 0
        self._sync_failures = 0
        self._bytes_read = 0
        self._reconnects = 0
        self._last_error = ""
        self._last_packet_s: float | None = None
        self._packet_times: deque[float] = deque(maxlen=_RATE_WINDOW)
        self._notes: deque[str] = deque(maxlen=_MAX_NOTES)

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> bool:
        """Start reading in the background. Returns False if unavailable."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return True
        if not self._serial_available():
            self._note("pyserial is not installed; LiDAR reading unavailable")
            self._set_status(LidarStatus.UNAVAILABLE, "pyserial is not installed")
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="lidar-reader", daemon=True)
        self._thread.start()
        return True

    def stop(self, timeout: float = 2.0) -> None:
        """Signal the thread to stop and join it. Safe to call repeatedly."""
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout)
        self._thread = None
        self._set_status(LidarStatus.STOPPED)

    @property
    def is_alive(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    # -- reads (thread-safe, non-blocking) -----------------------------------

    def snapshot(self) -> ScanSnapshot:
        """Return a consistent, immutable copy of the accumulated scan."""
        return self._accumulator.snapshot()

    def stats(self) -> LidarStats:
        """Return a copy of the current counters (never a live reference)."""
        with self._lock:
            times = list(self._packet_times)
            rate = 0.0
            if len(times) >= 2 and times[-1] > times[0]:
                rate = (len(times) - 1) / (times[-1] - times[0])
            return LidarStats(
                status=self._status,
                port=self.config.port,
                baud=self.config.baud,
                packets_ok=self._packets_ok,
                crc_failures=self._crc_failures,
                sync_failures=self._sync_failures,
                bytes_read=self._bytes_read,
                reconnects=self._reconnects,
                packets_per_s=rate,
                last_packet_s=self._last_packet_s,
                last_error=self._last_error,
            )

    def recent_notes(self) -> list[str]:
        """Recent status/error messages, oldest first (for the diagnostics UI)."""
        with self._lock:
            return list(self._notes)

    # -- internals -----------------------------------------------------------

    def _serial_available(self) -> bool:
        if self._serial_factory is not None:
            return True
        return importlib.util.find_spec("serial") is not None

    def _open_serial(self) -> SerialLike:
        if self._serial_factory is not None:
            return self._serial_factory(self.config.port, self.config.baud)
        import serial  # imported lazily so pyserial stays optional

        return serial.Serial(
            port=self.config.port,
            baudrate=self.config.baud,
            timeout=self.config.read_timeout_s,
        )

    def _run(self) -> None:
        while not self._stop.is_set():
            self._set_status(LidarStatus.CONNECTING)
            try:
                ser = self._open_serial()
            except OSError as exc:
                self._on_connection_error(exc)
                if self._stop.wait(self.config.reconnect_delay_s):
                    break
                continue

            self._note(f"connected to {self.config.port} @ {self.config.baud} baud")
            self._set_status(LidarStatus.RUNNING, clear_error=True)
            try:
                self._read_loop(ser)
            except OSError as exc:
                self._on_connection_error(exc)
                if self._stop.wait(self.config.reconnect_delay_s):
                    break
            finally:
                self._close_quietly(ser)
        self._set_status(LidarStatus.STOPPED)

    def _read_loop(self, ser: SerialLike) -> None:
        buffer = bytearray()
        last_data_s = self._clock()
        while not self._stop.is_set():
            chunk = ser.read(_READ_CHUNK)  # blocks up to read_timeout_s
            if chunk:
                last_data_s = self._clock()
                self._record_bytes(len(chunk))
                buffer.extend(chunk)
                self._consume(buffer)
                if len(buffer) > self.config.max_buffer_bytes:
                    # Never keep more than one packet's worth of unparsed data.
                    del buffer[: len(buffer) - PACKET_LEN]
            else:
                # A timeout with no bytes is normal, but a working LiDAR streams
                # continuously, so a long silence means the device is gone.
                if self._clock() - last_data_s > self.config.idle_timeout_s:
                    raise OSError("no data from LiDAR (idle timeout)")
                self._stop.wait(0.01)  # avoid busy-spinning on empty reads

    def _consume(self, buffer: bytearray) -> None:
        """Extract every complete, valid packet currently in *buffer*."""
        while True:
            pos = buffer.find(HEADER)
            if pos < 0:
                if len(buffer) > 1:
                    del buffer[:-1]  # keep a byte in case it is a partial header
                return
            if pos:
                del buffer[:pos]
            if len(buffer) < PACKET_LEN:
                return
            try:
                packet = decode_packet(bytes(buffer[:PACKET_LEN]))
            except LidarProtocolError as exc:
                if exc.kind == "crc":
                    self._bump_crc()
                else:
                    self._bump_sync()
                del buffer[0]  # advance one byte and re-search for the header
                continue
            self._accumulator.add_packet(packet)
            self._record_packet()
            del buffer[:PACKET_LEN]

    def _close_quietly(self, ser: SerialLike) -> None:
        try:
            ser.close()
        except Exception:  # noqa: BLE001 - closing must never crash the thread
            pass

    # -- counter helpers (all guarded by the lock) ---------------------------

    def _set_status(
        self,
        status: LidarStatus,
        last_error: str = "",
        *,
        clear_error: bool = False,
    ) -> None:
        with self._lock:
            self._status = status
            if clear_error:
                self._last_error = ""
            elif last_error:
                self._last_error = last_error

    def _on_connection_error(self, exc: BaseException) -> None:
        with self._lock:
            self._reconnects += 1
            self._last_error = f"{type(exc).__name__}: {exc}"
            self._status = LidarStatus.ERROR
            self._notes.append(f"{_timestamp()} serial error: {self._last_error}")

    def _record_bytes(self, count: int) -> None:
        with self._lock:
            self._bytes_read += count

    def _bump_crc(self) -> None:
        with self._lock:
            self._crc_failures += 1

    def _bump_sync(self) -> None:
        with self._lock:
            self._sync_failures += 1

    def _record_packet(self) -> None:
        now = self._clock()
        with self._lock:
            self._packets_ok += 1
            self._last_packet_s = now
            self._packet_times.append(now)

    def _note(self, message: str) -> None:
        with self._lock:
            self._notes.append(f"{_timestamp()} {message}")


def _timestamp() -> str:
    return time.strftime("%H:%M:%S")
