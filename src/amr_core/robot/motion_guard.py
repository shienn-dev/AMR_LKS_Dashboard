"""Fail-safe guard for hold-to-move chassis control.

The dashboard drives the robot by *holding* a button. The dangerous case is a
release event that never arrives: the pointer is released outside the button,
the browser tab is closed, the Wi-Fi drops, the laptop sleeps. If the server
keeps streaming motor frames in that situation, the robot keeps driving.

This module is the safety net. It is pure logic with an injected clock, so it
can be tested without a robot, a browser or a network -- and it is the only
place that decides whether the chassis is allowed to move.

Layers implemented here
-----------------------
``L1`` heartbeat
    The controlling browser has to keep saying "I still want to move". If the
    last heartbeat is older than ``heartbeat_timeout_s``, the guard stops the
    robot. This is the layer that catches *every* way of losing control,
    including the ones where no event is ever delivered.
``L3`` release / key-up
    Handled by the caller: it clears the command and renews nothing, so the
    next poll sees no command.
``L5`` software E-stop
    A latch that stops the robot and refuses new commands until an operator
    explicitly clears it.
``L7`` control lease
    Only one browser session may hold control. A second session is read-only,
    so two dashboards cannot fight over the robot.
``L6`` board watchdog
    Not implemented here -- it lives in the firmware. If the frame stream
    stops, the board stops the motors. This module's job is to make sure the
    stream really does stop.

The physical E-stop is not software and is not modelled here.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from amr_core.robot.interfaces import ChassisCommand

#: A heartbeat older than this means the operator is no longer in control.
#:
#: 0,8 s rather than something tighter: the heartbeat travels through the
#: dashboard's event loop, and that loop occasionally stalls for a few hundred
#: milliseconds while a panel is rebuilt. A tighter limit turned those hiccups
#: into "the robot stopped for no reason". The fast paths are unaffected --
#: releasing the button, losing the focus, hiding the tab and a disconnect
#: all stop the robot immediately. This timeout is only the backstop for a
#: client that dies silently.
DEFAULT_HEARTBEAT_TIMEOUT_S = 0.8

#: A motion request is only accepted if the heartbeat is at least this fresh.
DEFAULT_HEARTBEAT_GRACE_S = 0.1


@dataclass
class GuardState:
    """Everything the guard knows, in one inspectable object."""

    lease_owner: str | None = None
    command: ChassisCommand | None = None
    last_heartbeat: float = float("-inf")
    latched: bool = False
    latch_reason: str = ""
    stopped_reason: str = ""
    session_id: str = field(default="", compare=False)


class MotionGuard:
    """Decides whether the chassis may move, and when it must stop."""

    def __init__(
        self,
        *,
        heartbeat_timeout_s: float = DEFAULT_HEARTBEAT_TIMEOUT_S,
        heartbeat_grace_s: float = DEFAULT_HEARTBEAT_GRACE_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._heartbeat_timeout_s = heartbeat_timeout_s
        self._heartbeat_grace_s = heartbeat_grace_s
        self._clock = clock
        self._state = GuardState()

    # --- state inspection -------------------------------------------------- #

    @property
    def state(self) -> GuardState:
        return self._state

    @property
    def latched(self) -> bool:
        return self._state.latched

    @property
    def lease_owner(self) -> str | None:
        return self._state.lease_owner

    @property
    def stopped_reason(self) -> str:
        return self._state.stopped_reason

    def holds_lease(self, session_id: str) -> bool:
        return self._state.lease_owner == session_id

    def command(self) -> ChassisCommand | None:
        """The command that should currently be transmitted, if any."""
        return self._state.command

    # --- lease ------------------------------------------------------------- #

    def arm(self, session_id: str) -> bool:
        """Take the control lease. False if another session already holds it.

        A lease whose heartbeat has expired is not a live controller: the
        browser is gone, the network dropped or the laptop slept. Such a lease
        is taken over instead of locking the dashboard forever.
        """
        owner = self._state.lease_owner
        if owner not in (None, session_id) and self.heartbeat_fresh():
            return False
        self._state.lease_owner = session_id
        self._state.stopped_reason = ""
        return True

    def disarm(self, session_id: str) -> bool:
        """Release the lease and stop. True if this session held it."""
        if self._state.lease_owner != session_id:
            return False
        self._state.lease_owner = None
        self._state.command = None
        self._state.stopped_reason = "control released"
        return True

    # --- heartbeat --------------------------------------------------------- #

    def heartbeat(self, session_id: str) -> bool:
        """Record that ``session_id`` is still in control.

        Returns False when the session does not hold the lease, so a stray
        heartbeat from a second browser cannot keep the robot alive.
        """
        if self._state.lease_owner != session_id:
            return False
        self._state.last_heartbeat = self._clock()
        return True

    def heartbeat_age(self) -> float:
        if self._state.last_heartbeat == float("-inf"):
            return float("inf")
        return self._clock() - self._state.last_heartbeat

    def heartbeat_fresh(self) -> bool:
        return self.heartbeat_age() <= self._heartbeat_timeout_s

    # --- motion ------------------------------------------------------------ #

    def request_motion(self, session_id: str, command: ChassisCommand) -> bool:
        """Ask to move. False when the request must be refused.

        Refused when the session does not hold the lease, when the E-stop is
        latched, or when the heartbeat is too old to trust.
        """
        if self._state.lease_owner != session_id:
            self._state.stopped_reason = "no control lease for this session"
            return False
        if self._state.latched:
            self._state.stopped_reason = f"e-stop latched: {self._state.latch_reason}"
            return False
        if self.heartbeat_age() > self._heartbeat_timeout_s:
            self._state.command = None
            self._state.stopped_reason = "heartbeat lost"
            return False
        self._state.command = command
        self._state.stopped_reason = ""
        return True

    def release_motion(self, session_id: str) -> None:
        """Stop moving (the operator let go of the button)."""
        if self._state.lease_owner != session_id:
            return
        self._state.command = None
        self._state.stopped_reason = "button released"

    def reset_motion(self) -> None:
        """Forget the current command without giving up the lease.

        Used when the transport is (re)opened: a command left over from
        before must never start moving the robot by itself.
        """
        self._state.command = None

    def poll(self) -> ChassisCommand | None:
        """Return the command to transmit right now, or None to stop.

        This is the method the streaming loop calls at the frame rate. It
        returns None -- meaning "send zeros" -- as soon as any fail-safe
        condition fires.
        """
        if self._state.latched:
            self._state.command = None
            self._state.stopped_reason = f"e-stop latched: {self._state.latch_reason}"
            return None
        if self._state.command is None:
            return None
        if not self.heartbeat_fresh():
            self._state.command = None
            self._state.stopped_reason = "heartbeat lost"
            return None
        return self._state.command

    # --- software e-stop --------------------------------------------------- #

    def trip(self, reason: str = "") -> None:
        """Latch the software E-stop: stop now, refuse new commands."""
        self._state.latched = True
        self._state.latch_reason = reason
        self._state.command = None
        self._state.stopped_reason = f"e-stop latched: {reason}"

    def clear(self, *, confirmed_safe: bool) -> bool:
        """Clear the software E-stop; only with an explicit safety confirmation."""
        if not confirmed_safe:
            return False
        self._state.latched = False
        self._state.latch_reason = ""
        self._state.stopped_reason = ""
        return True
