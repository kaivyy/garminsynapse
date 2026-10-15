"""Unit tests for MCP tools."""
from unittest.mock import patch, MagicMock

from garminsynapse.mcp.tools import garmin_status, garmin_login

def test_garmin_status():
    result = garmin_status()
    assert isinstance(result, dict)
    assert result["status"] == "OK"
    assert "authenticated" in result


def test_garmin_login_resume_does_not_require_password():
    """Regression: an agent completing a paused MFA login with only
    email+mfa_code must not be rejected for omitting password.
    """
    with patch("garminsynapse.mcp.tools.DualAuthManager") as mock_mgr_cls:
        mock_mgr = MagicMock()
        mock_mgr.login_resume.return_value = {"source": "cffi_strategy"}
        mock_mgr_cls.return_value = mock_mgr

        result = garmin_login(email="user@example.com", mfa_code="123456")

        assert result["status"] == "success"
        mock_mgr.login_resume.assert_called_once_with("user@example.com", "123456")


def test_garmin_login_requires_password_to_start_new_login():
    result = garmin_login(email="user@example.com")
    assert result["status"] == "error"


def test_get_heart_rate_zones_unauth():
    from garminsynapse.mcp.tools import get_heart_rate_zones
    with patch("garminsynapse.mcp.tools.GarminAPI") as mock_api_cls:
        mock_api = MagicMock()
        mock_api._garmin_instance = None
        mock_api_cls.return_value = mock_api
        res = get_heart_rate_zones()
        assert res.get("error") == "unauthenticated"


def test_get_activity_hr_zones():
    from garminsynapse.mcp.tools import get_activity_hr_zones
    with patch("garminsynapse.mcp.tools.GarminAPI") as mock_api_cls:
        mock_api = MagicMock()
        mock_g = MagicMock()
        mock_g.get_activity_hr_in_timezones.return_value = [
            {"zoneNumber": 1, "secsInZone": 60, "zoneLowBoundary": 100},
            {"zoneNumber": 2, "secsInZone": 140, "zoneLowBoundary": 120}
        ]
        mock_api._garmin_instance = mock_g
        mock_api_cls.return_value = mock_api
        res = get_activity_hr_zones(12345)
        assert res["status"] == "success"
        assert res["activity_id"] == 12345
        assert res["total_duration_sec"] == 200
        assert len(res["zones"]) == 2
        assert res["zones"][0]["percentInZone"] == 30.0


def test_get_personal_records():
    from garminsynapse.mcp.tools import get_personal_records
    with patch("garminsynapse.mcp.tools.GarminAPI") as mock_api_cls:
        mock_api = MagicMock()
        mock_g = MagicMock()
        mock_g.get_personal_record.return_value = [{"typeId": 1, "value": 300}]
        mock_api._garmin_instance = mock_g
        mock_api_cls.return_value = mock_api
        res = get_personal_records()
        assert res["status"] == "success"
        assert len(res["personal_records"]) == 1


def test_garmin_raw_api():
    from garminsynapse.mcp.tools import garmin_raw_api
    with patch("garminsynapse.mcp.tools.GarminAPI") as mock_api_cls:
        mock_api = MagicMock()
        mock_g = MagicMock()
        mock_g.connectapi.return_value = {"foo": "bar"}
        mock_api._garmin_instance = mock_g
        mock_api_cls.return_value = mock_api
        res = garmin_raw_api("/test/endpoint")
        assert res["status"] == "success"
        assert res["data"] == {"foo": "bar"}


