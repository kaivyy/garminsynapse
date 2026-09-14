"""Unit tests for the activity-type-change and outlier-correction web routes."""
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from garminsynapse.web.app import app

client = TestClient(app)

AUTH_PATCH_TARGET = "garminsynapse.web.routes.DualAuthManager"


def _mock_authenticated():
    mgr = MagicMock()
    mgr.get_active_tokens.return_value = {"headers": {"Authorization": "Bearer x"}}
    return mgr


class TestListActivityTypesRoute:
    def test_returns_401_when_unauthenticated(self):
        with patch(AUTH_PATCH_TARGET) as mock_mgr_cls:
            mock_mgr = MagicMock()
            mock_mgr.get_active_tokens.return_value = None
            mock_mgr_cls.return_value = mock_mgr
            resp = client.get("/api/v1/activity-types")
            assert resp.status_code == 401

    def test_returns_types_when_authenticated(self):
        with patch(AUTH_PATCH_TARGET) as mock_mgr_cls, \
             patch("garminsynapse.web.routes.GarminAPI") as mock_api_cls:
            mock_mgr_cls.return_value = _mock_authenticated()
            mock_api = MagicMock()
            mock_api.get_activity_types.return_value = [{"typeKey": "hiking", "typeId": 9}]
            mock_api_cls.return_value = mock_api

            resp = client.get("/api/v1/activity-types")
            assert resp.status_code == 200
            assert resp.json()["types"] == [{"typeKey": "hiking", "typeId": 9}]


class TestChangeActivityTypeRoute:
    def test_returns_401_when_unauthenticated(self):
        with patch(AUTH_PATCH_TARGET) as mock_mgr_cls:
            mock_mgr = MagicMock()
            mock_mgr.get_active_tokens.return_value = None
            mock_mgr_cls.return_value = mock_mgr

            resp = client.put("/api/v1/activity/42/type", json={"type_key": "hiking"})
            assert resp.status_code == 401

    def test_changes_type_when_authenticated(self):
        with patch(AUTH_PATCH_TARGET) as mock_mgr_cls, \
             patch("garminsynapse.web.routes.GarminAPI") as mock_api_cls:
            mock_mgr_cls.return_value = _mock_authenticated()
            mock_api = MagicMock()
            mock_api.change_activity_type.return_value = {"activityId": 42}
            mock_api_cls.return_value = mock_api

            resp = client.put("/api/v1/activity/42/type", json={"type_key": "hiking"})

            assert resp.status_code == 200
            mock_api.change_activity_type.assert_called_once_with(42, "hiking")

    def test_returns_400_on_unknown_type_key(self):
        with patch(AUTH_PATCH_TARGET) as mock_mgr_cls, \
             patch("garminsynapse.web.routes.GarminAPI") as mock_api_cls:
            mock_mgr_cls.return_value = _mock_authenticated()
            mock_api = MagicMock()
            mock_api.change_activity_type.side_effect = ValueError("Unknown activity type_key: 'bogus'")
            mock_api_cls.return_value = mock_api

            resp = client.put("/api/v1/activity/42/type", json={"type_key": "bogus"})
            assert resp.status_code == 400


class TestPreviewCorrectionsRoute:
    def test_returns_401_when_unauthenticated(self):
        with patch(AUTH_PATCH_TARGET) as mock_mgr_cls:
            mock_mgr = MagicMock()
            mock_mgr.get_active_tokens.return_value = None
            mock_mgr_cls.return_value = mock_mgr

            resp = client.get("/api/v1/activity/42/corrections/preview")
            assert resp.status_code == 401

    def test_returns_findings_when_authenticated(self):
        with patch(AUTH_PATCH_TARGET) as mock_mgr_cls, \
             patch("garminsynapse.web.routes.GarminAPI") as mock_api_cls, \
             patch("garminsynapse.web.routes.activity_corrections.preview_corrections") as mock_preview:
            mock_mgr_cls.return_value = _mock_authenticated()
            mock_api_cls.return_value = MagicMock()
            mock_preview.return_value = {
                "activity_id": 42, "sport": "hiking", "record_count": 10,
                "findings": [{"detector": "d", "index": 1, "field": "f",
                              "original_value": 1, "corrected_value": 2, "reason": "r"}],
            }

            resp = client.get("/api/v1/activity/42/corrections/preview")
            assert resp.status_code == 200
            body = resp.json()
            assert len(body["findings"]) == 1


class TestApplyCorrectionsRoute:
    def test_returns_400_without_confirm_flag(self):
        with patch(AUTH_PATCH_TARGET) as mock_mgr_cls:
            mock_mgr_cls.return_value = _mock_authenticated()
            resp = client.post("/api/v1/activity/42/corrections/apply", json={"confirm": False})
            assert resp.status_code == 400

    def test_applies_when_confirmed(self):
        with patch(AUTH_PATCH_TARGET) as mock_mgr_cls, \
             patch("garminsynapse.web.routes.GarminAPI") as mock_api_cls, \
             patch("garminsynapse.web.routes.activity_corrections.apply_corrections") as mock_apply:
            mock_mgr_cls.return_value = _mock_authenticated()
            mock_api_cls.return_value = MagicMock()
            mock_apply.return_value = {
                "activity_id": 42, "applied": True, "findings": [], "backup_path": "/tmp/x.fit",
                "encode_report": {"summary": "ok", "dropped_mesg_counts": {}},
                "upload_result": {},
            }

            resp = client.post("/api/v1/activity/42/corrections/apply", json={"confirm": True})
            assert resp.status_code == 200
            _args, kwargs = mock_apply.call_args
            assert kwargs.get("confirm") is True
