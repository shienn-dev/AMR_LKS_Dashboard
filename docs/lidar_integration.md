# LiDAR Integration (STL-19P / LD19)

This note records how the physical LiDAR is integrated into the AMR LKS
dashboard, and — importantly — **what is verified vs. what is still an
assumption**. It complements the code in `src/amr_core/lidar/`.

## 1. Device facts (observed / established)

| Item | Value | Source |
| --- | --- | --- |
| Port | `/dev/ttyUSB0` | team capture script `~/lidar-test/test_stl19p.py` |
| USB adapter | QinHeng CH340, USB ID `1a86:7523` | `lsusb` on the Pi |
| Baud rate | `230400` | capture script + LDROBOT datasheet |
| Frame header | `0x54 0x2C` | capture script |
| Packet length | 47 bytes | capture script + datasheet |
| CRC | CRC-8, poly `0x4D`, init `0x00`, over the first 46 bytes | capture script |
| Points per packet | **12** (see §5) | capture script + datasheet |

`/dev/ttyACM0` is a **different** USB device (USB ID `1a86:55d4`) and is **not**
the LiDAR. Do not configure the reader to use it.

The port must be readable by the user running the dashboard (the Pi user is in
the `dialout` group; `/dev/ttyUSB0` is `root:dialout`, mode `0660`).

## 2. Packet layout (little-endian multi-byte fields)

| Offset | Size | Field |
| --- | --- | --- |
| 0 | 1 | header `0x54` |
| 1 | 1 | `VerLen` `0x2C` (high 3 bits = packet type 1, low 5 bits = 12 points) |
| 2 | 2 | rotation speed, deg/s |
| 4 | 2 | start angle, 0.01° units |
| 6 | 36 | 12 × (2-byte distance in mm + 1-byte intensity) |
| 42 | 2 | end angle, 0.01° units |
| 44 | 2 | timestamp, ms (wraps) |
| 46 | 1 | CRC-8 over bytes 0..45 |

Per-point angles are linearly interpolated between start and end angle
(`src/amr_core/lidar/protocol.py`). The 360° → 0° wrap is handled explicitly.

## 3. Architecture

- `amr_core/lidar/protocol.py` — pure CRC + decode (+ `build_packet` for tests).
  No serial I/O, no third-party dependency.
- `amr_core/lidar/scan.py` — `ScanAccumulator` folds points from many packets
  into angular buckets and publishes an immutable `ScanSnapshot` under a lock.
- `amr_core/lidar/reader.py` — `LidarReader` owns one background thread, opens
  the serial port, resynchronises, validates CRCs, reconnects, and exposes
  `snapshot()` / `stats()`. `pyserial` is imported lazily.
- `amr_core/lidar/config.py` — `LidarConfig`, from env vars.
- `amr_dashboard/lidar_runtime.py` — one process-wide reader (one port owner).
- `amr_dashboard/lidar_panel.py` — read-only NiceGUI panel + inline-SVG scan.

Design guarantees:

- Serial reading is on its own thread; the UI thread only reads snapshots.
- The UI never reads a half-updated scan (snapshot is a locked copy).
- One packet is **not** a full revolution: points from many packets are
  bucketed by angle (default 1° resolution, 360 buckets).
- Zero/invalid distances are kept as **invalid** and never become free space.
- A truncated packet, bad header, CRC failure, read timeout, missing port, or
  disconnected device are all handled; the reader retries with a backoff.
- The same port is never opened by two readers (single shared instance).

## 4. Configuration (no code edits needed)

Defaults: `/dev/ttyUSB0` @ `230400`.

| Env var | CLI flag | Meaning |
| --- | --- | --- |
| `AMR_LIDAR_PORT` | `--lidar-port` | serial port |
| `AMR_LIDAR_BAUD` | `--lidar-baud` | baud rate |
| `AMR_LIDAR_ENABLED` | `--no-lidar` | enable/disable the reader |

## 5. Discrepancy with the task brief (recorded)

The brief said each packet has **six** distance values of 3 bytes each. The
team's own verified capture script reads **twelve** values
(`range(6, 42, 3)` over 36 bytes), and the LDROBOT datasheet specifies 12
points per packet. The brief's "six" is incorrect for this device; the code
follows the script + datasheet (**12 points**). The 47-byte length and the
`0x54 0x2C` header in the brief are confirmed correct.

## 6. Verification status

**Verified by automated tests** (`tests/test_lidar_*.py`, run with `pytest`):
CRC vectors, decode/encode round-trip, 12-point count, angle interpolation and
360° wrap, invalid-zero handling, accumulator coverage/immutability, reader
parsing of valid + corrupted + split + truncated packets, reconnect on a
disconnected device, graceful "unavailable" without `pyserial`, config
overrides, SVG rendering, and the single-reader runtime.

**Verified against the physical device** (run on the Pi, 2026-10-16):
`scripts/lidar_probe.py --seconds 5` on `/dev/ttyUSB0` @ `230400` returned
2079 valid packets (~436 packets/s), **0 CRC failures, 0 sync failures**, full
360/360 bucket coverage, 50 detected revolutions, and 40 zero-distance
("invalid") points. The dashboard was then launched and confirmed to hold the
port and render the live panel.

**Assumptions not independently verified:**

- The angle interpolation divisor `(points - 1) = 11` (LDROBOT datasheet). Some
  community ports use `/points = 12`. We use the datasheet value; if the scan
  looks sheared, try the other divisor (`ANGLE_STEP_DIVISOR` in `protocol.py`).
- The 1°-bucket / "latest reading per bucket" scan model is a design choice, not
  a device property.
- The reported rotation speed (~3580 deg/s in earlier tests) was not
  re-measured here; the reader decodes it but does not depend on it.

**Not implemented / out of scope:** ROS 2 (`/scan`, `sensor_msgs/LaserScan`),
publishing, motion control, and any safety stop based on LiDAR. This is sensor
monitoring only.
