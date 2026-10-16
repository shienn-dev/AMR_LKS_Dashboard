"""Camera probe tests using a fake sysfs tree (no real device is touched)."""

from __future__ import annotations

from pathlib import Path

from amr_core.robot.camera import probe_camera
from amr_core.robot.interfaces import ConnectionState


def _make_sysfs(tmp_path: Path) -> Path:
    (tmp_path / "class" / "video4linux").mkdir(parents=True)
    (tmp_path / "bus" / "usb" / "devices").mkdir(parents=True)
    return tmp_path


def _add_video_node(sysfs: Path, node: str, name: str) -> None:
    directory = sysfs / "class" / "video4linux" / node
    directory.mkdir(parents=True)
    (directory / "name").write_text(name)


def _add_usb(sysfs: Path, dev: str, vid: str, pid: str) -> None:
    directory = sysfs / "bus" / "usb" / "devices" / dev
    directory.mkdir(parents=True)
    (directory / "idVendor").write_text(vid)
    (directory / "idProduct").write_text(pid)


def test_no_camera(tmp_path: Path) -> None:
    status = probe_camera(_make_sysfs(tmp_path))
    assert status.kind == "none"
    assert status.frames_available is False
    assert status.state is ConnectionState.UNAVAILABLE


def test_depth_camera_present_but_unavailable(tmp_path: Path) -> None:
    sysfs = _make_sysfs(tmp_path)
    _add_usb(sysfs, "2-2", "3251", "1930")
    status = probe_camera(sysfs)
    assert status.kind == "depth"
    assert status.frames_available is False
    assert "Aurora 930" in status.detail


def test_uvc_node_detected(tmp_path: Path) -> None:
    sysfs = _make_sysfs(tmp_path)
    _add_video_node(sysfs, "video0", "USB Camera: HD")
    status = probe_camera(sysfs)
    assert status.kind == "usb"
    assert status.frames_available is False


def test_pi_internal_nodes_are_not_cameras(tmp_path: Path) -> None:
    sysfs = _make_sysfs(tmp_path)
    _add_video_node(sysfs, "video19", "rpivid")
    _add_video_node(sysfs, "video20", "pispbe-input")
    status = probe_camera(sysfs)
    assert status.kind == "none"
