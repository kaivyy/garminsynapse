"""Full Garmin Connect API Wrapper wrapping 180+ endpoints from python-garminconnect."""
import logging
from typing import Dict, Any, List, Optional
import functools
import requests

try:
    import garminconnect
    _GARMINCONNECT_AVAILABLE = True
except ImportError:
    _GARMINCONNECT_AVAILABLE = False

from garminsynapse.auth.tokens import TokenManager

logger = logging.getLogger(__name__)


def with_auto_retry(func):
    """Decorator to retry requests on 5xx or network errors."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"API call {func.__name__} failed: {e}. Retrying...")
            return func(*args, **kwargs)
    return wrapper


class GarminAPI:
    """Wrapper covering 180+ Garmin Connect API endpoints."""

    def __init__(self, email: Optional[str] = None, password: Optional[str] = None, session_headers: Optional[Dict[str, str]] = None):
        self.session = requests.Session()
        if session_headers:
            self.session.headers.update(session_headers)
        self.base_url = "https://connect.garmin.com"
        self._garmin_instance = None

        if _GARMINCONNECT_AVAILABLE:
            token_mgr = TokenManager()
            cached = token_mgr.load_tokens() or {}
            headers = session_headers or cached.get("headers")
            target_email = email or cached.get("email")
            client_state = cached.get("client_state")

            if client_state:
                try:
                    g = garminconnect.Garmin()
                    g.client.loads(client_state)
                    self._garmin_instance = g
                    if hasattr(g, "client") and hasattr(g.client, "session"):
                        self.session = g.client.session
                except Exception as e:
                    logger.warning(f"Could not restore logged in Garmin instance from client_state: {e}")
            elif target_email and password:
                try:
                    g = garminconnect.Garmin(email=target_email, password=password)
                    g.login()
                    self._garmin_instance = g
                    if hasattr(g, "client") and hasattr(g.client, "session"):
                        self.session = g.client.session
                except Exception as e:
                    logger.warning(f"Could not initialize logged in Garmin instance: {e}")

    def __getattr__(self, name: str):
        """Dynamically proxy any missing endpoint method to python-garminconnect Garmin class."""
        if self._garmin_instance and hasattr(self._garmin_instance, name):
            attr = getattr(self._garmin_instance, name)
            if callable(attr):
                return with_auto_retry(attr)
            return attr
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    @with_auto_retry
    def get_user_profile(self) -> Dict[str, Any]:
        """Fetch user social profile."""
        if self._garmin_instance:
            return self._garmin_instance.get_user_profile()
        url = f"{self.base_url}/userprofile-service/socialProfile"
        resp = self.session.get(url)
        return resp.json() if resp.status_code == 200 else {}

    @with_auto_retry
    def get_daily_stats(self, date_str: str) -> Dict[str, Any]:
        """Fetch daily health summary (steps, calories, HR)."""
        if self._garmin_instance:
            return self._garmin_instance.get_user_summary(date_str)
        url = f"{self.base_url}/wellness-service/wellness/dailySummaryChart/{date_str}"
        resp = self.session.get(url)
        return resp.json() if resp.status_code == 200 else {}

    @with_auto_retry
    def get_sleep_data(self, date_str: str) -> Dict[str, Any]:
        """Fetch sleep levels, duration, and score."""
        if self._garmin_instance:
            return self._garmin_instance.get_sleep_data(date_str)
        url = f"{self.base_url}/wellness-service/wellness/dailySleepData"
        resp = self.session.get(url, params={"date": date_str})
        return resp.json() if resp.status_code == 200 else {}

    @with_auto_retry
    def get_stress_data(self, date_str: str) -> Dict[str, Any]:
        """Fetch daily stress level time series."""
        if self._garmin_instance:
            return self._garmin_instance.get_stress_data(date_str)
        url = f"{self.base_url}/wellness-service/wellness/dailyStress/{date_str}"
        resp = self.session.get(url)
        return resp.json() if resp.status_code == 200 else {}

    @with_auto_retry
    def get_activities(self, start: int = 0, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch list of user activities with pagination."""
        if self._garmin_instance:
            return self._garmin_instance.get_activities(start, limit)
        url = f"{self.base_url}/activitylist-service/activities/search/activities"
        resp = self.session.get(url, params={"start": start, "limit": limit})
        return resp.json() if resp.status_code == 200 else []

    @with_auto_retry
    def get_activity_details(self, activity_id: int) -> Dict[str, Any]:
        """Fetch detailed time-series metrics for an activity."""
        if self._garmin_instance:
            return self._garmin_instance.get_activity_details(activity_id)
        url = f"{self.base_url}/activity-service/activity/{activity_id}/details"
        resp = self.session.get(url)
        return resp.json() if resp.status_code == 200 else {}

    @with_auto_retry
    def download_activity_fit(self, activity_id: int) -> bytes:
        """Download raw binary FIT file for an activity."""
        if self._garmin_instance:
            return self._garmin_instance.download_activity(activity_id, dl_fmt=self._garmin_instance.ActivityDownloadFormat.ORIGINAL)
        url = f"{self.base_url}/download-service/files/activity/{activity_id}"
        resp = self.session.get(url)
        return resp.content if resp.status_code == 200 else b""
