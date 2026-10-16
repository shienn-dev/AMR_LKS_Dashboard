"""Arm adapter tests. No hardware: nothing is ever transmitted."""

from __future__ import annotations

from amr_core.robot.arm import OfflineArmAdapter, SerialArmAdapter
from amr_core.robot.interfaces import ArmCommand, ConnectionState


def test_offline_arm_validates_and_never_transmits() -> None:
    adapter = OfflineArmAdapter()
    outcome = adapter.submit(ArmCommand(positions=(0, 1000, 500), duration_s=2.0))
    assert outcome.accepted is True
    assert outcome.transmitted is False
    assert adapter.last_command() == ArmCommand(positions=(0, 1000, 500), duration_s=2.0)


def test_offline_arm_rejects_bad_input() -> None:
    adapter = OfflineArmAdapter()
    outcome = adapter.submit(ArmCommand(positions=(1.5,), duration_s=1.0))  # type: ignore[arg-type]
    assert outcome.accepted is False
    assert outcome.transmitted is False
    assert adapter.last_command() is None


def test_offline_arm_stop_records_empty_and_never_transmits() -> None:
    adapter = OfflineArmAdapter()
    adapter.submit(ArmCommand(positions=(500,), duration_s=1.0))
    outcome = adapter.stop()
    assert outcome.transmitted is False
    assert adapter.last_command() == ArmCommand()


def test_offline_arm_default_state_disabled() -> None:
    assert OfflineArmAdapter().state() is ConnectionState.DISABLED


def test_serial_arm_refuses_to_transmit() -> None:
    adapter = SerialArmAdapter()
    outcome = adapter.submit(ArmCommand(positions=(500,), duration_s=1.0))
    assert outcome.accepted is False
    assert outcome.transmitted is False
    assert adapter.state() is ConnectionState.UNAVAILABLE
