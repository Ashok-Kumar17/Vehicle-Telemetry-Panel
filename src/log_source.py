"""
log_source.py

Parses a candump-style CAN log file into a sequence of raw frames. Kept
deliberately separate from decoding (decoder.py) and from replay timing
(replayer.py) -- each of those three concerns changes for a different
reason, so they're three different files rather than one God-module.

Log line format expected (standard candump -L output):
    (1719500000.000000) can0 100#240C35034F550100
"""
import re

LOG_LINE_RE = re.compile(
    r"^\(([\d.]+)\)\s+(\S+)\s+([0-9A-Fa-f]+)#([0-9A-Fa-f]*)\s*$"
)


def parse_log_file(log_path: str):
    """Yields (timestamp: float, frame_id: int, data: bytes) for each valid line."""
    with open(log_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = LOG_LINE_RE.match(line)
            if not m:
                continue
            ts_str, _channel, id_str, data_str = m.groups()
            timestamp = float(ts_str)
            frame_id = int(id_str, 16)
            data = bytes.fromhex(data_str) if data_str else b""
            yield timestamp, frame_id, data
