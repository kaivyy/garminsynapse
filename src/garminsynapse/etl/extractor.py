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

            # 1. Sleep Data
            self._save_endpoint_json(api, "get_sleep_data", date_str, f"{date_str}_SLEEP.json")

            # 2. Daily Stats (Steps, Calories, RHR)
            self._save_endpoint_json(api, "get_daily_stats", date_str, f"{date_str}_STATS.json")

            # 3. Stress Data
            self._save_endpoint_json(api, "get_stress_data", date_str, f"{date_str}_STRESS.json")

            # 4. HRV Data
            self._save_endpoint_json(api, "get_hrv_data", date_str, f"{date_str}_HRV.json")

            # 5. Body Battery / Heart Rates
            self._save_endpoint_json(api, "get_heart_rates", date_str, f"{date_str}_HEART_RATE.json")

            # 6. Respiration Data
            self._save_endpoint_json(api, "get_respiration_data", date_str, f"{date_str}_RESPIRATION.json")

            # 7. Training Status / Readiness
            self._save_endpoint_json(api, "get_training_status", date_str, f"{date_str}_TRAINING_STATUS.json")

            import time
            time.sleep(0.3)
            curr += timedelta(days=1)

        # 8. User Profile
        try:
            profile = api.get_user_profile()
            if profile:
                with open(self.ingest_dir / "user_profile.json", "w", encoding="utf-8") as f:
                    json.dump(profile, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to extract user profile: {e}")

        # 9. Activities List
        try:
            activities = api.get_activities(start=0, limit=50)
            if activities:
                out_path = self.ingest_dir / "activities_list.json"
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(activities, f, indent=2)
                logger.info(f"Saved {len(activities)} activities to {out_path}")
        except Exception as e:
            logger.error(f"Failed to extract activities: {e}")

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
