# AMR LKS App

Aplikasi operator dan pengelolaan misi untuk proyek Autonomous Mobile Robot (AMR) LKS.

## Current Phase

Phase 1 — Dashboard prototype with simulated data only.

## Scope

- Operator dashboard
- Mission configuration and state management
- Robot health monitoring interface
- Vision and navigation monitoring interface
- Future integration with verified ROS 2 interfaces

## Safety

This prototype does not control a physical robot. Simulated status and actions must be clearly labeled.

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

## Tests and lint

```bash
python -m pytest -q          # unit tests (state model, validation, simulation)
python -m ruff check .       # lint
python scripts/smoke_dashboard.py   # start server + fetch '/' (HTTP 200)
```

## Layout

```text
src/amr_core/        state machine, mission model + validator, simulation, vision
src/amr_dashboard/   NiceGUI UI (competition + development modes)
config/missions/     SAMPLE mission YAML (documentation of the on-disk format)
tests/               pytest unit tests
scripts/             dashboard smoke test
```