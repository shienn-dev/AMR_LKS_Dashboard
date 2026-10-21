"""Interactive chassis control: hold a button, the robot moves.

This panel is rendered **once per page** and is never re-rendered by the
dashboard's refresh tick, because a button that is replaced while the pointer
is still down would lose the "release" event. The camera and odometry panels
stay in the refreshed region; this one does not.

How a hold works
----------------
``pointerdown`` on a direction button asks the
:class:`~amr_core.robot.motion_guard.MotionGuard` for permission to move. The
guard grants it only when the session holds the control lease, the software
E-stop is not latched, and the heartbeat is fresh. The command is then stored
in the guard, and the chassis adapter's stream thread sends it at 50 Hz until
the guard withdraws it.

Three things can withdraw it:

* the operator lets go (``pointerup`` / ``pointerleave``);
* the browser says "I am still in control" less often than every 300 ms
  (the heartbeat) -- this catches a lost release, a crashed tab, a dropped
  network or a sleeping laptop;
* the software E-stop is tripped, or another session takes the lease.

The heartbeat is a client-side timer that dispatches an event into the
server. If the page dies entirely, the heartbeat stops, the guard stops the
robot, and the board's own watchdog stops the motors if the frames stop.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from nicegui import context, ui

from amr_core.robot.interfaces import ChassisCommand, ConnectionState
from amr_core.robot.kinematics import (
    command_for_speed,
    is_above_stall_threshold,
)
from amr_dashboard.robot_runtime import RobotAdapters

#: Speed slider range, in m/s. The lower end is the stall threshold: below
#: ~0,3 rps the motors buzz without moving (sesi 2 §9.7), so offering less
#: would only confuse the operator.
MIN_SPEED_MPS = 0.06
MAX_SPEED_MPS = 0.19

#: How often the browser tells the server it is still in control.
HEARTBEAT_INTERVAL_MS = 100

_DIRECTIONS: tuple[tuple[str, str, str, tuple[float, float, float]], ...] = (
    ("Maju", "arrow_upward", "forward", (1.0, 0.0, 0.0)),
    ("Mundur", "arrow_downward", "backward", (-1.0, 0.0, 0.0)),
    ("Kiri", "arrow_back", "left", (0.0, 1.0, 0.0)),
    ("Kanan", "arrow_forward", "right", (0.0, -1.0, 0.0)),
    ("Putar L", "rotate_left", "yaw_ccw", (0.0, 0.0, 1.0)),
    ("Putar R", "rotate_right", "yaw_cw", (0.0, 0.0, -1.0)),
)


@dataclass
class _Hold:
    """Server-side state of one page's hold controls."""

    session_id: str
    active: str | None = None
    started_at: float | None = None
    speed_mps: float = MIN_SPEED_MPS


def chassis_control_panel(adapters: RobotAdapters) -> None:
    """Render the live chassis controls. Called once per page."""
    chassis = adapters.chassis
    guard = adapters.guard
    live = adapters.live and guard is not None
    limits = chassis.limits
    session_id = context.client.id
    hold = _Hold(session_id=session_id)

    with ui.card().classes("flex-1 min-w-[360px]"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("sports_esports")
            ui.label("Remote chassis control").classes("text-sm text-gray-500 uppercase")
            _state_badge(chassis.state())
            if live:
                ui.badge("LIVE").props("color=red-7 text-color=white")

        if live:
            ui.label(
                "LIVE: the robot moves while you hold a button. Keep the physical "
                "E-stop within reach. Releasing the button, losing the connection "
                "or tripping the software E-stop stops it."
            ).classes("text-xs text-red-700")
        else:
            ui.label(
                "OFFLINE: commands are validated and clamped, but NOT transmitted. "
                "Start the dashboard with --chassis-live to drive the real robot."
            ).classes("text-xs text-red-700")

        ui.label(
            f"Limits: +/-{limits.max_linear_x:.2f} m/s (x), "
            f"+/-{limits.max_linear_y:.2f} m/s (y), "
            f"+/-{limits.max_angular_z:.2f} rad/s (rot)"
        ).classes("text-xs text-gray-600")

        ui.label("Speed (m/s on the floor)").classes("text-xs text-gray-500 uppercase")
        speed = ui.slider(
            min=MIN_SPEED_MPS,
            max=MAX_SPEED_MPS,
            step=0.01,
            value=MIN_SPEED_MPS,
        ).classes("w-full")

        status = ui.label("").classes("text-xs font-mono text-gray-600")

        if not live:
            with ui.row().classes("gap-2"):
                for label, icon, _key, _axis in _DIRECTIONS:
                    ui.button(label, icon=icon).props("outline")
            ui.button("STOP", icon="stop").props("color=orange")
            ui.separator()
            _estop_controls(adapters)
            return

        _install_heartbeat(adapters, session_id, status)
        _install_hold_buttons(adapters, hold, speed, status)
        _install_stop_button(adapters, hold, status)
        # Refresh the hold timer while a button is held, so the operator can
        # read the exact hold time instead of trusting a stopwatch. The time
        # and the ruler distance together give the speed that was achieved.
        ui.timer(
            0.1,
            lambda: _refresh_status(adapters, hold, status, moving=hold.active is not None),
        )
        ui.separator()
        _estop_controls(adapters, status)


def _state_badge(state: ConnectionState) -> None:
    from amr_dashboard.robot_panel import _STATE_COLOR

    ui.badge(state.value).props(f"color={_STATE_COLOR[state]} text-color=white")


def _command_for(axis: tuple[float, float, float], speed: float) -> ChassisCommand:
    return ChassisCommand(
        linear_x=axis[0] * speed,
        linear_y=axis[1] * speed,
        angular_z=axis[2] * speed,
    )


def _install_hold_buttons(
    adapters: RobotAdapters,
    hold: _Hold,
    speed,
    status,
) -> None:
    """Build the six hold-to-move buttons."""
    guard = adapters.guard
    chassis = adapters.chassis
    assert guard is not None

    def _start(axis: tuple[float, float, float], name: str) -> None:
        if not guard.arm(hold.session_id):
            ui.notify("Control is held by another session.", color="negative", position="top")
            return
        guard.heartbeat(hold.session_id)
        target_speed = float(speed.value or MIN_SPEED_MPS)
        command = _command_for(axis, target_speed)
        # The guard decides whether the robot may move; the adapter validates
        # and clamps what actually reaches the wire.
        if not guard.request_motion(hold.session_id, command):
            ui.notify(
                guard.stopped_reason or "motion refused",
                color="negative",
                position="top",
            )
            return
        outcome = chassis.submit(command)
        if not outcome.accepted:
            guard.release_motion(hold.session_id)
            ui.notify(outcome.reason, color="negative", position="top")
            return
        hold.active = name
        hold.speed_mps = target_speed
        hold.started_at = time.monotonic()
        _refresh_status(adapters, hold, status, moving=True)

    def _stop() -> None:
        hold.active = None
        hold.started_at = None
        guard.release_motion(hold.session_id)
        _refresh_status(adapters, hold, status, moving=False)

    for label, icon, key, axis in _DIRECTIONS:
        button = ui.button(label, icon=icon)
        button.on("pointerdown", lambda e, a=axis, k=key: _start(a, k))
        button.on("pointerup", lambda e: _stop())
        button.on("pointerleave", lambda e: _stop())
        button.on("pointercancel", lambda e: _stop())


def _install_stop_button(adapters: RobotAdapters, hold: _Hold, status) -> None:
    def _stop_now() -> None:
        hold.active = None
        guard = adapters.guard
        if guard is not None:
            guard.release_motion(hold.session_id)
        adapters.chassis.stop()
        _refresh_status(adapters, hold, status, moving=False)

    ui.button("STOP", icon="stop", on_click=_stop_now).props("color=orange")


def _install_heartbeat(adapters: RobotAdapters, session_id: str, status) -> None:
    """Wire the client heartbeat and the global release net.

    Two hidden elements carry the events: one is ticked every 100 ms by the
    browser to renew the lease, the other is fired by the browser whenever a
    pointer is released anywhere on the page, or the window loses focus, or the
    tab is hidden. Both use a plain ``change`` event so no custom-event
    support is needed.
    """
    guard = adapters.guard
    assert guard is not None

    beat = ui.element("input").props("type=hidden id=guard-heartbeat")
    beat.on("change", lambda e: guard.heartbeat(session_id))

    release = ui.element("input").props("type=hidden id=guard-release")
    release.on("change", lambda e: _release_all(adapters, session_id))

    ui.add_body_html(
        """
        <script>
        (function () {
          function fire(id) {
            const el = document.getElementById(id);
            if (el) { el.value = String(Date.now()); el.dispatchEvent(new Event('change')); }
          }
          setInterval(function () { fire('guard-heartbeat'); }, HEARTBEAT_MS);
          ['pointerup', 'pointercancel'].forEach(function (name) {
            window.addEventListener(name, function () { fire('guard-release'); }, true);
          });
          window.addEventListener('blur', function () { fire('guard-release'); });
          document.addEventListener('visibilitychange', function () {
            if (document.hidden) { fire('guard-release'); }
          });
        })();
        </script>
        """.replace("HEARTBEAT_MS", str(HEARTBEAT_INTERVAL_MS))
    )


def _release_all(adapters: RobotAdapters, session_id: str) -> None:
    guard = adapters.guard
    if guard is None:
        return
    guard.release_motion(session_id)


def _refresh_status(
    adapters: RobotAdapters,
    hold: _Hold,
    status,
    *,
    moving: bool,
) -> None:
    guard = adapters.guard
    if guard is None:
        return
    age = guard.heartbeat_age()
    rate = command_for_speed(hold.speed_mps)
    stall_note = "" if is_above_stall_threshold(rate) else "  (below the stall threshold)"
    elapsed = ""
    if moving and hold.started_at is not None:
        elapsed = f"  |  hold {time.monotonic() - hold.started_at:5.1f} s"
    status.set_text(
        f"{'MOVING' if moving else 'idle'}{elapsed}  |  "
        f"command {hold.speed_mps:.2f} m/s -> {rate:.2f} rps{stall_note}  |  "
        f"heartbeat {age:.2f} s  |  {guard.stopped_reason}"
    )


def _estop_controls(adapters: RobotAdapters, status=None) -> None:
    estop = adapters.estop
    guard = adapters.guard
    if estop.latched:
        ui.label(f"SOFTWARE E-STOP LATCHED ({estop.reason})").classes(
            "text-sm font-bold text-red-700"
        )
    else:
        ui.label("Software E-stop: not latched.").classes("text-xs text-gray-500")

    def _trip() -> None:
        estop.trip("operator (software)")
        if guard is not None:
            guard.trip("operator (software)")
        adapters.chassis.stop()
        ui.notify(
            "Software E-STOP latched. This is NOT the physical E-stop.",
            color="negative",
            position="top",
        )

    confirmed = ui.checkbox("I have verified the robot area is safe to clear the stop")

    def _clear() -> None:
        if guard is not None:
            guard.clear(confirmed_safe=bool(confirmed.value))
        if estop.clear(confirmed_safe=bool(confirmed.value)):
            ui.notify("Software E-STOP cleared.", color="positive")
        else:
            ui.notify("Not cleared: confirm the area is safe first.", color="warning")

    with ui.row().classes("gap-2"):
        ui.button("E-STOP (software)", icon="pan_tool", on_click=_trip).props("color=red")
        ui.button("Clear stop", icon="lock_open", on_click=_clear).props("outline")
