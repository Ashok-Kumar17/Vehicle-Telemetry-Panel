"""
decoder.py

Loads a DBC and decodes individual raw CAN frames into named signals. This is
intentionally frame-at-a-time (not a bulk DataFrame like a batch-analysis tool
would use) because the telemetry server decodes frames one-by-one as they
arrive in real time off the replayer.
"""
import cantools


class FrameDecoder:
    def __init__(self, dbc_path: str):
        self.db = cantools.database.load_file(dbc_path)
        self._id_to_message = {msg.frame_id: msg for msg in self.db.messages}

    def decode(self, frame_id: int, data: bytes) -> dict | None:
        """
        Returns {"message": str, "signals": {name: value}} or None if the
        frame_id isn't in the DBC (unknown bus traffic -- not an error) or
        the frame fails to decode (truncated/corrupt -- also not fatal).
        """
        message = self._id_to_message.get(frame_id)
        if message is None:
            return None
        try:
            decoded = message.decode(data, decode_choices=True)
        except Exception:
            return None
        return {
            "message": message.name,
            "signals": {k: self._to_jsonable(v) for k, v in decoded.items()},
        }

    def is_dtc_message(self, frame_id: int, dtc_message_name: str = "DTC_REPORT") -> bool:
        message = self._id_to_message.get(frame_id)
        return message is not None and message.name == dtc_message_name

    @staticmethod
    def _to_jsonable(value):
        """cantools returns NamedSignalValue for VAL_-table signals -- coerce to str/float."""
        if hasattr(value, "value"):  # NamedSignalValue wraps both .value and a label
            return str(value)
        try:
            return float(value)
        except (TypeError, ValueError):
            return str(value)
