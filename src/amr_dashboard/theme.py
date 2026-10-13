"""Shared visual constants for the dashboard.

State colors follow the architecture "Tanda status" table so the dashboard uses
the same colors as the robot LED.
"""

from __future__ import annotations

from amr_core.states import RobotState

# State -> background color hex. Matches the LED table (BOOT blue, FAULT red,
# READY green, RUNNING yellow, DONE white, FAILED/STOPPED red).
STATE_COLORS: dict[RobotState, str] = {
    RobotState.BOOT: "#1d4ed8",     # blue
    RobotState.FAULT: "#dc2626",    # red
    RobotState.READY: "#16a34a",    # green
    RobotState.RUNNING: "#ca8a04",  # yellow
    RobotState.DONE: "#e5e7eb",     # white
    RobotState.FAILED: "#dc2626",   # red
    RobotState.STOPPED: "#dc2626",  # red
}

# Text color to use on top of each state background.
STATE_TEXT_COLORS: dict[RobotState, str] = {
    RobotState.DONE: "#111827",
}

SIMULATION_BANNER = (
    "SIMULATED PROTOTYPE — no robot is connected. "
    "Buttons here are software simulations, never the physical START or E-STOP."
)

# Font size for the large state indicator and key readouts.
STATE_FONT_PX = 56
