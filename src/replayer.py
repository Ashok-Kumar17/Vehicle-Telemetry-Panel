"""
replayer.py

Replays a CAN log at (a multiple of) real speed, decoding each frame as it
"arrives" and yielding it. This is what makes the dashboard feel like a live
vehicle feed instead of a progress bar dumping a file -- the inter-frame
delays from the original capture are preserved (scaled by `speed`), so a
20Hz signal genuinely renders as a 20Hz-updating chart line.

Async by design: this needs to run concurrently with a FastAPI WebSocket
sending loop without blocking the event loop on file I/O or sleeps.
"""
import asyncio
import time

from src.decoder import FrameDecoder
from src.log_source import parse_log_file


class CANReplayer:
    def __init__(self, log_path: str, decoder: FrameDecoder, speed: float = 1.0):
        self.log_path = log_path
        self.decoder = decoder
        self.speed = speed

    async def stream(self):
        """
        Async generator yielding decoded events in real time:
            {"type": "signal", "t": float, "message": str, "signals": {...}}
            {"type": "fault",  "t": float, "message": str, "signals": {...}}
        Sleeps between frames to match the original log's timing (divided by
        `speed`), based on wall-clock elapsed time rather than naively
        summing per-frame deltas -- this avoids cumulative drift on a long
        replay, since decode/send time on each frame is subtracted out.
        """
        frames = list(parse_log_file(self.log_path))
        if not frames:
            return

        playback_start_wall = time.monotonic()
        log_start_ts = frames[0][0]

        for timestamp, frame_id, data in frames:
            target_elapsed = (timestamp - log_start_ts) / self.speed
            actual_elapsed = time.monotonic() - playback_start_wall
            wait = target_elapsed - actual_elapsed
            if wait > 0:
                await asyncio.sleep(wait)

            decoded = self.decoder.decode(frame_id, data)
            if decoded is None:
                continue

            event_type = "fault" if self.decoder.is_dtc_message(frame_id) else "signal"
            yield {
                "type": event_type,
                "t": round(timestamp, 3),
                "message": decoded["message"],
                "signals": decoded["signals"],
            }
