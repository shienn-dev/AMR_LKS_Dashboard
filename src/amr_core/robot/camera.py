"""Camera availability probe.

The robot's camera is a **Deptrum Aurora 930 depth camera** (USB ``3251:1930``,
3D structured light). Audit finding: it has **no kernel driver bound** and exposes
**no** ``/dev/video`` node, so no frames can be read without the vendor (Deptrum)
SDK. It is therefore *not* a UVC camera and cannot be opened with standard Linux
video tooling.

This module only *reports* availability. It never opens a device and never
fabricates a frame — the dashboard must not show a placeholder as a live feed.
The probe reads sysfs only, so it is safe to call at any time.
"""

from __future__ import annotations

from pathlib import Path

from amr_core.robot.interfaces import CameraStatus, ConnectionState

AURORA930_VID = "3251"
AURORA930_PID = "1930"

# Pi-internal video nodes that are NOT cameras (ISP backend / H.264 codec).
_NON_CAMERA_NODE_PREFIXES = ("pispbe", "rpivid")


def _uvc_nodes(sysfs: Path) -> list[str]:
    """Return non-internal ``/dev/video*`` nodes (candidate UVC cameras)."""
    base = sysfs / "class" / "video4linux"
    found: list[str] = []
    if not base.is_dir():
        return found
    for node in sorted(base.iterdir()):
        try:
            name = (node / "name").read_text().strip()
        except OSError:
            continue
        if any(name.startswith(prefix) for prefix in _NON_CAMERA_NODE_PREFIXES):
            continue
        found.append(f"/dev/{node.name} ({name})")
    return found


def _usb_present(sysfs: Path, vid: str, pid: str) -> bool:
    """True if a USB device with the given vendor/product id is present."""
    base = sysfs / "bus" / "usb" / "devices"
    if not base.is_dir():
        return False
    for device in base.iterdir():
        vendor_file = device / "idVendor"
        product_file = device / "idProduct"
        try:
            if vendor_file.read_text().strip() == vid and product_file.read_text().strip() == pid:
                return True
        except OSError:
            continue
    return False


def probe_camera(sysfs: Path | str = "/sys") -> CameraStatus:
    """Read-only camera availability probe. Never opens a device."""
    sysfs = Path(sysfs)

    uvc = _uvc_nodes(sysfs)
    if uvc:
        return CameraStatus(
            state=ConnectionState.UNAVAILABLE,
            kind="usb",
            device=uvc[0],
            detail=(
                f"UVC video node(s) present ({', '.join(uvc)}), but no streaming backend "
                "is wired up in this phase."
            ),
            frames_available=False,
        )

    if _usb_present(sysfs, AURORA930_VID, AURORA930_PID):
        return CameraStatus(
            state=ConnectionState.UNAVAILABLE,
            kind="depth",
            device=f"usb {AURORA930_VID}:{AURORA930_PID}",
            detail=(
                "Deptrum Aurora 930 depth camera detected on USB, but no kernel driver "
                "or Deptrum SDK is installed, so it exposes no /dev/video node and no "
                "frames can be read. Installing the vendor SDK / ROS driver requires "
                "explicit approval."
            ),
            frames_available=False,
        )

    return CameraStatus(
        state=ConnectionState.UNAVAILABLE,
        kind="none",
        device="-",
        detail=(
            "No camera detected: no UVC /dev/video node and no known depth camera "
            "on USB."
        ),
        frames_available=False,
    )
