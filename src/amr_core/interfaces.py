"""Single source of truth for team interface names (architecture rule #1).

In the full application this module defines the *only* names that team code may
use. Phase 1 is a dashboard prototype with simulated data, so the constants
below are declared for reference and future wiring; nothing in this repo
publishes or subscribes to ROS 2 yet.

Traceability
------------
The architecture document ("Kontrak antarmuka") lists each interface with a
status. We mirror that status here so a reader can tell, without opening the
document, which names are:

- ``RANCANGAN``: proposed by the team; not yet observed on any robot.
- ``TERVERIFIKASI``: read from the upstream Hiwonder/LanderPi repository and
  marked "Terverifikasi di LanderPi" in the document.

Important: "Terverifikasi di LanderPi" means verified against the *upstream*
LanderPi repository, NOT against the school's own robot. No interface is
verified on the school robot until a software snapshot is captured from it. See
``INTERFACE_CONTRACT`` for the per-name status and source note.

Reference: "Arsitektur Aplikasi AMR LKS" -> "Kontrak antarmuka".
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class InterfaceStatus(str, Enum):
    """Verification status of a team interface name.

    Values match the status wording used in the architecture document.
    """

    RANCANGAN = "RANCANGAN"
    TERVERIFIKASI = "TERVERIFIKASI"


# --- Implemented (Rancangan) interface names --------------------------------
# These are the names currently declared for future wiring. All are RANCANGAN
# per the architecture document's contract table.
TOPIC_MISSION_STATE = "/amr/mission_state"
TOPIC_HW_BUTTON = "/amr/hw/button"
TOPIC_HW_ESTOP = "/amr/hw/estop"
TOPIC_HW_INDICATOR = "/amr/hw/indicator"
TOPIC_HW_BATTERY = "/amr/hw/battery"
TOPIC_VISION_DETECTIONS = "/amr/vision/detections"
TOPIC_VISION_ANNOTATED = "/amr/vision/annotated"

SERVICE_START = "/amr/start"
SERVICE_RESET = "/amr/reset"
SERVICE_LOAD_MISSION = "/amr/load_mission"


@dataclass(frozen=True)
class InterfaceSpec:
    """A single row of the architecture interface contract.

    ``name`` is the documented name, ``status`` its verification status, and
    ``note`` the source/mapping note from the document. This is a *reference*
    table: it does not imply the interface is wired up.
    """

    name: str
    status: InterfaceStatus
    note: str = ""


# The full contract table from the architecture document. Documented names that
# are not (yet) declared as constants above are still listed here so their
# status is traceable. Names are copied verbatim from the document; none are
# invented or renamed.
INTERFACE_CONTRACT: tuple[InterfaceSpec, ...] = (
    InterfaceSpec(
        "/scan",
        InterfaceStatus.TERVERIFIKASI,
        "Terverifikasi di LanderPi (filter dari scan_raw), upstream repo only",
    ),
    InterfaceSpec(
        "/odom + TF odom -> base_footprint",
        InterfaceStatus.TERVERIFIKASI,
        "Terverifikasi di LanderPi (remap dari odometry/filtered), upstream repo only",
    ),
    InterfaceSpec(
        "/imu",
        InterfaceStatus.RANCANGAN,
        "Di LanderPi dipetakan dari /ros_robot_controller/imu_raw",
    ),
    InterfaceSpec(
        "/image",
        InterfaceStatus.RANCANGAN,
        "Nama asli diambil dari snapshot",
    ),
    InterfaceSpec("cmd_vel_in", InterfaceStatus.RANCANGAN, "Ke twist_mux"),
    InterfaceSpec(
        "/amr/hw/button", InterfaceStatus.RANCANGAN, "Pesan tim: tombol, jenis tekan"
    ),
    InterfaceSpec(
        "/amr/hw/estop", InterfaceStatus.RANCANGAN, "std_msgs/Bool; relevan untuk opsi B"
    ),
    InterfaceSpec(
        "/amr/hw/indicator",
        InterfaceStatus.RANCANGAN,
        "Pesan tim: warna, pola buzzer, teks",
    ),
    InterfaceSpec("/amr/hw/battery", InterfaceStatus.RANCANGAN, "std_msgs/Float32, volt"),
    InterfaceSpec(
        "oms/lift, oms/grip, oms/store, oms/retrieve",
        InterfaceStatus.RANCANGAN,
        "Action tim, skill pick/place -> platform",
    ),
    InterfaceSpec(
        "/amr/mission_state",
        InterfaceStatus.RANCANGAN,
        "Pesan tim: state, langkah aktif, waktu",
    ),
    InterfaceSpec(
        "/amr/start, /amr/reset, /amr/load_mission",
        InterfaceStatus.RANCANGAN,
        "Service tim",
    ),
    InterfaceSpec(
        "/amr/vision/detections, /amr/vision/annotated",
        InterfaceStatus.RANCANGAN,
        "Pesan tim; annotated adalah sensor_msgs/Image berlabel",
    ),
    InterfaceSpec(
        "Frame map -> odom -> base_footprint",
        InterfaceStatus.TERVERIFIKASI,
        "Terverifikasi di LanderPi, upstream repo only",
    ),
)

# Names declared as constants in this module, mapped to the exact
# ``INTERFACE_CONTRACT`` row they belong to. One contract row may cover several
# constants (e.g. the three /amr services share one row). Every value here is
# RANCANGAN in the contract table.
CONTRACT_ROW_BY_CONSTANT: dict[str, str] = {
    TOPIC_MISSION_STATE: "/amr/mission_state",
    TOPIC_HW_BUTTON: "/amr/hw/button",
    TOPIC_HW_ESTOP: "/amr/hw/estop",
    TOPIC_HW_INDICATOR: "/amr/hw/indicator",
    TOPIC_HW_BATTERY: "/amr/hw/battery",
    TOPIC_VISION_DETECTIONS: "/amr/vision/detections, /amr/vision/annotated",
    TOPIC_VISION_ANNOTATED: "/amr/vision/detections, /amr/vision/annotated",
    SERVICE_START: "/amr/start, /amr/reset, /amr/load_mission",
    SERVICE_RESET: "/amr/start, /amr/reset, /amr/load_mission",
    SERVICE_LOAD_MISSION: "/amr/start, /amr/reset, /amr/load_mission",
}

# The distinct constant names declared here, for a quick implemented-vs-documented
# check.
IMPLEMENTED_NAMES: tuple[str, ...] = tuple(CONTRACT_ROW_BY_CONSTANT)


def status_of(name: str) -> InterfaceStatus | None:
    """Return the documented status for an implemented constant *name*.

    *name* is the constant value (e.g. ``"/amr/hw/button"``). Rows the constant
    belongs to are looked up via ``CONTRACT_ROW_BY_CONSTANT`` so a single
    contract row can cover several constants. Returns None if unknown.
    """
    row = CONTRACT_ROW_BY_CONSTANT.get(name)
    if row is None:
        return None
    return documented_status(row)


def documented_status(row_name: str) -> InterfaceStatus | None:
    """Return the status for an exact ``INTERFACE_CONTRACT`` row name.

    Use this for documented-only rows that are not implemented as constants
    (for example ``"/scan"``). Returns None if the row is not listed.
    """
    for spec in INTERFACE_CONTRACT:
        if spec.name == row_name:
            return spec.status
    return None


@dataclass(frozen=True)
class HealthComponent:
    """A single readiness-checklist item.

    ``key`` matches the simulated health-check identifier; ``label`` is what the
    operator sees. ``critical`` items cause BOOT/READY -> FAULT before a run and
    RUNNING -> FAILED during a run.
    """

    key: str
    label: str
    critical: bool


# Readiness checklist (architecture: DASH-02, OPS-02). Order is display order.
HEALTH_COMPONENTS: tuple[HealthComponent, ...] = (
    HealthComponent("lidar", "LiDAR", critical=True),
    HealthComponent("camera", "Camera", critical=True),
    HealthComponent("motor_controller", "Motor controller", critical=True),
    HealthComponent("battery", "Battery", critical=False),
    HealthComponent("localization", "Localization", critical=False),
    HealthComponent("mission_config", "Mission configuration", critical=False),
)
