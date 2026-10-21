"""Chassis adapter tests.

No hardware: the offline adapter validates but transmits nothing, and the live
serial adapter refuses to transmit until its port is actually opened.
"""

from __future__ import annotations

import math

from amr_core.robot.chassis import OfflineChassisAdapter
from amr_core.robot.interfaces import ChassisCommand, ConnectionState
from amr_core.robot.safety import SpeedLimits
from amr_core.robot.serial_chassis import SerialChassisAdapter


def test_offline_adapter_validates_clamps_and_never_transmits() -> None:
    adapter = OfflineChassisAdapter(limits=SpeedLimits(max_linear_x=0.3))
    outcome = adapter.submit(ChassisCommand(10.0, 0.0, 0.0))
    assert outcome.accepted is True
    assert outcome.transmitted is False
    assert adapter.last_command() == ChassisCommand(0.3, 0.0, 0.0)


def test_offline_adapter_rejects_non_finite() -> None:
    adapter = OfflineChassisAdapter()
    outcome = adapter.submit(ChassisCommand(math.nan, 0.0, 0.0))
    assert outcome.accepted is False
    assert outcome.transmitted is False
    assert adapter.last_command() is None


def test_offline_adapter_stop_records_zero_and_never_transmits() -> None:
    adapter = OfflineChassisAdapter()
    adapter.submit(ChassisCommand(0.1, 0.0, 0.0))
    outcome = adapter.stop()
    assert outcome.transmitted is False
    assert adapter.last_command() == ChassisCommand()


def test_offline_adapter_default_state_is_disabled() -> None:
    assert OfflineChassisAdapter().state() is ConnectionState.DISABLED


def test_connection_loss_is_reported_not_hidden() -> None:
    adapter = OfflineChassisAdapter(state=ConnectionState.CONNECTED)
    adapter.set_state(ConnectionState.DISCONNECTED)
    assert adapter.state() is ConnectionState.DISCONNECTED


def test_serial_adapter_refuses_to_transmit_before_the_port_is_open() -> None:
    adapter = SerialChassisAdapter()
    outcome = adapter.submit(ChassisCommand(0.1, 0.0, 0.0))
    assert outcome.accepted is True
    assert outcome.transmitted is False
    assert adapter.state() is ConnectionState.DISABLED
    assert adapter.last_command() == ChassisCommand(0.1, 0.0, 0.0)
