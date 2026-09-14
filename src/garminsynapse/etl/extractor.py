"""Garmin Connect data extraction module for garminsynapse."""
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from garminsynapse.auth.manager import DualAuthManager
from garminsynapse.core.api import GarminAPI

logger = logging.getLogger(__name__)

DEFAULT_INGEST_DIR = Path.cwd() / "garmin_files" / "ingest"


class GarminExtractor:
    """Extracts activity files and JSON health data from Garmin Connect API."""

    # Page size used when paginating through Garmin's activity list.
    _ACTIVITY_PAGE_SIZE = 100
    # Safety cap on the number of pages fetched per sync, to bound worst-case
    # API calls/time for accounts with an extremely long activity history.
    _ACTIVITY_SAFETY_MAX_PAGES = 50

    def __init__(self, ingest_dir: Optional[Path] = None):
        self.ingest_dir = Path(ingest_dir) if ingest_dir else DEFAULT_INGEST_DIR
        self.ingest_dir.mkdir(parents=True, exist_ok=True)
        self.auth_mgr = DualAuthManager()

    def extract_all(self, days: int = 7) -> None:
        """Extract daily health stats, sleep, stress, HRV, body battery, respiration, training status, and activities."""
        tokens = self.auth_mgr.get_active_tokens()
        if not tokens:
            logger.warning("No active tokens found for Garmin extraction.")
            return

        headers = {}
        if "access_token" in tokens:
            headers["Authorization"] = f"Bearer {tokens['access_token']}"
        elif "cookies" in tokens:
            headers["Cookie"] = "; ".join([f"{k}={v}" for k, v in tokens["cookies"].items()])

        api = GarminAPI(session_headers=headers)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        curr = start_date
        while curr <= end_date:
            date_str = curr.strftime("%Y-%m-%d")
            logger.info(f"Extracting all Garmin data metrics for {date_str}...")

            self._save_endpoint_json(api, "get_sleep_data", date_str, f"{date_str}_SLEEP.json")
            self._save_endpoint_json(api, "get_daily_stats", date_str, f"{date_str}_STATS.json")
            self._save_endpoint_json(api, "get_stress_data", date_str, f"{date_str}_STRESS.json")
            self._save_endpoint_json(api, "get_body_battery", date_str, f"{date_str}_BODY_BATTERY.json")
            self._save_endpoint_json(api, "get_hrv_data", date_str, f"{date_str}_HRV.json")
            self._save_endpoint_json(api, "get_heart_rates", date_str, f"{date_str}_HEART_RATE.json")
            self._save_endpoint_json(api, "get_respiration_data", date_str, f"{date_str}_RESPIRATION.json")
            self._save_endpoint_json(api, "get_spo2_data", date_str, f"{date_str}_SPO2.json")
            self._save_endpoint_json(api, "get_training_status", date_str, f"{date_str}_TRAINING_STATUS.json")
            self._save_endpoint_json(api, "get_training_readiness", date_str, f"{date_str}_READINESS.json")
            self._save_endpoint_json(api, "get_hydration_data", date_str, f"{date_str}_HYDRATION.json")
            self._save_endpoint_json(api, "get_fitnessage_data", date_str, f"{date_str}_FITNESS_AGE.json")

            import time
            time.sleep(0.3)
            curr += timedelta(days=1)

        try:
            profile = api.get_user_profile()
            if profile:
                with open(self.ingest_dir / "user_profile.json", "w", encoding="utf-8") as f:
                    json.dump(profile, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to extract user profile: {e}")

        try:
            if hasattr(api, "get_race_predictions"):
                predictions = api.get_race_predictions()
                if predictions:
                    with open(self.ingest_dir / "race_predictions.json", "w", encoding="utf-8") as f:
                        json.dump(predictions, f, indent=2)
        except Exception as e:
            logger.debug(f"Failed to extract race predictions: {e}")

        try:
            if hasattr(api, "get_earned_badges"):
                badges = api.get_earned_badges()
                if badges:
                    with open(self.ingest_dir / "earned_badges.json", "w", encoding="utf-8") as f:
                        json.dump(badges, f, indent=2)
        except Exception as e:
            logger.debug(f"Failed to extract earned badges: {e}")

        try:
            activities = self._fetch_activities_since(api, start_date)
            if activities:
                out_path = self.ingest_dir / "activities_list.json"
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(activities, f, indent=2)
                logger.info(f"Saved {len(activities)} activities to {out_path}")
        except Exception as e:
            logger.error(f"Failed to extract activities: {e}")

    def _parse_activity_start(self, activity: Dict[str, Any]) -> Optional[datetime]:
        """Parse an activity's startTimeLocal field, returning None if missing/unparseable."""
        raw = activity.get("startTimeLocal")
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return None

    def _fetch_activities_since(self, api: GarminAPI, start_date: datetime) -> List[Dict[str, Any]]:
        """Paginate through Garmin's activity list (newest-first) until either the
        oldest activity on a page predates start_date, a short/empty page signals
        we've reached the end of the account's history, or a safety page-count cap
        is hit (bounds worst-case API calls for very long activity histories).
        """
        all_activities: List[Dict[str, Any]] = []
        page_start = 0
        for _ in range(self._ACTIVITY_SAFETY_MAX_PAGES):
            page = api.get_activities(start=page_start, limit=self._ACTIVITY_PAGE_SIZE)
            if not page:
                break
            all_activities.extend(page)
            if len(page) < self._ACTIVITY_PAGE_SIZE:
                break
            oldest_dt = self._parse_activity_start(page[-1])
            if oldest_dt is not None and oldest_dt < start_date:
                break
            page_start += self._ACTIVITY_PAGE_SIZE
        return all_activities

    def _save_endpoint_json(self, api: GarminAPI, method_name: str, date_str: str, filename: str) -> None:
        """Helper to safely invoke endpoint method and write non-empty JSON."""
        try:
            if hasattr(api, method_name):
                fn = getattr(api, method_name)
                data = fn(date_str)
                if data:
                    with open(self.ingest_dir / filename, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to extract {method_name} for {date_str}: {e}")
