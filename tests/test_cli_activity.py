"""Unit tests for the `garminsynapse activity` CLI command group."""
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from garminsynapse.cli import cli


class TestActivitySetType:
    def test_calls_change_activity_type_and_reports_success(self):
        runner = CliRunner()
        with patch("garminsynapse.core.api.GarminAPI") as mock_api_cls:
            mock_api = MagicMock()
            mock_api.change_activity_type.return_value = {"activityId": 42}
            mock_api_cls.return_value = mock_api

            result = runner.invoke(cli, ["activity", "set-type", "42", "hiking"])

            assert result.exit_code == 0
            mock_api.change_activity_type.assert_called_once_with(42, "hiking")
            assert "42" in result.output

    def test_reports_error_on_failure(self):
        runner = CliRunner()
        with patch("garminsynapse.core.api.GarminAPI") as mock_api_cls:
            mock_api = MagicMock()
            mock_api.change_activity_type.side_effect = ValueError("Unknown activity type_key: 'bogus'")
            mock_api_cls.return_value = mock_api

            result = runner.invoke(cli, ["activity", "set-type", "42", "bogus"])

            assert result.exit_code != 0
            assert "Unknown activity type_key" in result.output


class TestActivityPreviewCorrections:
    def test_prints_findings(self):
        runner = CliRunner()
        with patch("garminsynapse.core.api.GarminAPI") as mock_api_cls, \
             patch("garminsynapse.core.activity_corrections.preview_corrections") as mock_preview:
            mock_api_cls.return_value = MagicMock()
            mock_preview.return_value = {
                "activity_id": 42,
                "sport": "hiking",
                "record_count": 100,
                "findings": [
                    {"detector": "median_altitude_outlier", "index": 10, "field": "enhanced_altitude",
                     "original_value": -9999.0, "corrected_value": None, "reason": "way off median"}
                ],
            }
            result = runner.invoke(cli, ["activity", "preview-corrections", "42"])

            assert result.exit_code == 0
            assert "1 outlier" in result.output or "median_altitude_outlier" in result.output

    def test_prints_no_outliers_message_when_clean(self):
        runner = CliRunner()
        with patch("garminsynapse.core.api.GarminAPI") as mock_api_cls, \
             patch("garminsynapse.core.activity_corrections.preview_corrections") as mock_preview:
            mock_api_cls.return_value = MagicMock()
            mock_preview.return_value = {"activity_id": 42, "sport": "hiking", "record_count": 100, "findings": []}
            result = runner.invoke(cli, ["activity", "preview-corrections", "42"])
            assert result.exit_code == 0
            assert "No outliers" in result.output


class TestActivityFix:
    def test_dry_run_only_previews_and_never_applies(self):
        runner = CliRunner()
        with patch("garminsynapse.core.api.GarminAPI") as mock_api_cls, \
             patch("garminsynapse.core.activity_corrections.preview_corrections") as mock_preview, \
             patch("garminsynapse.core.activity_corrections.apply_corrections") as mock_apply:
            mock_api_cls.return_value = MagicMock()
            mock_preview.return_value = {
                "activity_id": 42, "sport": "hiking", "record_count": 100,
                "findings": [{"detector": "d", "index": 1, "field": "f", "original_value": 1,
                              "corrected_value": 2, "reason": "r"}],
            }
            result = runner.invoke(cli, ["activity", "fix", "42", "--dry-run"])
            assert result.exit_code == 0
            mock_apply.assert_not_called()

    def test_requires_confirmation_before_applying(self):
        runner = CliRunner()
        with patch("garminsynapse.core.api.GarminAPI") as mock_api_cls, \
             patch("garminsynapse.core.activity_corrections.preview_corrections") as mock_preview, \
             patch("garminsynapse.core.activity_corrections.apply_corrections") as mock_apply:
            mock_api_cls.return_value = MagicMock()
            mock_preview.return_value = {
                "activity_id": 42, "sport": "hiking", "record_count": 100,
                "findings": [{"detector": "d", "index": 1, "field": "f", "original_value": 1,
                              "corrected_value": 2, "reason": "r"}],
            }
            # User declines the confirmation prompt.
            result = runner.invoke(cli, ["activity", "fix", "42"], input="n\n")
            assert result.exit_code == 0
            mock_apply.assert_not_called()

    def test_applies_after_user_confirms(self):
        runner = CliRunner()
        with patch("garminsynapse.core.api.GarminAPI") as mock_api_cls, \
             patch("garminsynapse.core.activity_corrections.preview_corrections") as mock_preview, \
             patch("garminsynapse.core.activity_corrections.apply_corrections") as mock_apply:
            mock_api_cls.return_value = MagicMock()
            mock_preview.return_value = {
                "activity_id": 42, "sport": "hiking", "record_count": 100,
                "findings": [{"detector": "d", "index": 1, "field": "f", "original_value": 1,
                              "corrected_value": 2, "reason": "r"}],
            }
            mock_apply.return_value = {"applied": True, "activity_id": 42, "backup_path": "/tmp/42.fit",
                                        "upload_result": {}, "findings": [], "encode_report": {"summary": "ok"}}
            result = runner.invoke(cli, ["activity", "fix", "42"], input="y\n")
            assert result.exit_code == 0
            mock_apply.assert_called_once()
            _args, kwargs = mock_apply.call_args
            assert kwargs.get("confirm") is True

    def test_skips_apply_when_no_outliers_found(self):
        runner = CliRunner()
        with patch("garminsynapse.core.api.GarminAPI") as mock_api_cls, \
             patch("garminsynapse.core.activity_corrections.preview_corrections") as mock_preview, \
             patch("garminsynapse.core.activity_corrections.apply_corrections") as mock_apply:
            mock_api_cls.return_value = MagicMock()
            mock_preview.return_value = {"activity_id": 42, "sport": "hiking", "record_count": 100, "findings": []}
            result = runner.invoke(cli, ["activity", "fix", "42"])
            assert result.exit_code == 0
            mock_apply.assert_not_called()
            assert "No outliers" in result.output
