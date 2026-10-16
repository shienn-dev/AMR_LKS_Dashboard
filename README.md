# AMR LKS App

Aplikasi operator dan pengelolaan misi untuk proyek Autonomous Mobile Robot (AMR) LKS.

## Current Phase

Phase 1 — Dashboard prototype with simulated data only.

## Scope

- Operator dashboard
- Mission configuration and state management
- Robot health monitoring interface
- Vision and navigation monitoring interface
- Live LiDAR (STL-19P / LD19) monitoring over USB-serial (real hardware)
- Future integration with verified ROS 2 interfaces

## Safety

This prototype does not control a physical robot. Simulated status and actions must be clearly labeled. The LiDAR panel reads sensor data only; it never commands the robot.

## Running the prototype

Install dependencies once (requires internet the first time):

```bash
pip install -r requirements.txt
```

Launch the dashboard:

```bash
python run_dashboard.py            # http://127.0.0.1:8080
python run_dashboard.py --port 9000
# or, after `pip install -e .`:
python -m amr_dashboard
```

Then open the printed URL in a browser. The dashboard runs fully offline once
dependencies are installed.

## Live LiDAR (real hardware)

The dashboard can read the physical STL-19P / LD19 LiDAR over USB-serial and
shows a live scan panel, clearly labelled as real hardware and kept separate
from the simulated data. Reading runs on a dedicated background thread; the UI
never blocks on serial I/O. See `docs/lidar_integration.md` for details.

The port is configurable **without editing code**, via environment variables or
CLI flags (defaults: `/dev/ttyUSB0` @ `230400`):

```bash
python run_dashboard.py                                  # uses the defaults
python run_dashboard.py --lidar-port /dev/ttyUSB1        # override the port
AMR_LIDAR_PORT=/dev/ttyUSB1 AMR_LIDAR_BAUD=230400 python run_dashboard.py
python run_dashboard.py --no-lidar                       # disable the reader
```

Read the LiDAR for a few seconds from the command line (diagnostics):

```bash
python scripts/lidar_probe.py --seconds 5
```

`pyserial` is required for live reading. If it is missing, the dashboard still
starts and the LiDAR panel reports "unavailable" instead of failing.

## Tests and lint

```bash
python -m pytest -q          # unit tests (state model, validation, simulation)
python -m ruff check .       # lint
python scripts/smoke_dashboard.py   # start server + fetch '/' (HTTP 200)
```

## Layout

```text
src/amr_core/        state machine, mission model + validator, simulation, vision
src/amr_core/lidar/  real LiDAR: protocol (CRC/decoder), scan accumulator, reader
src/amr_dashboard/   NiceGUI UI (competition + development modes, LiDAR panel)
config/missions/     SAMPLE mission YAML (documentation of the on-disk format)
docs/                integration notes (device facts, assumptions, verification)
tests/               pytest unit tests
scripts/             dashboard smoke test + LiDAR probe
```