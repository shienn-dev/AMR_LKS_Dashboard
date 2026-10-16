"""Tests for LiDAR configuration (port changeable without editing code)."""

from __future__ import annotations

from amr_core.lidar.config import (
    DEFAULT_BAUD,
    DEFAULT_PORT,
    ENV_BAUD,
    ENV_ENABLED,
    ENV_PORT,
    LidarConfig,
)


def test_defaults_match_device_facts() -> None:
    config = LidarConfig()
    assert config.port == DEFAULT_PORT == "/dev/ttyUSB0"
    assert config.baud == DEFAULT_BAUD == 230400
    assert config.enabled is True


def test_from_env_reads_overrides() -> None:
    config = LidarConfig.from_env(
        {ENV_PORT: "/dev/ttyUSB1", ENV_BAUD: "115200", ENV_ENABLED: "false"}
    )
    assert config.port == "/dev/ttyUSB1"
    assert config.baud == 115200
    assert config.enabled is False


def test_from_env_ignores_malformed_baud() -> None:
    config = LidarConfig.from_env({ENV_BAUD: "not-a-number"})
    assert config.baud == DEFAULT_BAUD


def test_from_env_empty_uses_defaults() -> None:
    config = LidarConfig.from_env({})
    assert config.port == DEFAULT_PORT
    assert config.baud == DEFAULT_BAUD
    assert config.enabled is True


def test_with_overrides_returns_a_copy() -> None:
    base = LidarConfig()
    changed = base.with_overrides(port="/dev/ttyUSB2", enabled=False)
    assert changed is not base
    assert changed.port == "/dev/ttyUSB2"
    assert changed.enabled is False
    # The original is untouched.
    assert base.port == DEFAULT_PORT
    assert base.enabled is True
