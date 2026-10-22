# AMR LKS App

Aplikasi operator dan pengelolaan misi untuk proyek Autonomous Mobile Robot (AMR) LKS.

## Current phase

Phase 1 — operator dashboard. Mission/state/log/vision panels still use simulated
data; **two panels talk to real hardware**: the live LiDAR (read-only) and the
chassis (opt-in, drives the robot only with `--chassis-live`).

## Scope

- Operator dashboard
- Mission configuration and state management
- Robot health monitoring interface
- Vision and navigation monitoring interface
- Live LiDAR (STL-19P / LD19) monitoring over USB-serial (real hardware)
- Live chassis control over USB-serial, hold-to-move (real hardware, opt-in)
- Future integration with verified ROS 2 interfaces

## Safety

The dashboard does **not** drive the robot unless you pass `--chassis-live`.
Without that flag every chassis command is validated and clamped but never sent,
and the robot cannot move. The LiDAR panel only reads sensor data; it never
commands the robot. Keep the physical E-stop within reach whenever the chassis
is live.

---

## Running the dashboard

All commands below assume the project root:

```bash
cd ~/AMRTestLander/AMR_LKS_Dashboard
```

### 1. Install dependencies (once, needs internet)

The project runs from a dedicated virtualenv at `~/AMRTestLander/.venv`:

```bash
python3 -m venv ~/AMRTestLander/.venv
~/AMRTestLander/.venv/bin/pip install -r requirements.txt
```

Alternatively, install the package itself (gives you `python -m amr_dashboard`):

```bash
~/AMRTestLander/.venv/bin/pip install -e .
```

### 2. Start it

```bash
~/AMRTestLander/.venv/bin/python run_dashboard.py
```

The server prints `NiceGUI ready to go on http://127.0.0.1:8080`. Open that URL.
Once dependencies are installed the dashboard runs fully offline.

### 3. Reach it from the laptop

The default bind address is `127.0.0.1`, so the page is only reachable on the Pi
itself. To open it from another machine on the school LAN:

```bash
~/AMRTestLander/.venv/bin/python run_dashboard.py --host 0.0.0.0
```

then browse to `http://<ip-pi>:8080` (check the current IP with `hostname -I` —
it comes from DHCP and does change). **Do not** expose this port to the internet.

### Flags

| Flag | Default | Meaning |
| --- | --- | --- |
| `--host` | `127.0.0.1` | bind address; `0.0.0.0` to allow LAN access |
| `--port` | `8080` | HTTP port |
| `--reload` | off | auto-reload on file changes (development) |
| `--lidar-port` | `$AMR_LIDAR_PORT` or `/dev/ttyUSB0` | LiDAR serial port |
| `--lidar-baud` | `$AMR_LIDAR_BAUD` or `230400` | LiDAR baud rate |
| `--no-lidar` | off | do not open the LiDAR port at all |
| `--chassis-port` | `/dev/ttyACM0` | STM32 chassis serial port |
| `--chassis-live` | off | **drive the real robot** (see below) |

```bash
# no LiDAR attached
~/AMRTestLander/.venv/bin/python run_dashboard.py --no-lidar

# LiDAR on a different port
~/AMRTestLander/.venv/bin/python run_dashboard.py --lidar-port /dev/ttyUSB1
AMR_LIDAR_PORT=/dev/ttyUSB1 AMR_LIDAR_BAUD=230400 ~/AMRTestLander/.venv/bin/python run_dashboard.py

# different HTTP port
~/AMRTestLander/.venv/bin/python run_dashboard.py --port 9000
```

### Driving the robot (live chassis)

```bash
~/AMRTestLander/.venv/bin/python run_dashboard.py --chassis-live --chassis-port /dev/ttyACM0
```

This is the single switch that makes the dashboard actuator-facing. Start-up
prints a loud warning and the chassis panel becomes hold-to-move: the robot
moves while a direction button is held (maju / mundur / kiri / kanan / putar)
and stops when it is released. Fail-safes: browser heartbeat (0.8 s timeout),
control lease per session, software E-stop latch, and the board watchdog. The
status bar reports the measured stream rate, the largest gap between frames, the
frame count and the hold time — the stream figures are what separate "the wheels
stutter" from "frames were dropped and the board's watchdog cut the motors".

Speed slider range is **0.06 – 0.19 m/s**, and 0.19 m/s is the highest value
ever measured on this robot — it is a hard cap, not a suggestion.

Sign conventions, as far as the floor has confirmed them:

| Direction | Status |
| --- | --- |
| Forward / backward | verified on the floor |
| Yaw left / right | verified on the floor |
| Strafe left / right | **was inverted**, corrected in `kinematics.LATERAL_SIGN = -1`, **not yet re-tested** |

So do not treat "kiri"/"kanan" as trusted until that correction has been driven
on the floor. Keep the robot's own watchdog as the last line: it stops the
motors when frames stop arriving, independent of anything in the browser.

### Two dashboards, one robot

Never run two dashboard processes at once. The STM32 USB CDC port does not
enforce exclusive access, so a second process can write motor frames to the same
board even though the web port fails to bind. The opener refuses to open a
chassis port already held by another process, and a bind failure is reported as
a fixable message instead of a traceback:

```bash
fuser -v 8080/tcp     # find the old dashboard
fuser -k 8080/tcp     # stop it
```

Note that `git pull` does not affect a running process: the dashboard keeps
executing the old code until it is stopped and started again.

### Diagnostics from the command line

```bash
~/AMRTestLander/.venv/bin/python scripts/lidar_probe.py --seconds 5
```

`pyserial` is required for live reading. If it is missing, the dashboard still
starts and the LiDAR panel reports "unavailable" instead of failing.

---

## Tests and lint

```bash
cd ~/AMRTestLander/AMR_LKS_Dashboard
~/AMRTestLander/.venv/bin/python -m pytest -q        # unit tests (currently 379 passed)
~/AMRTestLander/.venv/bin/ruff check .               # lint (E,F,I,UP,B; line-length 100)
~/AMRTestLander/.venv/bin/python scripts/smoke_dashboard.py   # server + GET '/' (HTTP 200, exit 0)
```

## Layout

```text
src/amr_core/            state machine, mission model + validator, simulation, vision
src/amr_core/lidar/      real LiDAR: protocol (CRC/decoder), scan accumulator, reader
src/amr_core/robot/      chassis: kinematics, STM32 protocol/frames, serial adapter,
                         motion guard (lease + heartbeat), safety limits
src/amr_dashboard/       NiceGUI UI (competition + development modes, LiDAR panel,
                         chassis hold-to-move panel + transport)
config/missions/         SAMPLE mission YAML (documentation of the on-disk format)
docs/                    integration notes (device facts, assumptions, verification)
tests/                   pytest unit tests
scripts/                 dashboard smoke test, LiDAR probe, wheel test, pattern helpers
```

## Further reading

- `docs/robot_integration.md` — what is verified on this specific unit
- `docs/rencana_chassis_live.md` — chassis activation plan and the G1 sign gate
- `docs/lidar_integration.md` — LiDAR protocol and wiring notes
- `docs/CHANGELOG_DEV.md` — chronological development log
