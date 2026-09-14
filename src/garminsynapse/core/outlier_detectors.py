"""Pluggable outlier detection & correction framework for FIT activity records.

Detectors operate on the list of `record` message dicts from a decoded FIT
file (see `core.fit_editor.FitActivity.records`) and are designed to be
sport-agnostic where possible. The framework intentionally avoids hardcoded
absolute thresholds (e.g. "negative altitude = bad") because those break for
legitimate cases like lakes sitting well above sea level, or tide-influenced
coastal water sports. Instead, detectors compare each sample against the
*activity's own* median/robust statistics.

Adding a new rule only requires implementing the `OutlierDetector` protocol
and registering an instance in `DEFAULT_DETECTORS`.
"""
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Sequence

logger = logging.getLogger(__name__)

EARTH_RADIUS_M = 6371000.0
SEMICIRCLE_TO_DEGREES = 180.0 / (2 ** 31)


@dataclass
class OutlierFinding:
    """A single flagged sample within an activity's record stream."""

    detector: str
    index: int
    field_name: str
    original_value: Any
    corrected_value: Any
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detector": self.detector,
            "index": self.index,
            "field": self.field_name,
            "original_value": self.original_value,
            "corrected_value": self.corrected_value,
            "reason": self.reason,
        }


class OutlierDetector(Protocol):
    """Contract every pluggable outlier rule must satisfy."""

    name: str

    def applies_to(self, sport: Optional[str]) -> bool:
        """Whether this detector is relevant for the given activity sport key."""
        ...

    def detect(self, records: Sequence[Dict[str, Any]]) -> List[OutlierFinding]:
        """Return findings without mutating `records`."""
        ...

    def correct(self, records: List[Dict[str, Any]], findings: List[OutlierFinding]) -> None:
        """Mutate `records` in place to apply the corrections described by `findings`."""
        ...


def _median(values: Sequence[float]) -> float:
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def _mad(values: Sequence[float], med: float) -> float:
    """Median absolute deviation, a robust (outlier-resistant) spread measure."""
    deviations = [abs(v - med) for v in values]
    return _median(deviations)


def _valid_indexed(records: Sequence[Dict[str, Any]], field_name: str) -> List[tuple]:
    out = []
    for i, rec in enumerate(records):
        v = rec.get(field_name)
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            out.append((i, float(v)))
    return out


def _interpolate_value(records: Sequence[Dict[str, Any]], field_name: str, index: int, outlier_indices: set) -> Optional[float]:
    """Linearly interpolate a field's value at `index` from the nearest valid
    (non-outlier) neighbors. Falls back to the nearer neighbor's value if only
    one side is available (e.g. outlier at the very start/end of the activity)."""
    before = None
    for i in range(index - 1, -1, -1):
        if i in outlier_indices:
            continue
        v = records[i].get(field_name)
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            before = (i, float(v))
            break
    after = None
    for i in range(index + 1, len(records)):
        if i in outlier_indices:
            continue
        v = records[i].get(field_name)
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            after = (i, float(v))
            break

    if before is not None and after is not None:
        bi, bv = before
        ai, av = after
        if ai == bi:
            return bv
        fraction = (index - bi) / (ai - bi)
        return bv + (av - bv) * fraction
    if before is not None:
        return before[1]
    if after is not None:
        return after[1]
    return None


class MedianAltitudeOutlierDetector:
    """Flags altitude/depth samples that deviate sharply from the activity's
    own median altitude, regardless of sign.

    This deliberately does NOT treat "negative" as inherently bad: a dive or
    snorkel session's depth readings can dip below a sea-level datum, and a
    lake session at high elevation could otherwise look "negative" relative
    to sea level. Instead we flag samples far from the activity's median,
    using a combination of a robust MAD-based z-score and a minimum absolute
    delta (so tiny natural terrain variation isn't flagged).
    """

    name = "median_altitude_outlier"
    FIELD_CANDIDATES = ("enhanced_altitude", "altitude")

    def __init__(self, mad_z_threshold: float = 6.0, min_delta_m: float = 50.0):
        self.mad_z_threshold = mad_z_threshold
        self.min_delta_m = min_delta_m

    def applies_to(self, sport: Optional[str]) -> bool:
        return True  # altitude/depth outliers can occur in any GPS/barometric activity

    def _field(self, records: Sequence[Dict[str, Any]]) -> Optional[str]:
        for f in self.FIELD_CANDIDATES:
            if any(f in rec for rec in records):
                return f
        return None

    def detect(self, records: Sequence[Dict[str, Any]]) -> List[OutlierFinding]:
        field_name = self._field(records)
        if not field_name:
            return []
        valid = _valid_indexed(records, field_name)
        if len(valid) < 5:
            return []

        values = [v for _, v in valid]
        med = _median(values)
        mad = _mad(values, med)
        # MAD can legitimately be 0 on very flat/indoor activities; fall back
        # to the fixed absolute delta threshold in that case.
        robust_scale = mad * 1.4826 if mad > 0 else 0.0

        findings = []
        for i, v in valid:
            delta = abs(v - med)
            z = delta / robust_scale if robust_scale > 0 else float("inf")
            if delta >= self.min_delta_m and z >= self.mad_z_threshold:
                findings.append(
                    OutlierFinding(
                        detector=self.name,
                        index=i,
                        field_name=field_name,
                        original_value=v,
                        corrected_value=None,  # filled in during correct()
                        reason=(
                            f"{field_name}={v:.1f}m deviates {delta:.1f}m from activity "
                            f"median {med:.1f}m (robust z-score {z:.1f})"
                        ),
                    )
                )
        return findings

    def correct(self, records: List[Dict[str, Any]], findings: List[OutlierFinding]) -> None:
        field_name = self._field(records)
        if not field_name:
            return
        outlier_indices = {f.index for f in findings if f.field_name == field_name}
        for f in findings:
            if f.field_name != field_name:
                continue
            new_val = _interpolate_value(records, field_name, f.index, outlier_indices)
            if new_val is None:
                new_val = _median([v for i, v in _valid_indexed(records, field_name) if i not in outlier_indices])
            f.corrected_value = round(new_val, 2)
            records[f.index][field_name] = f.corrected_value


class GpsSpeedHopDetector:
    """Flags GPS position samples that imply an implausible instantaneous
    speed (a "teleport") caused by a bad GPS fix, then corrects the position
    by interpolating between the nearest valid neighboring fixes.
    """

    name = "gps_speed_hop"

    def __init__(self, max_plausible_speed_mps: float = 12.0, mad_z_threshold: float = 8.0):
        # ~12 m/s (~43 km/h) covers all non-motorized activity types with margin;
        # combined with a robust z-score so faster legitimate sports (e.g.
        # cycling) don't get flagged just for being generally fast.
        self.max_plausible_speed_mps = max_plausible_speed_mps
        self.mad_z_threshold = mad_z_threshold

    def applies_to(self, sport: Optional[str]) -> bool:
        return True

    @staticmethod
    def _haversine_m(lat1_semi: int, lon1_semi: int, lat2_semi: int, lon2_semi: int) -> float:
        lat1 = math.radians(lat1_semi * SEMICIRCLE_TO_DEGREES)
        lon1 = math.radians(lon1_semi * SEMICIRCLE_TO_DEGREES)
        lat2 = math.radians(lat2_semi * SEMICIRCLE_TO_DEGREES)
        lon2 = math.radians(lon2_semi * SEMICIRCLE_TO_DEGREES)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(min(1.0, math.sqrt(a)))
        return EARTH_RADIUS_M * c

    def _positions(self, records: Sequence[Dict[str, Any]]) -> List[Optional[tuple]]:
        out = []
        for rec in records:
            lat = rec.get("position_lat")
            lon = rec.get("position_long")
            ts = rec.get("timestamp")
            if lat is not None and lon is not None and ts is not None:
                out.append((lat, lon, ts))
            else:
                out.append(None)
        return out

    def detect(self, records: Sequence[Dict[str, Any]]) -> List[OutlierFinding]:
        positions = self._positions(records)
        valid_idx = [i for i, p in enumerate(positions) if p is not None]
        if len(valid_idx) < 5:
            return []

        speeds: List[float] = []
        speed_by_index: Dict[int, float] = {}
        for a, b in zip(valid_idx, valid_idx[1:]):
            lat1, lon1, ts1 = positions[a]
            lat2, lon2, ts2 = positions[b]
            dt = (ts2 - ts1).total_seconds() if hasattr(ts2 - ts1, "total_seconds") else float(ts2 - ts1)
            if dt <= 0:
                continue
            dist = self._haversine_m(lat1, lon1, lat2, lon2)
            spd = dist / dt
            speeds.append(spd)
            # Attribute the speed spike to the *later* sample (the one whose
            # fix likely caused the jump).
            speed_by_index[b] = spd

        if len(speeds) < 5:
            return []

        med = _median(speeds)
        mad = _mad(speeds, med)
        robust_scale = mad * 1.4826 if mad > 0 else 0.0

        findings = []
        for idx, spd in speed_by_index.items():
            if spd < self.max_plausible_speed_mps:
                continue
            z = (spd - med) / robust_scale if robust_scale > 0 else float("inf")
            if z >= self.mad_z_threshold:
                lat, lon, _ = positions[idx]
                findings.append(
                    OutlierFinding(
                        detector=self.name,
                        index=idx,
                        field_name="position",
                        original_value={"position_lat": lat, "position_long": lon},
                        corrected_value=None,
                        reason=(
                            f"implied speed {spd:.1f} m/s at sample {idx} deviates sharply "
                            f"from activity median {med:.1f} m/s (robust z-score {z:.1f}) "
                            "-- likely a GPS location hop"
                        ),
                    )
                )
        return findings

    def correct(self, records: List[Dict[str, Any]], findings: List[OutlierFinding]) -> None:
        outlier_indices = {f.index for f in findings if f.field_name == "position"}
        for f in findings:
            if f.field_name != "position":
                continue
            new_lat = _interpolate_value(records, "position_lat", f.index, outlier_indices)
            new_lon = _interpolate_value(records, "position_long", f.index, outlier_indices)
            if new_lat is None or new_lon is None:
                continue
            new_lat, new_lon = int(round(new_lat)), int(round(new_lon))
            f.corrected_value = {"position_lat": new_lat, "position_long": new_lon}
            records[f.index]["position_lat"] = new_lat
            records[f.index]["position_long"] = new_lon


DEFAULT_DETECTORS: List[OutlierDetector] = [
    MedianAltitudeOutlierDetector(),
    GpsSpeedHopDetector(),
]


def run_all_detectors(
    records: List[Dict[str, Any]],
    sport: Optional[str] = None,
    detectors: Optional[Sequence[OutlierDetector]] = None,
) -> List[OutlierFinding]:
    """Run every applicable detector against `records`, returning combined
    findings without mutating `records`. Call `apply_corrections` separately
    to mutate once the caller has confirmed the preview."""
    active = detectors if detectors is not None else DEFAULT_DETECTORS
    findings: List[OutlierFinding] = []
    for detector in active:
        if not detector.applies_to(sport):
            continue
        try:
            findings.extend(detector.detect(records))
        except Exception as e:
            logger.warning(f"Outlier detector {getattr(detector, 'name', detector)} failed: {e}")
    return findings


def apply_corrections(
    records: List[Dict[str, Any]],
    findings: List[OutlierFinding],
    detectors: Optional[Sequence[OutlierDetector]] = None,
) -> None:
    """Mutate `records` in place, applying each detector's correction for its
    own findings. Safe to call with a findings list produced by
    `run_all_detectors` using the same detector set."""
    active = detectors if detectors is not None else DEFAULT_DETECTORS
    by_detector: Dict[str, List[OutlierFinding]] = {}
    for f in findings:
        by_detector.setdefault(f.detector, []).append(f)

    for detector in active:
        det_findings = by_detector.get(detector.name)
        if det_findings:
            detector.correct(records, det_findings)
