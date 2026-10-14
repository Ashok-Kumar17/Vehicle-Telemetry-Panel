"""Measure how accurately the replay engine reproduces the log's original timing.

Run from the repository root:
    python scripts/bench_replay.py --speed 1

Reports per-frame lateness relative to the first frame (so log parsing time is
excluded), which is the jitter a dashboard viewer would actually see, plus the
final value -- if that stays close to the median, drift is not accumulating.
"""
import argparse
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.decoder import FrameDecoder  # noqa: E402
from src.log_source import parse_log_file  # noqa: E402
from src.replayer import CANReplayer  # noqa: E402


async def measure(log_path: str, dbc_path: str, speed: float) -> None:
    t0 = next(iter(parse_log_file(log_path)))[0]
    replayer = CANReplayer(log_path, FrameDecoder(dbc_path), speed=speed)

    lateness_ms = []
    start = time.monotonic()
    async for event in replayer.stream():
        target = (event["t"] - t0) / speed
        lateness_ms.append((time.monotonic() - start - target) * 1000.0)
    duration = time.monotonic() - start

    base = lateness_ms[0]
    jitter = sorted(x - base for x in lateness_ms)
    pct = lambda q: jitter[int(q * (len(jitter) - 1))]  # noqa: E731
    print(f"speed {speed}x | {len(jitter)} frames in {duration:.2f} s "
          f"({len(jitter) / duration:.0f} frames/s)")
    print(f"jitter ms  p50 {pct(0.50):.2f} | p95 {pct(0.95):.2f} | "
          f"p99 {pct(0.99):.2f} | max {jitter[-1]:.2f} | final {lateness_ms[-1] - base:.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--log", default="data/demo_drive.log")
    parser.add_argument("--dbc", default="dbc/vehicle_demo.dbc")
    args = parser.parse_args()
    asyncio.run(measure(args.log, args.dbc, args.speed))
