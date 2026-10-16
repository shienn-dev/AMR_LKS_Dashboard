"""Chassis adapters.

The dashboard talks to the chassis only through the ``ChassisAdapter`` protocol.
In this phase the only usable adapter is :class:`OfflineChassisAdapter`: it
validates and records commands but transmits nothing.
:class:`SerialChassisAdapter` is a deliberate placeholder that refuses to
transmit until the STM32 serial protocol is verified on the school's board.
"""

from __future__ import annotations

from amr_core.robot.interfaces import ChassisCommand, CommandOutcome, ConnectionState
from amr_core.robot.safety import SpeedLimits, validate_chassis_command


class OfflineChassisAdapter:
    """Safe default. Validates + clamps + records; transmits nothing."""

    name = "offline"

    def __init__(
        self,
        limits: SpeedLimits | None = None,
        state: ConnectionState = ConnectionState.DISABLED,
    ) -> None:
        self.limits = limits if limits is not None else SpeedLimits()
        self._state = state
        self._last: ChassisCommand | None = None

    def state(self) -> ConnectionState:
        return self._state

    def set_state(self, state: ConnectionState) -> None:
        """Test/UI helper: simulate a link change (e.g. a dropped connection)."""
        self._state = state

    def last_command(self) -> ChassisCommand | None:
        return self._last

    def submit(self, command: ChassisCommand) -> CommandOutcome:
        clamped, reason = validate_chassis_command(command, self.limits)
        if clamped is None:
            return CommandOutcome(accepted=False, transmitted=False, reason=reason)
        self._last = clamped
        return CommandOutcome(
            accepted=True,
            transmitted=False,
            reason=(
                "validated; no verified chassis transport in this phase "
                "(nothing transmitted)"
            ),
        )

    def stop(self) -> CommandOutcome:
        self._last = ChassisCommand()
        return CommandOutcome(
            accepted=True,
            transmitted=False,
            reason="stop recorded; no verified chassis transport (nothing transmitted)",
        )


class SerialChassisAdapter:
    """Placeholder for a future verified serial transport — refuses to transmit."""

    name = "serial-unverified"

    def __init__(self, port: str = "/dev/ttyACM0", limits: SpeedLimits | None = None) -> None:
        self.port = port
        self.limits = limits if limits is not None else SpeedLimits()
        self._last: ChassisCommand | None = None

    def state(self) -> ConnectionState:
        return ConnectionState.UNAVAILABLE

    def last_command(self) -> ChassisCommand | None:
        return self._last

    def submit(self, command: ChassisCommand) -> CommandOutcome:
        return CommandOutcome(
            accepted=False,
            transmitted=False,
            reason=(
                "serial chassis transport is not implemented: the STM32 protocol is "
                "unverified on this board (see docs/robot_integration.md)"
            ),
        )

    def stop(self) -> CommandOutcome:
        return self.submit(ChassisCommand())
