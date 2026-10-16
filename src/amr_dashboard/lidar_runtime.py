"""Process-wide LiDAR reader lifecycle for the dashboard.

There must be exactly one reader per serial port, shared by every browser
session, so this module keeps a single module-level :class:`LidarReader`. Pages
never create their own reader; they call :func:`get_lidar_reader` and read
snapshots from it.

The reader is **not** started on import — only :func:`start_lidar` starts it,
which the dashboard launcher calls. This keeps importing the app (and the test
suite) free of any serial side effect.
"""

from __future__ import annotations

from amr_core.lidar.config import LidarConfig
from amr_core.lidar.reader import LidarReader

_reader: LidarReader | None = None
_pending_config: LidarConfig | None = None


def configure(config: LidarConfig) -> None:
    """Set the config used when the reader is (re)created.

    Must be called before :func:`get_lidar_reader`; if a reader already exists
    it is stopped and discarded so the new config takes effect.
    """
    global _pending_config
    _pending_config = config
    if _reader is not None:
        _reader.stop()


def get_lidar_reader() -> LidarReader:
    """Return the shared reader, creating it (but not starting it) on first use."""
    global _reader
    if _reader is None:
        config = _pending_config if _pending_config is not None else LidarConfig.from_env()
        _reader = LidarReader(config)
    return _reader


def start_lidar() -> bool:
    """Start the shared reader if LiDAR is enabled. Returns whether it started."""
    reader = get_lidar_reader()
    if not reader.config.enabled:
        return False
    return reader.start()


def stop_lidar() -> None:
    """Stop the shared reader if it exists."""
    if _reader is not None:
        _reader.stop()


def reset_lidar_runtime() -> None:
    """Stop and drop the shared reader (test helper)."""
    global _reader, _pending_config
    if _reader is not None:
        _reader.stop()
    _reader = None
    _pending_config = None
