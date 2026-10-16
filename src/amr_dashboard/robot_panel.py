"""Robot panels: camera status, odometry status, remote chassis + arm control.

Every panel is honest about availability. A missing link is shown as
NOT CONNECTED / UNAVAILABLE, never as a live feed or a fabricated pose. The
chassis and arm controls submit to *offline* adapters that validate but never
transmit, and the panel says so on every action.
"""

from __future__ import annotations

from nicegui import ui

from amr_core.robot.interfaces import ArmCommand, ChassisCommand, CommandOutcome, ConnectionState
from amr_dashboard.robot_runtime import RobotAdapters

_STATE_COLOR: dict[ConnectionState, str] = {
    ConnectionState.CONNECTED: "green-7",
    ConnectionState.DISCONNECTED: "amber-7",
    ConnectionState.UNAVAILABLE: "orange-8",
    ConnectionState.DISABLED: "grey-7",
}


def robot_panels(adapters: RobotAdapters) -> None:
    """Render all robot subsystem panels (camera, odometry, chassis, arm)."""
    camera_panel(adapters)
    odometry_panel(adapters)
    with ui.row().classes("w-full gap-4 items-stretch"):
        chassis_control_panel(adapters)
        arm_control_panel(adapters)


def _state_badge(state: ConnectionState) -> None:
    ui.badge(state.value).props(f"color={_STATE_COLOR[state]} text-color=white")


def _report(outcome: CommandOutcome) -> None:
    color = "positive" if outcome.accepted else "negative"
    prefix = "VALIDATED (not transmitted)" if outcome.accepted else "REJECTED"
    ui.notify(f"{prefix}: {outcome.reason}", color=color, position="top")


def _metric(caption: str, value: str) -> None:
    with ui.column().classes("gap-0"):
        ui.label(caption).classes("text-xs text-gray-500 uppercase")
        ui.label(value).classes("text-base font-mono")


def camera_panel(adapters: RobotAdapters) -> None:
    status = adapters.camera
    with ui.card().classes("w-full"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("videocam" if status.frames_available else "videocam_off")
            ui.label("Camera (robot)").classes("text-sm text-gray-500 uppercase")
            _state_badge(status.state)
            ui.badge(f"kind: {status.kind}").props("color=blue-grey-7 text-color=white")
        if status.frames_available:
            ui.label(f"Live source: {status.device}").classes("text-xs text-green-700")
        else:
            ui.label("NO LIVE FEED — no camera frames are available.").classes(
                "text-sm font-medium text-red-700"
            )
            ui.label(status.detail).classes("text-xs text-gray-600")


def odometry_panel(adapters: RobotAdapters) -> None:
    source = adapters.odometry
    sample = source.sample()
    with ui.card().classes("w-full"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("explore")
            ui.label("Odometry (robot)").classes("text-sm text-gray-500 uppercase")
            _state_badge(source.state())
            ui.label(f"source: {source.name}").classes("text-xs text-gray-500 font-mono")
        ui.label(source.detail()).classes("text-xs text-gray-600")
        if sample is None:
            ui.label("No odometry data available.").classes("text-sm text-amber-800")
        else:
            with ui.grid(columns=3).classes("w-full gap-2"):
                _metric("x", f"{sample.x:.2f} m")
                _metric("y", f"{sample.y:.2f} m")
                _metric("yaw", f"{sample.yaw:.1f} deg")
                _metric("v", f"{sample.linear_x:.2f} m/s")
                _metric("omega", f"{sample.angular_z:.2f} rad/s")
                _metric("stamp", f"{sample.stamp_s:.2f} s")


def chassis_control_panel(adapters: RobotAdapters) -> None:
    chassis = adapters.chassis
    limits = chassis.limits
    with ui.card().classes("flex-1 min-w-[320px]"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("sports_esports")
            ui.label("Remote chassis control").classes("text-sm text-gray-500 uppercase")
            _state_badge(chassis.state())
        ui.label(
            "OFFLINE STRUCTURE — commands are validated and clamped to the limits "
            "below, but NOT transmitted: no verified chassis transport exists yet."
        ).classes("text-xs text-red-700")
        ui.label(
            f"Limits: +/-{limits.max_linear_x:.2f} m/s (x), "
            f"+/-{limits.max_linear_y:.2f} m/s (y), "
            f"+/-{limits.max_angular_z:.2f} rad/s (rot)"
        ).classes("text-xs text-gray-600")

        step_x, step_y, step_w = 0.10, 0.10, 0.50

        def _move(vx: float = 0.0, vy: float = 0.0, wz: float = 0.0) -> None:
            _report(chassis.submit(ChassisCommand(vx, vy, wz)))

        with ui.row().classes("gap-2"):
            ui.button("Forward", icon="arrow_upward", on_click=lambda: _move(vx=step_x))
            ui.button("Back", icon="arrow_downward", on_click=lambda: _move(vx=-step_x))
        with ui.row().classes("gap-2"):
            ui.button("Left", icon="arrow_back", on_click=lambda: _move(vy=step_y))
            ui.button("Right", icon="arrow_forward", on_click=lambda: _move(vy=-step_y))
        with ui.row().classes("gap-2"):
            ui.button("Rotate L", icon="rotate_left", on_click=lambda: _move(wz=step_w))
            ui.button("Rotate R", icon="rotate_right", on_click=lambda: _move(wz=-step_w))
        ui.button("STOP", icon="stop", on_click=lambda: _report(chassis.stop())).props(
            "color=orange"
        )

        ui.separator()
        _estop_controls(adapters)

        last = chassis.last_command()
        if last is not None:
            ui.label(
                f"Last validated command: vx={last.linear_x:.2f}, vy={last.linear_y:.2f}, "
                f"wz={last.angular_z:.2f} (NOT transmitted)"
            ).classes("text-xs text-gray-500 font-mono")


def _estop_controls(adapters: RobotAdapters) -> None:
    estop = adapters.estop
    if estop.latched:
        ui.label(f"SOFTWARE E-STOP LATCHED ({estop.reason})").classes(
            "text-sm font-bold text-red-700"
        )
    else:
        ui.label("Software E-stop: not latched.").classes("text-xs text-gray-500")

    def _trip() -> None:
        estop.trip("operator (software)")
        adapters.chassis.stop()
        ui.notify(
            "Software E-STOP latched. This is NOT the physical E-stop.",
            color="negative",
            position="top",
        )

    confirmed = ui.checkbox("I have verified the robot area is safe to clear the stop")

    def _clear() -> None:
        if estop.clear(confirmed_safe=bool(confirmed.value)):
            ui.notify("Software E-STOP cleared.", color="positive")
        else:
            ui.notify("Not cleared: confirm the area is safe first.", color="warning")

    with ui.row().classes("gap-2"):
        ui.button("E-STOP (software)", icon="pan_tool", on_click=_trip).props("color=red")
        ui.button("Clear stop", icon="lock_open", on_click=_clear).props("outline")


def arm_control_panel(adapters: RobotAdapters) -> None:
    arm = adapters.arm
    with ui.card().classes("flex-1 min-w-[320px]"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("precision_manufacturing")
            ui.label("Arm control").classes("text-sm text-gray-500 uppercase")
            _state_badge(arm.state())
        ui.label(
            "NOT CONNECTED — the arm command interface is unverified on this board, so "
            "no arm command is sent. The controls below only validate input."
        ).classes("text-xs text-red-700")
        ui.label(
            "Upstream uses 5 joints + gripper as bus-servo pulse widths (0..1000). "
            "Joint count, safe ranges and limits are NOT yet verified here."
        ).classes("text-xs text-gray-600")

        joints = ui.input("Joints (comma-separated pulse widths)", value="500,500,500,500,500")
        duration = ui.number("Duration (s)", value=1.0, min=0.02, max=30.0)

        def _submit() -> None:
            raw = str(joints.value or "")
            try:
                positions = tuple(int(part.strip()) for part in raw.split(",") if part.strip())
            except ValueError:
                ui.notify("Invalid joint list: use comma-separated integers.", color="negative")
                return
            command = ArmCommand(positions=positions, duration_s=float(duration.value or 1.0))
            _report(arm.submit(command))

        ui.button("Validate arm command", icon="rule", on_click=_submit).props("outline")
        last = arm.last_command()
        if last is not None:
            ui.label(
                f"Last validated: {last.positions} @ {last.duration_s:.2f}s (NOT transmitted)"
            ).classes("text-xs text-gray-500 font-mono")
