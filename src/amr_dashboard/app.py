"""NiceGUI dashboard entry point (Phase 1 prototype).

Run with:  python -m amr_dashboard
or:        python run_dashboard.py

Design notes
------------
- UI is kept separate from state/mission logic (``amr_core``).
- One application, two modes (DASH-01). Competition mode locks/hides features.
- The mission is advanced by exactly ONE server-side loop
  (``amr_dashboard.runtime.start_server_loop``), started on app startup. The
  per-page ``ui.timer`` only refreshes the view; it never advances the runtime,
  so adding browsers does not add advancement loops.
- No motion controls exist in competition mode (DASH-04).
"""

from __future__ import annotations

import random

from nicegui import app, ui

from amr_core.mission import MissionConfig, validate_mission
from amr_core.mission_runner import mission_status
from amr_core.samples import SAMPLE_MISSIONS, get_sample_mission
from amr_core.states import RobotState
from amr_core.vision import sample_detections
from amr_dashboard import panels
from amr_dashboard.runtime import get_runtime, start_server_loop, stop_server_loop

TICK_INTERVAL_S = 0.5  # per-page display refresh interval (seconds)


class DashboardState:
    """Holds the single simulation engine and current UI mode.

    UI-facing glue only. All authoritative state lives in the engine.

    ``draft`` is the mission configuration being *edited* in the UI. It is kept
    as a separate object from ``engine.mission`` (the active mission): edits to
    the draft never change the active mission until "Validate & apply" promotes
    an independent copy of the draft to the engine.
    """

    def __init__(self) -> None:
        self.rng = random.Random(2026)  # deterministic sample data (for the draft)
        # Use the process-wide runtime engine so mission execution does NOT
        # depend on a browser connection (Opsi A). Two browser pages share the
        # same engine and runner; closing one does not stop the mission.
        runtime = get_runtime()
        self.runtime = runtime
        self.engine = runtime.engine
        self.mode = "competition"
        first = get_sample_mission(SAMPLE_MISSIONS[0].mission_id)
        assert first is not None
        self.draft: MissionConfig = first.sample_config(self.rng)
        self.runner = runtime.runner
        # Event-log cursor: the highest event sequence number already shown.
        # Starts at 0 so a fresh page displays every retained event once.
        self.log_cursor = 0
        # Last rendered layout signature; drives structural rebuilds (F9).
        self.layout_signature: tuple[str, ...] | None = None


@ui.page("/")
def main_page() -> None:
    state = DashboardState()
    _build_header(state)

    # Refreshable regions. They are created once inside the structure and each
    # `.refresh()` re-renders only that region in place (no body.clear()).
    monitor = ui.refreshable(lambda: _render_monitor(state))
    mission_panel = ui.refreshable(lambda: _render_mission_config(state))
    mission_log = ui.refreshable(lambda: _render_mission_log(state))

    with ui.column().classes("w-full max-w-6xl mx-auto gap-3 p-3"):
        panels.simulation_banner()
        panels.connection_indicator(connected=False)

        # Structure is rebuilt only when the *layout* changes (currently: the
        # Competition/Development mode). Read-only content updates in place, so
        # the 2 Hz tick no longer destroys interactive widgets (F9).
        structure = ui.column().classes("w-full gap-3")
        _render_structure(structure, state, monitor, mission_panel, mission_log)

        # A single persistent, append-only event log shared by both modes.
        ui.label("Event log (simulated)").classes("text-sm text-gray-500 uppercase")
        log = panels.event_log(max_lines=300)
        state.log_cursor = panels.append_events(log, state.engine, state.log_cursor)

        # Per-page timer: refresh the view only. It never advances the runtime.
        timer = ui.timer(
            TICK_INTERVAL_S,
            lambda: _on_tick(structure, log, state, monitor, mission_panel, mission_log),
            active=True,
        )

    with ui.page_sticky(position="bottom-right"):
        # Pauses only this browser's display refresh; the mission keeps running
        # on the server (single runtime loop).
        ui.button("Pause display refresh", icon="pause", on_click=timer.deactivate).props(
            "outline"
        )


def _render_structure(
    structure: ui.column,
    state: DashboardState,
    monitor: ui.refreshable,
    mission_panel: ui.refreshable,
    mission_log: ui.refreshable,
) -> None:
    """Build (or rebuild) the page layout. Called on page load and layout change."""
    structure.clear()
    with structure:
        with ui.row().classes("w-full gap-4 items-stretch"):
            monitor()
            if state.mode == "competition":
                _render_competition_side(state)
            else:
                _render_development_side(state)
        mission_panel()
        _render_vision_panel()
        mission_log()


def _on_tick(
    structure: ui.column,
    log: ui.log,
    state: DashboardState,
    monitor: ui.refreshable,
    mission_panel: ui.refreshable,
    mission_log: ui.refreshable,
) -> None:
    # REFRESH ONLY. The mission is advanced by the single server-side loop in
    # amr_dashboard.runtime; the page must never call runtime.step()/engine.tick()
    # or each connected browser would add another advancement loop.

    # Rebuild the layout only when its structure changed (e.g. mode switch).
    signature = layout_signature(state)
    if signature != state.layout_signature:
        state.layout_signature = signature
        _render_structure(structure, state, monitor, mission_panel, mission_log)
    else:
        # Update read-only regions in place instead of clearing the whole body.
        monitor.refresh()
        mission_panel.refresh()
        mission_log.refresh()

    state.log_cursor = panels.append_events(log, state.engine, state.log_cursor)


def layout_signature(state: DashboardState) -> tuple[str, ...]:
    """Structural facts that require a full layout rebuild when they change.

    Kept deliberately small and deterministic: currently only the active mode
    (Competition vs Development) changes which panel is shown. All other
    updates are applied in place by refreshing the read-only regions.
    """
    return (state.mode,)


def _build_header(state: DashboardState) -> None:
    with ui.header().classes("items-center justify-between bg-slate-800 text-white px-4"):
        with ui.row().classes("items-center gap-2"):
            ui.icon("smart_toy")
            ui.label("AMR LKS Operator Dashboard").classes("text-lg font-semibold")
            ui.badge("PHASE 1 · SIMULATED").props("color=amber-8 text-color=black")
        with ui.row().classes("items-center gap-4"):
            ui.label("Mode").classes("text-sm opacity-80")
            ui.toggle(
                {"competition": "Competition", "development": "Development"},
                value="competition",
                on_change=lambda e: _set_mode(state, e.value),
            ).props("color=amber")


def _set_mode(state: DashboardState, mode: str) -> None:
    state.mode = mode


def _render_mission_log(state: DashboardState) -> None:
    """Read-only structured mission log (Phase 2). No mission logic here."""
    with ui.card().classes("w-full"):
        ui.label("Structured mission log").classes("text-sm text-gray-500 uppercase")
        ui.label(
            "Per-step records from the mock mission runner (typed log, not the "
            "event log above)."
        ).classes("text-xs text-gray-500")
        status = mission_status(state.engine.runner)  # type: ignore[arg-type]
        panels.mission_log_panel(status)


# --------------------------------------------------------------------------- #
# Monitor (shared, read-only)
# --------------------------------------------------------------------------- #

def _render_monitor(state: DashboardState) -> None:
    engine = state.engine
    with ui.card().classes("flex-1 min-w-[320px]"):
        ui.label("Robot state (simulated)").classes("text-sm text-gray-500 uppercase")
        panels.state_indicator(engine)

        ui.separator()
        ui.label("Readiness checklist").classes("text-sm text-gray-500 uppercase")
        panels.health_checklist(engine)

        ui.separator()
        ui.label("Active mission").classes("text-sm text-gray-500 uppercase")
        panels.mission_summary(engine)

        ui.separator()
        ui.label(f"Current step: {engine.current_step}").classes("text-sm font-medium")
        panels.progress_row(engine)
        ui.label(
            f"Progress {engine.progress_fraction:.0%} "
            f"({engine.step_index}/{engine.total_steps} steps)"
        ).classes("text-xs text-gray-500")


# --------------------------------------------------------------------------- #
# Competition mode side panel (minimal, read-only, no motion controls)
# --------------------------------------------------------------------------- #

def _render_competition_side(state: DashboardState) -> None:
    engine = state.engine
    with ui.card().classes("w-[340px]"):
        ui.label("Competition mode").classes("text-sm text-gray-500 uppercase")
        ui.label("Operator focus: verify readiness, then START on the robot.").classes(
            "text-xs text-gray-500"
        )

        ui.separator()
        ui.label("Simulated controls").classes("text-xs text-amber-700 uppercase")
        ui.label(
            "These buttons only move the software simulation. "
            "The real START and E-STOP are physical buttons on the robot."
        ).classes("text-xs text-amber-800")

        start_check = engine.can_start()
        can_reset = engine.state in (
            RobotState.DONE,
            RobotState.FAILED,
            RobotState.STOPPED,
            RobotState.FAULT,
        )
        with ui.row().classes("gap-2"):
            ui.button("Simulate START", icon="play_arrow", on_click=lambda: _do_start(state)) \
                .props("color=green").set_enabled(start_check.allowed)
            ui.button("Simulate RESET", icon="restart_alt", on_click=lambda: _do_reset(state)) \
                .props("outline").set_enabled(can_reset)

        # Show why START is unavailable instead of failing silently.
        if not start_check.allowed:
            ui.label(f"START unavailable: {start_check.reason}").classes(
                "text-xs text-amber-800"
            )


# --------------------------------------------------------------------------- #
# Development mode side panel (diagnostics, detailed logs, demo controls)
# --------------------------------------------------------------------------- #

def _render_development_side(state: DashboardState) -> None:
    engine = state.engine
    with ui.card().classes("w-[380px]"):
        ui.label("Development mode").classes("text-sm text-gray-500 uppercase")
        ui.label(
            "Diagnostics only in Phase 1. Manual movement and hardware commands "
            "are OUT OF SCOPE."
        ).classes("text-xs text-gray-500")

        ui.separator()
        ui.label("Simulated component health (inject failures)").classes(
            "text-xs text-gray-500 uppercase"
        )
        for key, item in engine.health.items():
            with ui.row().classes("items-center justify-between w-full"):
                ui.label(
                    f"{item.label}{' (critical)' if item.critical else ''}"
                ).classes("text-sm")
                ui.switch(
                    value=item.ok,
                    on_change=lambda e, k=key: _set_health(state, k, bool(e.value)),
                )

        ui.separator()
        ui.label("Simulated fault injection").classes("text-xs text-gray-500 uppercase")
        with ui.row().classes("gap-2"):
            ui.button("Fail mission", on_click=lambda: _do_fail(state)).props("outline")
            ui.button("Mark DONE", on_click=lambda: _do_done(state)).props("outline")


def _set_health(state: DashboardState, key: str, ok: bool) -> None:
    """Route a simulated health change through the engine's public API.

    The engine owns the resulting state transition (READY/BOOT -> FAULT,
    RUNNING -> FAILED); the UI never assigns ``engine.state`` itself.
    """
    state.engine.apply_health(key, ok)


def _do_start(state: DashboardState) -> None:
    """Request a simulated START. Report rejection instead of failing silently."""
    result = state.engine.start_mission()
    if not result.allowed:
        ui.notify(f"START rejected: {result.reason}", color="negative", position="top")


def _do_reset(state: DashboardState) -> None:
    state.engine.reset()


def _do_fail(state: DashboardState) -> None:
    state.engine.fail_mission("operator-injected simulated failure")


def _do_done(state: DashboardState) -> None:
    state.engine.complete_mission()


# --------------------------------------------------------------------------- #
# Mission configuration (locked while RUNNING — DASH-05)
# --------------------------------------------------------------------------- #

def _render_mission_config(state: DashboardState) -> None:
    engine = state.engine
    locked = not engine.can_edit_mission()

    with ui.card().classes("w-full"):
        with ui.row().classes("items-center gap-3"):
            ui.label("Mission configuration").classes("text-sm text-gray-500 uppercase")
            ui.badge("SIMULATED SAMPLE DATA").props("color=amber-8 text-color=black")
            if locked:
                ui.badge("LOCKED (RUNNING)").props("color=red-6")

        ui.label("Mission editing is locked while the simulated robot is RUNNING.").classes(
            "text-xs text-gray-500"
        )

        with ui.column().classes("w-full gap-2") as editor:
            if locked:
                editor.props("disable")
            with ui.row().classes("gap-4 items-end"):
                ui.select(
                    options=[m.mission_id for m in SAMPLE_MISSIONS],
                    label="Sample mission",
                    value=state.draft.mission_id,
                    on_change=lambda e: _change_mission(state, e.value),
                ).classes("w-48")
                ui.number(
                    label="Time limit (s)",
                    value=state.draft.time_limit_s,
                    min=30,
                    max=600,
                    on_change=lambda e: _set_field(state, "time_limit_s", int(e.value or 0)),
                ).classes("w-40")
                ui.number(
                    label="Reserve for home (s)",
                    value=state.draft.reserve_for_home_s,
                    min=0,
                    max=600,
                    on_change=lambda e: _set_field(
                        state, "reserve_for_home_s", int(e.value or 0)
                    ),
                ).classes("w-44")

            ui.label("Target order (randomized sample)").classes("text-xs text-gray-500")
            with ui.row().classes("gap-2"):
                for i, target in enumerate(state.draft.target_order):
                    ui.select(
                        options=["T1", "T2", "T3", "T4"],
                        value=target,
                        label=f"#{i + 1}",
                        on_change=lambda e, idx=i: _set_target(state, idx, e.value),
                    ).classes("w-24")

            ui.label("Rack colors (sample)").classes("text-xs text-gray-500")
            with ui.row().classes("gap-2"):
                for rack, color in state.draft.rack_colors.items():
                    ui.select(
                        options=["red", "green", "blue"],
                        value=color,
                        label=rack,
                        on_change=lambda e, r=rack: _set_rack(state, r, e.value),
                    ).classes("w-32")

            with ui.row().classes("gap-2"):
                ui.button("Randomize sample", on_click=lambda: _randomize(state)).props("outline")
                ui.button("Validate & apply", on_click=lambda: _validate_apply(state)).props(
                    "color=primary"
                )

        issues = validate_mission(state.draft)
        if issues:
            with ui.column().classes("gap-0 pt-2"):
                ui.label("Draft validation errors").classes("text-xs text-red-700 uppercase")
                for issue in issues:
                    ui.label(f"• {issue.field}: {issue.message}").classes("text-xs text-red-700")
            ui.label(
                "Draft is not applied. The active mission is unchanged until "
                "'Validate & apply' succeeds."
            ).classes("text-xs text-amber-800")
        elif _draft_matches_active(state):
            ui.label("Draft valid and applied to the active mission.").classes(
                "text-xs text-green-700 pt-2"
            )
        else:
            ui.label(
                "Draft valid. Not yet applied — active mission still uses the "
                "previous configuration."
            ).classes("text-xs text-amber-800 pt-2")


def _draft_matches_active(state: DashboardState) -> bool:
    """True when the draft's fields equal the currently active mission."""
    active = state.engine.mission
    draft = state.draft
    return (
        active is not None
        and active.mission_id == draft.mission_id
        and active.version == draft.version
        and active.time_limit_s == draft.time_limit_s
        and active.reserve_for_home_s == draft.reserve_for_home_s
        and active.target_order == draft.target_order
        and active.rack_colors == draft.rack_colors
    )


def _change_mission(state: DashboardState, mission_id: str) -> None:
    """Replace the *draft* with a fresh sample for the chosen mission.

    Does not touch the active mission.
    """
    mission = get_sample_mission(mission_id)
    if mission is None or not state.engine.can_edit_mission():
        return
    state.draft = mission.sample_config(state.rng)


def _set_field(state: DashboardState, field: str, value: int) -> None:
    """Edit a numeric draft field in place. Does not touch the active mission."""
    if state.engine.can_edit_mission():
        setattr(state.draft, field, value)


def _set_target(state: DashboardState, index: int, value: str) -> None:
    """Edit one target in the draft. Does not touch the active mission."""
    if state.engine.can_edit_mission() and index < len(state.draft.target_order):
        state.draft.target_order[index] = value


def _set_rack(state: DashboardState, rack: str, value: str) -> None:
    """Edit one rack color in the draft. Does not touch the active mission."""
    if state.engine.can_edit_mission():
        state.draft.rack_colors[rack] = value


def _randomize(state: DashboardState) -> None:
    """Randomize the *draft* only. Does not touch the active mission."""
    if not state.engine.can_edit_mission():
        ui.notify("Mission editing is locked while RUNNING.", color="red")
        return
    mission = get_sample_mission(state.draft.mission_id)
    if mission is not None:
        state.draft = mission.sample_config(state.rng)


def _validate_apply(state: DashboardState) -> None:
    """Validate the draft, then promote an independent copy to the active mission.

    On failure the active mission is left unchanged and the draft stays
    editable. On success the active mission is replaced with a copy of the
    draft (a new object) and a confirmation is shown. This does not change the
    robot state or start a mission.
    """
    if not state.engine.can_edit_mission():
        ui.notify("Mission editing is locked while RUNNING.", color="red")
        return
    issues = validate_mission(state.draft)
    if issues:
        ui.notify(f"Invalid: {issues[0]}", color="negative")
        return
    state.engine.mission = state.draft.copy()
    state.engine.log("Mission configuration validated and applied (simulated).")
    ui.notify("Mission configuration valid. Applied.", color="positive")


# --------------------------------------------------------------------------- #
# Vision panel (placeholder + simulated detections)
# --------------------------------------------------------------------------- #

def _render_vision_panel() -> None:
    with ui.card().classes("w-full"):
        with ui.row().classes("items-center gap-3"):
            ui.label("Vision").classes("text-sm text-gray-500 uppercase")
            ui.badge("PLACEHOLDER — NOT A LIVE CAMERA FEED").props("color=amber-8 text-color=black")
        with ui.row().classes("w-full gap-4"):
            with ui.column().classes(
                "w-64 h-40 items-center justify-center bg-slate-200 rounded"
            ):
                ui.icon("videocam_off").classes("text-4xl text-slate-500")
                ui.label("Camera feed placeholder").classes("text-xs text-slate-600")
            with ui.column().classes("gap-0"):
                ui.label("Sample detections (simulated)").classes("text-xs text-gray-500")
                for det in sample_detections():
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("category").classes("text-slate-500")
                        ui.label(det.display).classes("text-sm font-mono")


def _start_runtime_loop() -> None:
    """Start the single server-side advancement loop (runs without any browser).

    Idempotent: called once per application process on startup. It does not run
    per page/browser, so opening more clients adds no advancement loops.
    """
    start_server_loop()


def _stop_runtime_loop() -> None:
    """Cancel the server-side loop on application shutdown."""
    stop_server_loop()


app.on_startup(_start_runtime_loop)
app.on_shutdown(_stop_runtime_loop)


def run(host: str = "127.0.0.1", port: int = 8080, reload: bool = False) -> None:
    ui.run(host=host, port=port, title="AMR LKS Dashboard", reload=reload, show=False)
