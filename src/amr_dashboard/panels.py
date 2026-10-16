"""Reusable UI building blocks for the dashboard.

Each function is a *small* unit that renders into the current NiceGUI container.
Keeping these separate from state logic satisfies the "UI separate from
mission/state logic" requirement.
"""

from __future__ import annotations

from nicegui import ui

from amr_core.mission_runner import MissionStatus
from amr_core.simulation import SimulationEngine
from amr_core.states import RobotState
from amr_dashboard.theme import (
    SIMULATION_BANNER,
    STATE_COLORS,
    STATE_FONT_PX,
    STATE_TEXT_COLORS,
)

_LEVEL_ICON = {"ok": ("check_circle", "text-green-600"), "fault": ("cancel", "text-red-600"),
               "warn": ("error", "text-amber-600")}


def simulation_banner() -> None:
    """A persistent, unmistakable notice that this build is simulated."""
    with ui.row().classes("w-full items-center bg-amber-100 text-amber-900 px-3 py-1 rounded"):
        ui.icon("science")
        ui.label(SIMULATION_BANNER).classes("text-sm font-medium")


def connection_indicator(connected: bool = False) -> None:
    """Robot connection indicator. Phase 1 is always 'disconnected (simulated)'."""
    color = "green" if connected else "grey"
    text = "ROBOT CONNECTED" if connected else "NO ROBOT CONNECTED (simulated)"
    with ui.row().classes("items-center gap-2"):
        ui.icon("circle").classes(f"text-{color}-600 text-xs")
        ui.label(text).classes("text-sm text-gray-600")


def state_indicator(engine: SimulationEngine) -> ui.label:
    """The large robot state indicator. Returns the label so callers can refresh."""
    label = ui.label(engine.state.value)
    label.classes("w-full text-center rounded py-2 font-bold")
    paint_state(label, engine.state)
    return label


def paint_state(label: ui.label, state: RobotState) -> None:
    """Update a previously rendered indicator to reflect a new state."""
    label.text = state.value
    bg = STATE_COLORS[state]
    fg = STATE_TEXT_COLORS.get(state, "white")
    label.style(
        f"background:{bg}; color:{fg}; font-size:{STATE_FONT_PX}px; letter-spacing:2px;"
    )


def health_checklist(engine: SimulationEngine) -> None:
    """Readiness checklist (LiDAR, camera, motor controller, battery, ...)."""
    with ui.column().classes("gap-1"):
        for item in engine.health.values():
            icon, color = _LEVEL_ICON[item.level]
            tag = " (critical)" if item.critical else ""
            with ui.row().classes("items-center gap-2"):
                ui.icon(icon).classes(color)
                ui.label(f"{item.label}{tag}").classes("text-sm")
                ui.label("OK" if item.ok else "FAIL").classes(
                    f"text-xs {'text-green-700' if item.ok else 'text-red-700'}"
                )


def mission_summary(engine: SimulationEngine) -> None:
    """Active mission name/version and run timing (read-only monitor)."""
    mission = engine.mission
    name = mission.display_name if mission else "-"
    version = mission.version if mission else "-"
    with ui.grid(columns=4).classes("w-full gap-2"):
        _metric("Mission", name)
        _metric("Version", str(version))
        _metric("Elapsed", f"{engine.elapsed_s:.0f} s")
        _metric("Remaining", f"{engine.remaining_s:.0f} s")


def _metric(caption: str, value: str) -> None:
    with ui.column().classes("gap-0"):
        ui.label(caption).classes("text-xs text-gray-500 uppercase")
        ui.label(value).classes("text-lg font-semibold")


def progress_row(engine: SimulationEngine) -> None:
    ui.linear_progress(value=engine.progress_fraction, show_value=False).classes("w-full")


def event_log(max_lines: int = 300) -> ui.log:
    """Create a persistent, append-only event log widget.

    Timestamps are already attached to each ``LogEvent`` at emit time, so the
    widget only renders text; it never re-stamps or rewrites history.
    """
    return ui.log(max_lines=max_lines).classes("w-full h-64 font-mono text-xs")


def append_events(log: ui.log, engine: SimulationEngine, since_seq: int) -> int:
    """Push retained events with ``seq > since_seq``; return the new cursor.

    ``since_seq`` is an event sequence number (``LogEvent.seq``), not a list
    index, so it stays correct even when the engine trims old events from its
    buffer. This keeps rendering append-only: re-rendering does not duplicate
    entries and does not re-timestamp them. The returned cursor is the highest
    sequence number consumed (or ``since_seq`` when nothing new arrived).
    """
    cursor = since_seq
    for event in engine.events_since(since_seq):
        log.push(event.render())
        cursor = event.seq
    return cursor


def mission_log_panel(status: MissionStatus | None) -> None:
    """Render the structured mission log (read-only).

    Shows one row per structured record (step id, skill, attempt, outcome,
    reason, duration). This is the *typed* per-step log, distinct from the
    human-readable event log above.
    """
    if status is None:
        ui.label("No mission runner attached (legacy simulation path).").classes(
            "text-xs text-gray-500"
        )
        return

    if status.terminal_reason:
        ui.label(f"Terminal: {status.terminal_reason}").classes("text-xs text-red-700")

    if not status.records:
        ui.label("No steps recorded yet.").classes("text-xs text-gray-500")
        return

    with ui.column().classes("w-full gap-0"):
        for rec in status.records:
            duration = f"{rec.duration_s:.0f}s" if rec.duration_s is not None else "-"
            flag = " [incomplete]" if rec.incomplete else ""
            ui.label(
                f"{rec.step_id}  {rec.skill}  attempt {rec.attempt}  "
                f"-> {rec.outcome}{flag}  ({rec.reason}, {duration})"
            ).classes("text-xs font-mono text-gray-700")
