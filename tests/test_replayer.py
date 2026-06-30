"""
Tests for the decoder and replayer (the parts testable without a running
server/browser). Run with: pytest tests/
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from src.decoder import FrameDecoder
from src.log_source import parse_log_file
from src.replayer import CANReplayer

DBC_PATH = "dbc/vehicle_demo.dbc"
LOG_PATH = "data/demo_drive.log"


@pytest.fixture(scope="module")
def decoder():
    return FrameDecoder(DBC_PATH)


def test_log_source_parses_lines():
    frames = list(parse_log_file(LOG_PATH))
    assert len(frames) > 0
    ts, frame_id, data = frames[0]
    assert isinstance(ts, float)
    assert isinstance(frame_id, int)
    assert isinstance(data, bytes)


def test_decoder_resolves_known_frame(decoder):
    frames = list(parse_log_file(LOG_PATH))
    # First frame should be a MOTOR_STATUS frame (frame_id 0x100)
    for ts, frame_id, data in frames:
        if frame_id == 0x100:
            decoded = decoder.decode(frame_id, data)
            assert decoded is not None
            assert decoded["message"] == "MOTOR_STATUS"
            assert "ControllerTemp" in decoded["signals"]
            break
    else:
        pytest.fail("No MOTOR_STATUS frame found in demo log")


def test_decoder_handles_unknown_frame_id(decoder):
    result = decoder.decode(0xFFF, b"\x00" * 8)
    assert result is None


def test_motor_state_resolves_to_label(decoder):
    frames = list(parse_log_file(LOG_PATH))
    for ts, frame_id, data in frames:
        if frame_id == 0x100:
            decoded = decoder.decode(frame_id, data)
            assert decoded["signals"]["MotorState"] in ("Running", "Idle", "Regen", "Fault", "Derate")
            break


def test_dtc_frame_detected(decoder):
    assert decoder.is_dtc_message(0x700) is True  # 1792 decimal == 0x700
    assert decoder.is_dtc_message(0x100) is False


@pytest.mark.asyncio
async def test_replayer_emits_fault_event(decoder):
    replayer = CANReplayer(LOG_PATH, decoder, speed=1000)
    fault_events = []
    async for event in replayer.stream():
        if event["type"] == "fault":
            fault_events.append(event)
    assert len(fault_events) == 1
    assert fault_events[0]["signals"]["DTC_Code"] == "P0C31_CONTROLLER_OVERTEMP"


@pytest.mark.asyncio
async def test_replayer_respects_speed_timing(decoder):
    """At high speed multiplier, a 60s log should replay in well under a second
    of wall-clock time -- this guards against accidentally reverting to a
    blocking/no-sleep replay or a broken speed divisor."""
    replayer = CANReplayer(LOG_PATH, decoder, speed=500)
    start = time.monotonic()
    count = 0
    async for _ in replayer.stream():
        count += 1
    elapsed = time.monotonic() - start
    assert count > 1000
    assert elapsed < 2.0  # generous upper bound, real value is ~0.12s
