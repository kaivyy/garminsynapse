"""Regression tests for CffiStrategy's non-blocking MFA login flow.

Covers three issues found in Copilot review of PR #1:
1. login_start() must not raise on an ordinary (non-MFA) successful login,
   where Garmin.login() returns None rather than a (status, result) tuple.
2. login_resume() must not discard the pending login entry when the submitted
   MFA code is rejected, so the user can retry without restarting the login.
3. login_resume() must honor the pending-login TTL (treat an expired entry as
   not found) even though it's no longer eagerly popped on every call.
"""
import time
from unittest.mock import MagicMock

import garminsynapse.auth.cffi_strategy as cffi_strategy_module
from garminsynapse.auth.cffi_strategy import CffiStrategy


def _clear_pending():
    cffi_strategy_module._PENDING_LOGINS.clear()


def test_login_start_succeeds_when_garmin_login_returns_none(monkeypatch):
    """Garmin.login() returns None on an ordinary successful login (the
    (status, result) tuple is only produced for the MFA short-circuit path).
    """
    _clear_pending()
    fake_garmin = MagicMock()
    fake_garmin.login.return_value = None
    fake_garmin.client = MagicMock()
    fake_garmin.display_name = "Test User"

    monkeypatch.setattr(cffi_strategy_module, "Garmin", lambda **kwargs: fake_garmin)

    strategy = CffiStrategy()
    result = strategy.login_start("user@example.com", "hunter2")

    assert result["needs_mfa"] is False
    assert "user@example.com" not in cffi_strategy_module._PENDING_LOGINS


def test_login_start_flags_mfa_when_status_tuple_returned(monkeypatch):
    _clear_pending()
    fake_garmin = MagicMock()
    fake_garmin.login.return_value = ("needs_mfa", None)
    fake_garmin.client = MagicMock()

    monkeypatch.setattr(cffi_strategy_module, "Garmin", lambda **kwargs: fake_garmin)

    strategy = CffiStrategy()
    result = strategy.login_start("user@example.com", "hunter2")

    assert result == {"needs_mfa": True, "email": "user@example.com"}
    assert "user@example.com" in cffi_strategy_module._PENDING_LOGINS


def test_login_resume_keeps_pending_entry_on_failed_code():
    """A rejected/mistyped MFA code must not permanently discard the paused
    Garmin session -- the user should be able to retry with the correct code.
    """
    _clear_pending()
    fake_garmin = MagicMock()
    fake_garmin.client.resume_login.side_effect = Exception("invalid code")
    cffi_strategy_module._PENDING_LOGINS["user@example.com"] = {
        "garmin": fake_garmin, "password": "hunter2", "ts": time.time()
    }

    strategy = CffiStrategy()
    try:
        strategy.login_resume("user@example.com", "000000")
        assert False, "expected the resume failure to propagate"
    except Exception:
        pass

    assert "user@example.com" in cffi_strategy_module._PENDING_LOGINS


def test_login_resume_succeeds_and_clears_pending_entry(monkeypatch):
    _clear_pending()
    fake_garmin = MagicMock()
    fake_garmin.client = MagicMock()
    fake_garmin.client.get_api_headers.return_value = {}
    fake_garmin.display_name = "Test User"
    cffi_strategy_module._PENDING_LOGINS["user@example.com"] = {
        "garmin": fake_garmin, "password": "hunter2", "ts": time.time()
    }

    strategy = CffiStrategy()
    tokens = strategy.login_resume("user@example.com", "123456")

    assert tokens["_password"] == "hunter2"
    assert "user@example.com" not in cffi_strategy_module._PENDING_LOGINS


def test_login_resume_rejects_expired_pending_entry():
    _clear_pending()
    fake_garmin = MagicMock()
    stale_ts = time.time() - (cffi_strategy_module._MFA_PENDING_TTL_SECONDS + 5)
    cffi_strategy_module._PENDING_LOGINS["user@example.com"] = {
        "garmin": fake_garmin, "password": "hunter2", "ts": stale_ts
    }

    strategy = CffiStrategy()
    try:
        strategy.login_resume("user@example.com", "123456")
        assert False, "expected a RuntimeError for an expired pending login"
    except RuntimeError:
        pass

    assert "user@example.com" not in cffi_strategy_module._PENDING_LOGINS
