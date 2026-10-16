"""NiceGUI panel for the *live* LiDAR (real hardware).

The panel is read-only and separated from the serial reader: it only calls
``reader.snapshot()`` / ``reader.stats()`` and renders the result. The scan is
drawn as an inline SVG polar plot, which needs no extra dependency.

This data comes from the physical LiDAR and is labelled as such — it is kept
visually distinct from the simulated prototype data elsewhere on the dashboard.
"""

from __future__ import annotations

import math

from nicegui import ui

from amr_core.lidar.reader import LidarReader, LidarStatus
from amr_core.lidar.scan import ScanSnapshot

# Colour per status (NiceGUI badge colour name).
_STATUS_COLOR: dict[LidarStatus, str] = {
    LidarStatus.RUNNING: "green-7",
    LidarStatus.CONNECTING: "amber-7",
    LidarStatus.ERROR: "red-7",
    LidarStatus.STOPPED: "grey-7",
    LidarStatus.UNAVAILABLE: "orange-8",
}

_STATUS_LABEL: dict[LidarStatus, str] = {
    LidarStatus.RUNNING: "LIVE — reading hardware",
    LidarStatus.CONNECTING: "connecting…",
    LidarStatus.ERROR: "error — retrying",
    LidarStatus.STOPPED: "stopped",
    LidarStatus.UNAVAILABLE: "unavailable (pyserial missing)",
}

_DEFAULT_MAX_RANGE_MM = 4000.0


def render_scan_svg(
    snapshot: ScanSnapshot,
    *,
    size: int = 300,
    max_range_mm: float = _DEFAULT_MAX_RANGE_MM,
) -> str:
    """Render a scan snapshot as an inline SVG polar plot.

    Angle 0 deg points right (+x) and increases counter-clockwise, matching the
    LiDAR's own convention. Valid points are coloured by distance (near = warm,
    far = cool). Invalid (zero-distance) points are not drawn; their count is
    reported in the panel text.
    """
    if size <= 0:
        raise ValueError("size must be positive")
    if max_range_mm <= 0:
        raise ValueError("max_range_mm must be positive")

    center = size / 2.0
    radius = center - 8.0
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        f'width="{size}" height="{size}">',
        f'<circle cx="{center}" cy="{center}" r="{radius}" '
        f'fill="#0b1220" stroke="#334155" stroke-width="1"/>',
    ]

    # Range rings at 25/50/75/100 % of the display range.
    for fraction in (0.25, 0.5, 0.75, 1.0):
        parts.append(
            f'<circle cx="{center}" cy="{center}" r="{radius * fraction:.1f}" '
            f'fill="none" stroke="#1e293b" stroke-width="1"/>'
        )
    # Crosshair.
    parts.append(
        f'<line x1="{center - radius:.1f}" y1="{center}" '
        f'x2="{center + radius:.1f}" y2="{center}" stroke="#1e293b" stroke-width="1"/>'
    )
    parts.append(
        f'<line x1="{center}" y1="{center - radius:.1f}" '
        f'x2="{center}" y2="{center + radius:.1f}" stroke="#1e293b" stroke-width="1"/>'
    )

    for point in snapshot.points:
        if not point.valid:
            continue
        distance = min(point.distance_mm, max_range_mm)
        r = distance / max_range_mm * radius
        rad = math.radians(point.angle_deg)
        x = center + r * math.cos(rad)
        y = center - r * math.sin(rad)
        t = distance / max_range_mm
        color = f"rgb({int(239 * (1 - t) + 34 * t)},{int(68 * (1 - t) + 197 * t)},59)"
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.8" fill="{color}"/>'
        )

    # Range label.
    parts.append(
        f'<text x="6" y="{size - 6}" fill="#64748b" font-size="10">'
        f"0–{max_range_mm / 1000:.0f} m</text>"
    )
    parts.append("</svg>")
    return "".join(parts)


def lidar_panel(reader: LidarReader) -> None:
    """Render the live LiDAR card (status, counters and scan plot)."""
    stats = reader.stats()
    snapshot = reader.snapshot()

    with ui.card().classes("w-full"):
        with ui.row().classes("items-center gap-3 w-full"):
            ui.icon("radar")
            ui.label("LiDAR (live hardware)").classes("text-sm text-gray-500 uppercase")
            ui.badge(_STATUS_LABEL[stats.status]).props(
                f"color={_STATUS_COLOR[stats.status]} text-color=white"
            )
            ui.label(f"{stats.port} @ {stats.baud} baud").classes(
                "text-xs text-gray-500 font-mono"
            )

        if stats.status is LidarStatus.UNAVAILABLE:
            ui.label(
                "pyserial is not installed in this environment. "
                "Install it (pip install pyserial) to read the physical LiDAR."
            ).classes("text-xs text-orange-700")
            return

        if stats.status is LidarStatus.ERROR and stats.last_error:
            ui.label(f"Last serial error: {stats.last_error}").classes(
                "text-xs text-red-700"
            )

        with ui.row().classes("w-full gap-4 items-start"):
            ui.html(render_scan_svg(snapshot)).classes("shrink-0")
            with ui.column().classes("gap-1 grow"):
                _metric_row("Packets OK", f"{stats.packets_ok}")
                _metric_row("Packets/s", f"{stats.packets_per_s:.0f}")
                _metric_row("CRC failures", f"{stats.crc_failures}")
                _metric_row("Sync failures", f"{stats.sync_failures}")
                _metric_row("Bytes read", f"{stats.bytes_read}")
                _metric_row("Reconnects", f"{stats.reconnects}")
                ui.separator()
                _metric_row("Scan points", f"{len(snapshot.points)} / {snapshot.buckets}")
                _metric_row("Coverage", f"{snapshot.coverage_fraction:.0%}")
                _metric_row("Revolutions", f"{snapshot.revolutions}")
                if snapshot.invalid_count:
                    ui.label(
                        f"{snapshot.invalid_count} point(s) with no valid return "
                        "(distance 0) — treated as invalid, not free space."
                    ).classes("text-xs text-amber-700")

        if snapshot.points:
            ui.label(
                "Accumulated scan from multiple packets, arranged by angle. "
                "One packet is not a full revolution."
            ).classes("text-xs text-gray-500")
        else:
            ui.label("Waiting for valid scan data…").classes("text-xs text-gray-500")

        notes = reader.recent_notes()
        if notes:
            with ui.expansion("LiDAR reader log", icon="terminal").classes("w-full"):
                for note in notes[-12:]:
                    ui.label(note).classes("text-xs font-mono text-gray-600")


def _metric_row(caption: str, value: str) -> None:
    with ui.row().classes("items-center justify-between w-full"):
        ui.label(caption).classes("text-xs text-gray-500")
        ui.label(value).classes("text-sm font-mono")
