"""Robot panels: camera status, odometry status, remote chassis + arm control.

Every panel is honest about availability. A missing link is shown as
NOT CONNECTED / UNAVAILABLE, never as a live feed or a fabricated pose. The
arm control submits to an *offline* adapter that validates but never
transmits, and the panel says so on every action. The live chassis control
lives in :mod:`amr_dashboard.chassis_panel`.
"""

from __future__ import annotations

from nicegui import ui

from amr_core.robot.interfaces import ArmCommand, CommandOutcome, ConnectionState
from amr_dashboard.robot_runtime import RobotAdapters

_STATE_COLOR: dict[ConnectionState, str] = {
    ConnectionState.CONNECTED: "green-7",
    ConnectionState.DISCONNECTED: "amber-7",
    ConnectionState.UNAVAILABLE: "orange-8",
    ConnectionState.DISABLED: "grey-7",
}


def robot_panels(adapters: RobotAdapters) -> None:
    """Render the read-only robot panels (camera, odometry).

    The interactive panels (chassis, arm) are **not** here: they are rendered
    once, outside the region the dashboard's refresh tick re-renders. A panel
    that is rebuilt every 0,5 s loses whatever the operator was typing, and
    it costs the event loop the time the motor stream needs.
    """
    camera_panel(adapters)
    odometry_panel(adapters)


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
