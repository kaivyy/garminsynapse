"""Unit tests for the FIT read-modify-write pipeline (core.fit_editor)."""
import datetime
import math

from garmin_fit_sdk import Encoder

from garminsynapse.core.fit_editor import FitActivity, FitEditReport, load_fit


def _build_synthetic_fit(num_records: int = 5, sport: str = "hiking") -> bytes:
    """Build a minimal valid FIT activity file for tests, without depending
    on any real user data."""
    enc = Encoder()
    enc.on_mesg(0, {
        "type": "activity",
        "manufacturer": "garmin",
        "product": 1,
        "time_created": datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
    })
    for i in range(num_records):
        enc.on_mesg(20, {
            "timestamp": datetime.datetime(2024, 1, 1, 0, 0, i, tzinfo=datetime.timezone.utc),
            "position_lat": 500000000 + i * 1000,
            "position_long": 100000000 + i * 1000,
            "enhanced_altitude": 100.0 + i,
            "heart_rate": 120 + i,
        })
    enc.on_mesg(18, {
        "timestamp": datetime.datetime(2024, 1, 1, 0, 0, num_records, tzinfo=datetime.timezone.utc),
        "start_time": datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        "sport": sport,
        "message_index": 0,
    })
    return enc.close()


def test_load_fit_parses_records_and_sport():
    raw = _build_synthetic_fit(num_records=5, sport="hiking")
    activity = load_fit(raw)

    assert len(activity.records) == 5
    assert activity.sport() == "hiking"
    assert activity.records[0]["enhanced_altitude"] == 100.0


def test_encode_round_trip_preserves_unedited_records():
    raw = _build_synthetic_fit(num_records=5)
    activity = load_fit(raw)

    data, report = activity.encode()
    assert isinstance(data, (bytes, bytearray))
    assert isinstance(report, FitEditReport)

    reloaded = load_fit(data)
    assert len(reloaded.records) == 5
    for original, roundtripped in zip(activity.records, reloaded.records):
        assert original["enhanced_altitude"] == roundtripped["enhanced_altitude"]
        assert original["position_lat"] == roundtripped["position_lat"]
        assert original["heart_rate"] == roundtripped["heart_rate"]


def test_mutating_records_in_place_is_reflected_after_encode():
    raw = _build_synthetic_fit(num_records=5)
    activity = load_fit(raw)

    # Mutate directly, as an outlier corrector would.
    activity.records[2]["enhanced_altitude"] = 999.0

    data, _report = activity.encode()
    reloaded = load_fit(data)

    assert reloaded.records[2]["enhanced_altitude"] == 999.0
    # Unedited neighbors are untouched.
    assert reloaded.records[1]["enhanced_altitude"] == 101.0
    assert reloaded.records[3]["enhanced_altitude"] == 103.0


def test_sanitize_strips_nan_fields_instead_of_raising():
    raw = _build_synthetic_fit(num_records=3)
    activity = load_fit(raw)
    # Simulate a device field that legitimately has no data (NaN in FIT SDK output).
    activity.records[0]["total_grit"] = float("nan")

    data, report = activity.encode()
    assert isinstance(data, (bytes, bytearray))
    assert len(data) > 0

    reloaded = load_fit(data)
    assert "total_grit" not in reloaded.records[0] or not math.isnan(reloaded.records[0].get("total_grit", 0))


def test_unknown_mesg_type_is_dropped_and_reported_not_fatal():
    raw = _build_synthetic_fit(num_records=3)
    activity = load_fit(raw)
    # Inject a manufacturer-specific message number the SDK profile won't recognize.
    activity._messages.append([288, {"some_field": 1}])

    data, report = activity.encode()
    assert isinstance(data, (bytes, bytearray))
    assert report.has_losses is True
    assert 288 in report.dropped_mesg_counts
    assert "message type #288" in report.summary()


def test_report_summary_reports_no_losses_when_clean():
    raw = _build_synthetic_fit(num_records=3)
    activity = load_fit(raw)
    _data, report = activity.encode()
    assert report.has_losses is False
    assert "No data loss" in report.summary()
