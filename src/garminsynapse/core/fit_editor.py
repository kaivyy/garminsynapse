"""FIT activity file read-modify-write pipeline built on the official garmin_fit_sdk.

Garmin Connect has no API to patch individual metric samples inside an
already-uploaded activity. The only way to correct bad data (e.g. a GPS
"teleport" spike, or an altitude/depth outlier) is to:

    1. Download the original FIT file
    2. Decode it into editable messages
    3. Mutate the offending `record` messages in place
    4. Re-encode a new FIT file
    5. Delete the original activity and upload the corrected file

This module handles steps 2-4. Because the FIT format allows manufacturers
to embed proprietary/undocumented message types (e.g. dive-computer-specific
messages), a full byte-for-byte round trip isn't always possible with the
public SDK profile. `FitActivity.encode()` therefore degrades gracefully:
any message type or field the SDK's Profile doesn't recognize is dropped
(not fatal) and reported back via `FitEditReport`, so callers can surface a
clear warning before an upload is confirmed.
"""
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from garmin_fit_sdk import Decoder, Encoder, Stream

logger = logging.getLogger(__name__)

# Standard FIT global message numbers we care about (see FIT SDK Profile.xlsx).
MESG_NUM_RECORD = 20
MESG_NUM_LAP = 19
MESG_NUM_SESSION = 18
MESG_NUM_SPORT = 12


@dataclass
class FitEditReport:
    """Summary of any fidelity loss incurred while re-encoding a FIT file."""

    dropped_mesg_counts: Dict[int, int] = field(default_factory=dict)

    @property
    def has_losses(self) -> bool:
        return bool(self.dropped_mesg_counts)

    def summary(self) -> str:
        if not self.has_losses:
            return "No data loss detected while re-encoding this FIT file."
        parts = [f"message type #{num} (x{count})" for num, count in sorted(self.dropped_mesg_counts.items())]
        return (
            "Re-encoding will drop these unsupported/manufacturer-specific "
            "FIT messages: " + ", ".join(parts) + ". Standard records, laps, "
            "and session summaries are preserved."
        )


class FitActivity:
    """Loads a FIT activity file into an editable, ordered message stream."""

    def __init__(self, raw_bytes: bytes):
        self._raw_bytes = raw_bytes
        # Ordered list of [mesg_num, mesg_dict]; dicts are mutated in place by
        # detectors/correctors and re-used directly during encode() so no
        # separate "sync back" step is needed.
        self._messages: List[List[Any]] = []
        self._decoded: Dict[str, List[Dict[str, Any]]] = {}
        self._decode_errors: List[Any] = []
        self._load()

    def _load(self) -> None:
        def listener(mesg_num, mesg):
            self._messages.append([mesg_num, dict(mesg)])

        stream = Stream.from_byte_array(bytearray(self._raw_bytes))
        decoder = Decoder(stream)
        self._decoded, self._decode_errors = decoder.read(mesg_listener=listener)
        if self._decode_errors:
            logger.warning(f"FIT decode reported {len(self._decode_errors)} error(s): {self._decode_errors}")

    @property
    def records(self) -> List[Dict[str, Any]]:
        """Editable list of `record` message dicts (same objects held internally)."""
        return [mesg for mesg_num, mesg in self._messages if mesg_num == MESG_NUM_RECORD]

    @property
    def laps(self) -> List[Dict[str, Any]]:
        return [mesg for mesg_num, mesg in self._messages if mesg_num == MESG_NUM_LAP]

    @property
    def sessions(self) -> List[Dict[str, Any]]:
        return [mesg for mesg_num, mesg in self._messages if mesg_num == MESG_NUM_SESSION]

    def sport(self) -> Optional[str]:
        """Best-effort lookup of the activity's sport key (e.g. 'hiking', 'surfing_v2')."""
        for mesg in self.sessions:
            if mesg.get("sport"):
                return mesg.get("sport")
        for mesg_num, mesg in self._messages:
            if mesg_num == MESG_NUM_SPORT and mesg.get("sport"):
                return mesg.get("sport")
        return None

    @staticmethod
    def _sanitize(mesg: Dict[str, Any]) -> Dict[str, Any]:
        """Strip NaN float values.

        The FIT SDK's Encoder cannot serialize NaN into a float32 field; in
        FIT semantics a field simply being absent means "invalid/no data",
        which is exactly what upstream `garmin_fit_sdk.Decoder` returns as
        NaN for fields like `total_grit`/`avg_flow` when a device didn't
        record them.
        """
        return {k: v for k, v in mesg.items() if not (isinstance(v, float) and math.isnan(v))}

    def encode(self) -> Tuple[bytes, FitEditReport]:
        """Re-encode the (possibly edited) message stream into a new FIT file."""
        encoder = Encoder()
        report = FitEditReport()
        for mesg_num, mesg in self._messages:
            try:
                encoder.on_mesg(mesg_num, self._sanitize(mesg))
            except ValueError as e:
                report.dropped_mesg_counts[mesg_num] = report.dropped_mesg_counts.get(mesg_num, 0) + 1
                logger.debug(f"Dropped mesg_num={mesg_num} during FIT re-encode: {e}")
        data = encoder.close()
        return data, report


def load_fit(raw_bytes: bytes) -> FitActivity:
    """Convenience factory mirroring the module's primary entry point."""
    return FitActivity(raw_bytes)
