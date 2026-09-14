"""Cffi Strategy adapting python-garminconnect's 5-stage login engine."""
import logging
from typing import Dict, Any, Optional
from garminconnect import Garmin

logger = logging.getLogger(__name__)


class CffiStrategy:
    """Uses python-garminconnect's multi-stage browser impersonation login engine."""

    def __init__(self, domain: str = "garmin.com"):
        self.domain = domain

    def login(self, email: str, password: str, prompt_mfa=None) -> Dict[str, Any]:
        logger.info(f"Authenticating Garmin Connect for {email}...")
        garmin = Garmin(email=email, password=password, prompt_mfa=prompt_mfa, verify_login=False)
        if hasattr(garmin, "client"):
            garmin.client.skip_strategies = {"mobile+cffi", "mobile+requests"}
        garmin.login()
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

        tokens = {
            "email": email,
            "user_id": getattr(garmin, "display_name", None) or getattr(garmin, "username", None),
            "client_state": client_dump,
            "headers": headers,
            "source": "cffi_strategy"
        }
        return tokens

