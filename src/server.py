"""
server.py

FastAPI app exposing:
    GET  /            -- serves the dashboard (static/index.html)
    GET  /api/signals -- lists every signal name available in the loaded DBC
                         (so the frontend can build chart panels without
                         hardcoding signal names)
    WS   /ws?speed=N  -- streams decoded CAN events in real time, replayed
                         at N times the original log speed (default 1.0)

Each WebSocket connection gets its own independent replay from the start of
the log -- opening a second browser tab starts a fresh playback rather than
joining an existing one. That's a deliberate simplification for a portfolio
project; a production telemetry system would more likely broadcast one live
feed to many subscribers (see README for that distinction).
"""
import asyncio
import json
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.decoder import FrameDecoder
from src.replayer import CANReplayer

DBC_PATH = os.environ.get("CAN_DBC_PATH", "dbc/vehicle_demo.dbc")
LOG_PATH = os.environ.get("CAN_LOG_PATH", "data/demo_drive.log")

app = FastAPI(title="CAN Telemetry Dashboard")

_decoder = FrameDecoder(DBC_PATH)


@app.get("/api/signals")
def list_signals():
    """Returns {message_name: [signal_name, ...]} so the frontend can build
    chart panels dynamically instead of hardcoding signal names twice."""
    return {msg.name: [s.name for s in msg.signals] for msg in _decoder.db.messages}


@app.websocket("/ws")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    speed = float(websocket.query_params.get("speed", "1.0"))
    replayer = CANReplayer(LOG_PATH, _decoder, speed=speed)

    try:
        async for event in replayer.stream():
            await websocket.send_text(json.dumps(event))
        await websocket.send_text(json.dumps({"type": "end_of_log"}))
    except WebSocketDisconnect:
        # Client closed the tab mid-replay -- not an error, just stop streaming.
        pass


# Serve the dashboard frontend. Mounted last so it doesn't shadow /api or /ws.
app.mount("/", StaticFiles(directory="static", html=True), name="static")
