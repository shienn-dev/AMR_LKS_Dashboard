"""Chassis control panel tests: the panel must render and never move the robot.

These are not browser tests: they call the panel builder directly, which is
enough to catch a broken render (a missing attribute, a bad NiceGUI call) and
to prove that rendering the panel does not transmit anything.
"""

from __future__ import annotations

from amr_core.robot.interfaces import ConnectionState
from amr_dashboard import chassis_panel, robot_runtime


def test_offline_panel_renders_and_stays_silent() -> None:
    adapters = robot_runtime.build_adapters(live=False)
    chassis_panel.chassis_control_panel(adapters)
    assert adapters.chassis.state() is ConnectionState.DISABLED
    assert adapters.chassis.last_command() is None
    assert adapters.guard is None


def test_live_panel_renders_without_opening_the_port() -> None:
    """Rendering must not open the port: only the operator's start-up does."""
    adapters = robot_runtime.build_adapters(live=True, port="/dev/does-not-exist")
    chassis_panel.chassis_control_panel(adapters)
    assert adapters.guard is not None
    assert adapters.chassis.state() is ConnectionState.DISABLED
    assert adapters.chassis.last_command() is None


def test_the_hold_command_maps_the_axes_to_the_body_frame() -> None:
    command = chassis_panel._command_for((0.0, 1.0, 0.0), 0.1)
    assert command.linear_x == 0.0
    assert command.linear_y == 0.1
    assert command.angular_z == 0.0
    turn = chassis_panel._command_for((0.0, 0.0, -1.0), 0.1)
    assert turn.angular_z == -0.1
