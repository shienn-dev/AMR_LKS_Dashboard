"""Runtime configuration for the LiDAR reader.

The serial port must be changeable **without editing code**, so configuration
comes from environment variables (and, at the CLI, command-line flags that
override them). This module has no third-party dependency.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, replace

# Environment variable names. The defaults match the device facts established
# for this robot (see the task brief and ~/lidar-test/test_stl19p.py).
ENV_PORT = "AMR_LIDAR_PORT"
ENV_BAUD = "AMR_LIDAR_BAUD"
ENV_ENABLED = "AMR_LIDAR_ENABLED"

DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUD = 230400

_TRUTHY = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class LidarConfig:
    """Immutable LiDAR reader configuration."""

    port: str = DEFAULT_PORT
    baud: int = DEFAULT_BAUD
    enabled: bool = True
    # Serial read timeout. Small so the reader thread stays responsive to stop
    # requests without busy-spinning (a read blocks up to this long).
    read_timeout_s: float = 0.1
    # If no bytes arrive for this long, treat the device as disconnected and
    # reconnect (a working LiDAR streams continuously).
    idle_timeout_s: float = 3.0
    # Delay between reconnect attempts.
    reconnect_delay_s: float = 1.0
    # Hard cap on the parse buffer; protects against runaway memory if the
    # stream never contains a valid header.
    max_buffer_bytes: int = 8192
    # Angular resolution of the accumulated scan.
    buckets: int = 360

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> LidarConfig:
        """Build a config from environment variables (with defaults)."""
        env = os.environ if env is None else env
        config = cls()
        port = env.get(ENV_PORT)
        if port:
            config = replace(config, port=port)
        baud = env.get(ENV_BAUD)
        if baud:
            try:
                config = replace(config, baud=int(baud))
            except ValueError:
                pass  # keep the default on a malformed value
        enabled = env.get(ENV_ENABLED)
        if enabled is not None:
            config = replace(config, enabled=enabled.strip().lower() in _TRUTHY)
        return config

    def with_overrides(
        self,
        *,
        port: str | None = None,
        baud: int | None = None,
        enabled: bool | None = None,
    ) -> LidarConfig:
        """Return a copy with the given fields replaced (None = keep current)."""
        return replace(
            self,
            port=self.port if port is None else port,
            baud=self.baud if baud is None else baud,
            enabled=self.enabled if enabled is None else enabled,
        )
