# CAN Telemetry Dashboard

A real-time CAN bus telemetry server: replays a CAN log at (a multiple of)
real speed, decodes signals against a DBC as they "arrive," and streams them
over a WebSocket to a live-updating browser dashboard. Built as a companion
to [can-diagnostic-assistant](https://github.com/Ashok-Kumar17/can-diagnostic-assistant)
-- that project answers natural-language questions about a completed log
after the fact; this one is about watching a vehicle's signals live as they
happen, the way a real telemetry dashboard would during a competition or
field test.

No LLM involved here -- this is a backend/systems project: async I/O,
WebSockets, real-time data pipelines, and a from-scratch frontend.

## Why this exists

Team Anveshak (and most rover/EV competitions) need to watch live signals
during a run -- motor temps, battery state, fault codes -- without staring
at raw hex in a terminal. This is a from-scratch version of that kind of
base-station telemetry view, built against a synthetic demo dataset so it's
fully runnable without any proprietary hardware logs.

## Architecture

```
CAN log (.log, candump format) + DBC file
        │
        ▼
  log_source.py  -- parses raw (timestamp, frame_id, data) tuples
        ▼
  replayer.py    -- async generator: re-plays frames respecting original
        │            inter-frame timing (scaled by a speed multiplier),
        │            with wall-clock drift correction for long replays
        ▼
  decoder.py     -- decodes each frame against the DBC as it's replayed
        ▼
  server.py      -- FastAPI WebSocket endpoint streams decoded JSON events
        │            to the browser in real time
        ▼
  static/index.html -- Chart.js dashboard: live-updating signal panels,
                        a rolling time window, and a fault banner that
                        lights up the instant a DTC event streams in
```

A REST endpoint (`/api/signals`) exposes the DBC's signal layout so the
frontend doesn't hardcode signal names -- swap in a different DBC and the
metadata endpoint reflects it automatically (the chart *panels* are
currently hand-grouped in `index.html` for visual layout, but the available
signal list itself is fully dynamic).

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
uvicorn src.server:app --reload
```

Then open **http://127.0.0.1:8000** in a browser, pick a replay speed, and
click "Start Replay."

## Demo scenario

Uses the same synthetic fault scenario as `can-diagnostic-assistant`: ~60
seconds of driving where sustained high throttle causes the motor controller
to overheat, trips a `P0C31_CONTROLLER_OVERTEMP` DTC at t≈41.6s, and the
drivetrain enters a derate state while cooling. Watch the Motor & Controller
Temp panel climb steadily, then the fault banner fire right as it crosses
the thermal limit.

## Using your own CAN logs

Set two environment variables before starting the server:

```bash
export CAN_DBC_PATH=/path/to/your.dbc
export CAN_LOG_PATH=/path/to/your.log
uvicorn src.server:app --reload
```

Log format must be candump `-L` style text lines:
```
(1719500000.000000) can0 100#240C35034F550100
```

## A note on the WebSocket design

Each browser connection currently gets its own independent replay starting
from the beginning of the log -- opening two tabs starts two separate
playbacks rather than both watching one shared live feed. That's a
deliberate simplification for a single-vehicle demo/portfolio project. A
production telemetry system serving an actual live CAN bus to multiple
viewers would more likely run one replay/capture loop and broadcast its
events to all connected WebSocket clients via a shared queue or pub/sub --
worth mentioning if asked about productionizing this further.

## Testing

```bash
pytest tests/
```

Covers the decoder and replayer layer, including a timing test that asserts
the replay actually respects the speed multiplier against wall-clock time
(catches regressions like accidentally reverting to a blocking, no-sleep
replay).

## Project structure

```
dbc/                  DBC file defining the CAN bus signal layout
data/                 Synthetic log generator + generated demo log
src/
  log_source.py       Raw candump-log line parsing
  decoder.py          DBC-based frame decoding
  replayer.py         Async, real-time-paced log replay
  server.py           FastAPI app: WebSocket stream + REST metadata endpoint
static/
  index.html          Chart.js live dashboard frontend
tests/                pytest suite for decoder + replayer
```
