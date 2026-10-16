"""Arm adapters.

The Lander arm is driven by bus servos on the STM32 controller upstream
(``ros_robot_controller/bus_servo/set_position``). That ROS interface is absent
here (no ROS 2) and the direct serial protocol is unverified, so this phase ships
only an offline adapter: it validates input and records the request but never
moves a servo. :class:`SerialArmAdapter` refuses to transmit.
"""

from __future__ import annotations

from amr_core.robot.interfaces import ArmCommand, CommandOutcome, ConnectionState
from amr_core.robot.safety import validate_arm_command


class OfflineArmAdapter:
    """Safe default arm adapter. Validates + records; transmits nothing."""

    name = "offline"

    def __init__(self, state: ConnectionState = ConnectionState.DISABLED) -> None:
        self._state = state
        self._last: ArmCommand | None = None

    def state(self) -> ConnectionState:
        return self._state

    def set_state(self, state: ConnectionState) -> None:
        self._state = state

    def last_command(self) -> ArmCommand | None:
        return self._last

    def submit(self, command: ArmCommand) -> CommandOutcome:
        validated, reason = validate_arm_command(command)
        if validated is None:
            return CommandOutcome(accepted=False, transmitted=False, reason=reason)
        self._last = validated
        return CommandOutcome(
            accepted=True,
            transmitted=False,
            reason=(
                "validated; no verified arm transport in this phase "
                "(nothing transmitted)"
            ),
        )

    def stop(self) -> CommandOutcome:
        self._last = ArmCommand()
        return CommandOutcome(
            accepted=True,
            transmitted=False,
            reason="stop recorded; no verified arm transport (nothing transmitted)",
        )


class SerialArmAdapter:
    """Placeholder for a future verified arm transport — refuses to transmit."""

    name = "serial-unverified"

    def __init__(self, port: str = "/dev/ttyACM0") -> None:
        self.port = port
        self._last: ArmCommand | None = None

    def state(self) -> ConnectionState:
        return ConnectionState.UNAVAILABLE

    def last_command(self) -> ArmCommand | None:
        return self._last

    def submit(self, command: ArmCommand) -> CommandOutcome:
        return CommandOutcome(
            accepted=False,
            transmitted=False,
            reason=(
                "serial arm transport is not implemented: the bus-servo protocol is "
                "unverified on this board (see docs/robot_integration.md)"
            ),
        )

    def stop(self) -> CommandOutcome:
        return self.submit(ArmCommand())
