"""Unit tests for the activity outlier preview/apply orchestration."""
import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from garmin_fit_sdk import Encoder

from garminsynapse.core import activity_corrections as ac


def _build_synthetic_fit_with_outlier() -> bytes:
    enc = Encoder()
    enc.on_mesg(0, {
        "type": "activity",
        "manufacturer": "garmin",
        "product": 1,
        "time_created": datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
    })
    for i in range(20):
        altitude = 1200.0 if i != 10 else -9999.0  # single spurious spike
        enc.on_mesg(20, {
            "timestamp": datetime.datetime(2024, 1, 1, 0, 0, i, tzinfo=datetime.timezone.utc),
            "position_lat": 500000000 + i * 100,
            "position_long": 100000000 + i * 100,
            "enhanced_altitude": altitude,
        })
    enc.on_mesg(18, {
        "timestamp": datetime.datetime(2024, 1, 1, 0, 0, 20, tzinfo=datetime.timezone.utc),
        "start_time": datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        "sport": "hiking",
        "message_index": 0,
    })
    return enc.close()


def _build_synthetic_fit_clean() -> bytes:
    enc = Encoder()
    enc.on_mesg(0, {
        "type": "activity",
        "manufacturer": "garmin",
        "product": 1,
        "time_created": datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
    })
    for i in range(10):
        enc.on_mesg(20, {
            "timestamp": datetime.datetime(2024, 1, 1, 0, 0, i, tzinfo=datetime.timezone.utc),
            "enhanced_altitude": 500.0,
        })
    return enc.close()


class TestPreviewCorrections:
    def test_reports_findings_without_mutating_anything(self):
        mock_api = MagicMock()
        mock_api.download_activity_fit.return_value = _build_synthetic_fit_with_outlier()

        result = ac.preview_corrections(mock_api, activity_id=42)

        assert result["activity_id"] == 42
        assert result["sport"] == "hiking"
        assert result["record_count"] == 20
        assert len(result["findings"]) == 1
        assert result["findings"][0]["field"] == "enhanced_altitude"
        mock_api.delete_activity.assert_not_called()
        mock_api.upload_activity.assert_not_called()

    def test_reports_no_findings_for_clean_activity(self):
        mock_api = MagicMock()
        mock_api.download_activity_fit.return_value = _build_synthetic_fit_clean()

        result = ac.preview_corrections(mock_api, activity_id=7)
        assert result["findings"] == []


class TestApplyCorrections:
    def test_refuses_without_explicit_confirm(self):
        mock_api = MagicMock()
        with pytest.raises(ValueError):
            ac.apply_corrections(mock_api, activity_id=42, confirm=False)
        mock_api.download_activity_fit.assert_not_called()

    def test_no_op_when_no_outliers_found(self, tmp_path: Path):
        mock_api = MagicMock()
        mock_api.download_activity_fit.return_value = _build_synthetic_fit_clean()

        result = ac.apply_corrections(mock_api, activity_id=7, confirm=True, backup_dir=tmp_path)

        assert result["applied"] is False
        mock_api.delete_activity.assert_not_called()
        mock_api.upload_activity.assert_not_called()

    def test_backs_up_deletes_and_reuploads_when_outliers_found(self, tmp_path: Path):
        mock_api = MagicMock()
        raw = _build_synthetic_fit_with_outlier()
        mock_api.download_activity_fit.return_value = raw
        mock_api.delete_activity.return_value = None
        mock_api.upload_activity.return_value = {"detailedImportResult": {"successes": [{"internalId": 999}]}}

        result = ac.apply_corrections(mock_api, activity_id=42, confirm=True, backup_dir=tmp_path)

        assert result["applied"] is True
        assert len(result["findings"]) == 1

        # Original was backed up to disk, byte-for-byte.
        backups = list(tmp_path.glob("42_*.fit"))
        assert len(backups) == 1
        assert backups[0].read_bytes() == raw

        mock_api.delete_activity.assert_called_once_with("42")
        mock_api.upload_activity.assert_called_once()
        uploaded_path = mock_api.upload_activity.call_args[0][0]
        assert not Path(uploaded_path).exists(), "temp upload file should be cleaned up"

        assert result["upload_result"] == {"detailedImportResult": {"successes": [{"internalId": 999}]}}
