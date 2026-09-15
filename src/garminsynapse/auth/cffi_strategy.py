"""Cffi Strategy adapting python-garminconnect's 5-stage login engine."""
import logging
import threading
import time
from typing import Dict, Any, Optional
from garminconnect import Garmin

logger = logging.getLogger(__name__)

# How long a paused (awaiting-MFA-code) login is kept in memory before it is
# discarded. The in-progress Garmin/client instance can't be serialized to
# disk, so it lives only in this process until resumed or it expires.
_MFA_PENDING_TTL_SECONDS = 300

# Process-wide (module-level) pending-login store, keyed by email. This must
# NOT live on a CffiStrategy/DualAuthManager instance: each HTTP request
# constructs a fresh DualAuthManager (see web/routes.py and mcp/tools.py), so
# instance-level state would be discarded before the follow-up MFA-code
# request could ever see it.
# email -> {"garmin": Garmin, "password": str, "ts": float}
_PENDING_LOGINS: Dict[str, Dict[str, Any]] = {}
_PENDING_LOCK = threading.Lock()


class CffiStrategy:
    """Uses python-garminconnect's multi-stage browser impersonation login engine."""

    def __init__(self, domain: str = "garmin.com"):
        self.domain = domain

    def _build_tokens(self, email: str, garmin: Garmin) -> Dict[str, Any]:
        client_obj = getattr(garmin, "client", None)
        if client_obj and hasattr(client_obj, "get_api_headers"):
            headers = client_obj.get_api_headers()
        elif client_obj and hasattr(client_obj, "session"):
            headers = dict(client_obj.session.headers)
        else:
            headers = {}

        client_dump = None
        if client_obj and hasattr(client_obj, "dumps"):
            try:
                client_dump = client_obj.dumps()
            except Exception as e:
                logger.warning(f"Could not serialize garmin client: {e}")

        return {
            "email": email,
            "user_id": getattr(garmin, "display_name", None) or getattr(garmin, "username", None),
            "client_state": client_dump,
            "headers": headers,
            "source": "cffi_strategy"
        }

    def _gc_pending(self) -> None:
        now = time.time()
        with _PENDING_LOCK:
            expired = [k for k, v in _PENDING_LOGINS.items() if now - v["ts"] > _MFA_PENDING_TTL_SECONDS]
            for k in expired:
                del _PENDING_LOGINS[k]

    def login(self, email: str, password: str, prompt_mfa=None) -> Dict[str, Any]:
        """One-shot blocking login. If MFA is required and prompt_mfa is provided, it is
        invoked synchronously to obtain the code and complete the login in this call."""
        logger.info(f"Authenticating Garmin Connect for {email}...")
        garmin = Garmin(email=email, password=password, prompt_mfa=prompt_mfa, verify_login=False)
        if hasattr(garmin, "client"):
            garmin.client.skip_strategies = {"mobile+cffi", "mobile+requests"}
        garmin.login()
        return self._build_tokens(email, garmin)

    def login_start(self, email: str, password: str) -> Dict[str, Any]:
        """Begin a non-blocking login. Returns {'needs_mfa': True, 'email': email} if an
        MFA code is required (call login_resume() to finish), otherwise returns full tokens."""
        self._gc_pending()
        logger.info(f"Starting Garmin Connect login for {email} (MFA-aware)...")
        garmin = Garmin(email=email, password=password, return_on_mfa=True, verify_login=False)
        if hasattr(garmin, "client"):
            garmin.client.skip_strategies = {"mobile+cffi", "mobile+requests"}
        # Garmin.login() returns None on an ordinary successful login; the
        # (status, result) tuple is only returned when return_on_mfa causes
        # it to short-circuit for an MFA challenge. Unpacking unconditionally
        # would raise on every non-MFA login and incorrectly fall back to
        # Playwright, so only inspect the tuple when one is actually returned.
        login_result = garmin.login()
        if login_result:
            mfa_status, _ = login_result
            if mfa_status == "needs_mfa":
                with _PENDING_LOCK:
                    _PENDING_LOGINS[email] = {"garmin": garmin, "password": password, "ts": time.time()}
                return {"needs_mfa": True, "email": email}
        tokens = self._build_tokens(email, garmin)
        tokens["needs_mfa"] = False
        return tokens

    def login_resume(self, email: str, mfa_code: str) -> Dict[str, Any]:
        """Complete a login previously paused by login_start() using the MFA code."""
        with _PENDING_LOCK:
            entry = _PENDING_LOGINS.get(email)
            if entry and time.time() - entry["ts"] > _MFA_PENDING_TTL_SECONDS:
                # Expired: discard now so a stale entry can't be resumed, and
                # report the same "not found" error a missing entry would.
                del _PENDING_LOGINS[email]
                entry = None
        if not entry:
            raise RuntimeError(
                "No pending MFA login found for this email (it may have expired after "
                f"{_MFA_PENDING_TTL_SECONDS}s). Please start the login again."
            )
        garmin = entry["garmin"]
        # Keep the pending entry in place until the resume actually succeeds,
        # so a mistyped/rejected code doesn't discard the live Garmin session
        # and permanently prevent the user from retrying.
        garmin.client.resume_login(None, mfa_code)
        with _PENDING_LOCK:
            _PENDING_LOGINS.pop(email, None)
        tokens = self._build_tokens(email, garmin)
        # Transient only: carried back to the caller so it can persist saved
        # credentials for auto-login, then stripped before tokens hit disk.
        tokens["_password"] = entry.get("password")
        return tokens
