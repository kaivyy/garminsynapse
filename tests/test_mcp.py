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

