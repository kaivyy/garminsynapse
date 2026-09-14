"""Unit tests for the activity-type-change and outlier-correction MCP tools."""
from unittest.mock import MagicMock, patch

AUTH_PATCH_TARGET = "garminsynapse.mcp.tools.DualAuthManager"


def _mock_authenticated():
    mgr = MagicMock()
    mgr.get_active_tokens.return_value = {"headers": {"Authorization": "Bearer x"}}
    return mgr


class TestChangeActivityTypeTool:
    def test_returns_error_when_unauthenticated(self):
        from garminsynapse.mcp.tools import change_activity_type
        with patch(AUTH_PATCH_TARGET) as mock_mgr_cls:
            mock_mgr = MagicMock()
            mock_mgr.get_active_tokens.return_value = None
            mock_mgr_cls.return_value = mock_mgr

            result = change_activity_type(42, "hiking")
            assert result.get("error") == "unauthenticated"

    def test_calls_api_when_authenticated(self):
        from garminsynapse.mcp.tools import change_activity_type
        with patch(AUTH_PATCH_TARGET) as mock_mgr_cls, \
             patch("garminsynapse.mcp.tools.GarminAPI") as mock_api_cls:
            mock_mgr_cls.return_value = _mock_authenticated()
            mock_api = MagicMock()
            mock_api.change_activity_type.return_value = {"activityId": 42}
            mock_api_cls.return_value = mock_api

            result = change_activity_type(42, "hiking")
            assert result["status"] == "success"
            mock_api.change_activity_type.assert_called_once_with(42, "hiking")


class TestPreviewActivityOutliersTool:
    def test_returns_error_when_unauthenticated(self):
        from garminsynapse.mcp.tools import preview_activity_outliers
        with patch(AUTH_PATCH_TARGET) as mock_mgr_cls:
            mock_mgr = MagicMock()
            mock_mgr.get_active_tokens.return_value = None
            mock_mgr_cls.return_value = mock_mgr

            result = preview_activity_outliers(42)
            assert result.get("error") == "unauthenticated"

    def test_returns_findings_when_authenticated(self):
        from garminsynapse.mcp.tools import preview_activity_outliers
        with patch(AUTH_PATCH_TARGET) as mock_mgr_cls, \
             patch("garminsynapse.mcp.tools.GarminAPI") as mock_api_cls, \
             patch("garminsynapse.mcp.tools.activity_corrections.preview_corrections") as mock_preview:
            mock_mgr_cls.return_value = _mock_authenticated()
            mock_api_cls.return_value = MagicMock()
            mock_preview.return_value = {
                "activity_id": 42, "sport": "hiking", "record_count": 10,
                "findings": [{"detector": "d", "index": 1, "field": "f",
                              "original_value": 1, "corrected_value": 2, "reason": "r"}],
            }
            result = preview_activity_outliers(42)
            assert len(result["findings"]) == 1


class TestApplyActivityCorrectionsTool:
    def test_refuses_without_confirm(self):
        from garminsynapse.mcp.tools import apply_activity_corrections
        with patch(AUTH_PATCH_TARGET) as mock_mgr_cls, \
             patch("garminsynapse.mcp.tools.activity_corrections.apply_corrections") as mock_apply:
            mock_mgr_cls.return_value = _mock_authenticated()
            result = apply_activity_corrections(42, confirm=False)
            assert result["status"] == "confirmation_required"
            mock_apply.assert_not_called()

    def test_applies_when_confirmed(self):
        from garminsynapse.mcp.tools import apply_activity_corrections
        with patch(AUTH_PATCH_TARGET) as mock_mgr_cls, \
             patch("garminsynapse.mcp.tools.GarminAPI") as mock_api_cls, \
             patch("garminsynapse.mcp.tools.activity_corrections.apply_corrections") as mock_apply:
            mock_mgr_cls.return_value = _mock_authenticated()
            mock_api_cls.return_value = MagicMock()
            mock_apply.return_value = {
                "activity_id": 42, "applied": True, "findings": [], "backup_path": "/tmp/x.fit",
                "encode_report": {"summary": "ok", "dropped_mesg_counts": {}}, "upload_result": {},
            }
            result = apply_activity_corrections(42, confirm=True)
            assert result["applied"] is True
            _args, kwargs = mock_apply.call_args
            assert kwargs.get("confirm") is True
