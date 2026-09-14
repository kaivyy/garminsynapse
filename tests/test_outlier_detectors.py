"""Unit tests for the pluggable outlier detection & correction framework."""
import datetime

from garminsynapse.core.outlier_detectors import (
    GpsSpeedHopDetector,
    MedianAltitudeOutlierDetector,
    apply_corrections,
    run_all_detectors,
)


def _ts(offset_s: int) -> datetime.datetime:
    return datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc) + datetime.timedelta(seconds=offset_s)


def _flat_records(n: int, altitude: float = 1200.0) -> list:
    """Records around a stable median altitude, e.g. a lake sitting at elevation."""
    return [
        {
            "timestamp": _ts(i),
            "position_lat": 500000000 + i * 100,
            "position_long": 100000000 + i * 100,
            "enhanced_altitude": altitude + (i % 3) * 0.2,  # tiny natural noise
        }
        for i in range(n)
    ]


class TestMedianAltitudeOutlierDetector:
    def test_flags_sample_far_from_median(self):
        records = _flat_records(20, altitude=1200.0)
        records[10]["enhanced_altitude"] = -50.0  # spurious spike, unrelated to sign

        detector = MedianAltitudeOutlierDetector()
        findings = detector.detect(records)

        assert len(findings) == 1
        assert findings[0].index == 10
        assert findings[0].field_name == "enhanced_altitude"

    def test_does_not_flag_legitimate_negative_values_relative_to_own_median(self):
        # A dive/depth activity whose median is already negative (below datum).
        records = [
            {
                "timestamp": _ts(i),
                "enhanced_altitude": -10.0 + (i % 3) * 0.1,
            }
            for i in range(20)
        ]
        detector = MedianAltitudeOutlierDetector()
        findings = detector.detect(records)
        assert findings == []

    def test_does_not_flag_lake_at_elevation_just_because_sea_level_is_zero(self):
        # Regression test for the specific scenario the user raised: a lake
        # at 1200m altitude should not have its legitimate readings flagged
        # just because they're far from 0 (sea level).
        records = _flat_records(30, altitude=1200.0)
        detector = MedianAltitudeOutlierDetector()
        findings = detector.detect(records)
        assert findings == []

    def test_correct_interpolates_from_neighbors(self):
        records = _flat_records(10, altitude=500.0)
        records[5]["enhanced_altitude"] = 5000.0

        detector = MedianAltitudeOutlierDetector()
        findings = detector.detect(records)
        assert len(findings) == 1

        detector.correct(records, findings)
        assert 490.0 < records[5]["enhanced_altitude"] < 510.0
        assert findings[0].corrected_value == records[5]["enhanced_altitude"]

    def test_ignores_short_activities(self):
        records = _flat_records(3, altitude=500.0)
        records[1]["enhanced_altitude"] = 9999.0
        detector = MedianAltitudeOutlierDetector()
        assert detector.detect(records) == []


class TestGpsSpeedHopDetector:
    def _walking_track(self, n: int) -> list:
        # ~1 m per second of lat drift is a slow walk; keep well under the
        # detector's plausible-speed cap.
        return [
            {
                "timestamp": _ts(i),
                "position_lat": 500000000 + i * 20,
                "position_long": 100000000 + i * 20,
            }
            for i in range(n)
        ]

    def test_flags_teleport_spike(self):
        records = self._walking_track(20)
        # Massive jump then jump back -> classic bad-GPS-fix "hop".
        records[10]["position_lat"] += 5_000_000
        records[10]["position_long"] += 5_000_000

        detector = GpsSpeedHopDetector()
        findings = detector.detect(records)

        assert any(f.index == 10 for f in findings)

    def test_does_not_flag_steady_walking_pace(self):
        records = self._walking_track(20)
        detector = GpsSpeedHopDetector()
        findings = detector.detect(records)
        assert findings == []

    def test_correct_interpolates_position(self):
        records = self._walking_track(20)
        original_lat, original_lon = records[10]["position_lat"], records[10]["position_long"]
        records[10]["position_lat"] += 5_000_000
        records[10]["position_long"] += 5_000_000

        detector = GpsSpeedHopDetector()
        findings = detector.detect(records)
        detector.correct(records, findings)

        assert abs(records[10]["position_lat"] - original_lat) < 50
        assert abs(records[10]["position_long"] - original_lon) < 50


class TestFrameworkIntegration:
    def test_run_all_detectors_and_apply_corrections(self):
        records = _flat_records(20, altitude=1200.0)
        records[8]["enhanced_altitude"] = -9999.0
        records[12]["position_lat"] += 5_000_000
        records[12]["position_long"] += 5_000_000

        findings = run_all_detectors(records, sport="hiking")
        assert len(findings) >= 2

        apply_corrections(records, findings)

        assert records[8]["enhanced_altitude"] > 1000.0
        expected_lat = 500000000 + 12 * 100
        assert abs(records[12]["position_lat"] - expected_lat) < 50

    def test_applies_to_gate_can_exclude_detector(self):
        class NeverApplies(MedianAltitudeOutlierDetector):
            def applies_to(self, sport):
                return False

        records = _flat_records(20, altitude=1200.0)
        records[5]["enhanced_altitude"] = -9999.0

        findings = run_all_detectors(records, sport="hiking", detectors=[NeverApplies()])
        assert findings == []
