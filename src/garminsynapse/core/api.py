"""Full Garmin Connect API Wrapper wrapping 180+ endpoints from python-garminconnect."""
import io
import logging
import zipfile
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
    """Decorator to retry requests on 5xx, 401, or network errors with auto-login."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            err_str = str(e)
            if "401" in err_str or "403" in err_str or "unauthenticated" in err_str.lower():
                logger.info(f"API call {func.__name__} encountered auth error: {e}. Attempting fast token refresh and retry...")
                from garminsynapse.auth.manager import DualAuthManager
                auth_mgr = DualAuthManager()
                new_tokens = auth_mgr.fast_refresh() or auth_mgr.auto_login()
                if new_tokens:
                    if args and isinstance(args[0], GarminAPI):
                        api_inst = args[0]
                        if new_tokens.get("client_state") and _GARMINCONNECT_AVAILABLE:
                            try:
                                g = garminconnect.Garmin()
                                g.client.loads(new_tokens["client_state"])
                                g.display_name = new_tokens.get("user_id")
                                api_inst._garmin_instance = g
                                if hasattr(g.client, "get_api_headers"):
                                    api_inst.session.headers.update(g.client.get_api_headers())
                            except Exception as reload_err:
                                logger.warning(f"Failed to reload client after token refresh: {reload_err}")
                    return func(*args, **kwargs)
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
            from garminsynapse.auth.manager import DualAuthManager
            auth_mgr = DualAuthManager()
            cached = auth_mgr.get_active_tokens(auto_refresh=True) or {}
            headers = session_headers or cached.get("headers")
            target_email = email or cached.get("email")
            client_state = cached.get("client_state")

            if client_state:
                try:
                    g = garminconnect.Garmin()
                    g.client.loads(client_state)
                    # Restore display_name immediately from cached user_id without extra HTTP roundtrips
                    g.display_name = cached.get("user_id")
                    self._garmin_instance = g
                    if hasattr(g, "client") and hasattr(g.client, "get_api_headers"):
                        self.session.headers.update(g.client.get_api_headers())
                    elif hasattr(g, "client") and hasattr(g.client, "session"):
                        self.session = g.client.session
                except Exception as e:
                    logger.warning(f"Could not restore logged in Garmin instance from client_state: {e}")
            elif target_email and password:
                try:
                    g = garminconnect.Garmin(email=target_email, password=password)
                    if hasattr(g, "client"):
                        g.client.skip_strategies = {"mobile+cffi", "mobile+requests"}
                    g.login()
                    self._garmin_instance = g
                    if hasattr(g, "client") and hasattr(g.client, "get_api_headers"):
                        self.session.headers.update(g.client.get_api_headers())
                    elif hasattr(g, "client") and hasattr(g.client, "session"):
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
            try:
                return self._garmin_instance.get_user_summary(date_str)
            except Exception:
                try:
                    steps_list = self._garmin_instance.get_daily_steps(date_str, date_str)
                    if steps_list and isinstance(steps_list, list):
                        item = steps_list[0]
                        return {
                            "totalSteps": item.get("totalSteps", 0),
                            "dailyStepGoal": item.get("stepGoal", 10000),
                            "totalDistance": item.get("totalDistance", 0)
                        }
                except Exception:
                    pass
                return {}
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

    def _normalize_to_1km_splits(self, laps: list, target_dist: float = 1000.0) -> list:
        """Normalize raw lap segments into continuous 1.0 km metric splits.
        
        Fixes issue where workout phases, interval steps, or manual lap buttons
        fragment splits into non-1km segments (e.g. 1km, 1km, 1km, 0.75km, 1km, 0.3km).
        """
        if not laps or not isinstance(laps, list):
            return []
            
        needs_norm = False
        for lap in laps[:-1]:
            d = lap.get("distance", 0) or 0
            if abs(d - target_dist) > 50:  # >50m deviation
                needs_norm = True
                break
                
        if not needs_norm:
            for idx, lap in enumerate(laps):
                if not lap.get("splitIndex"):
                    lap["splitIndex"] = idx + 1
            return laps

        lap_iter = iter(laps)
        lap = next(lap_iter, None)
        lap_rem_dist = float(lap.get("distance") or 0) if lap else 0.0
        lap_rem_dur = float(lap.get("duration") or 0) if lap else 0.0
        lap_rem_elev = float(lap.get("elevationGain") or 0) if lap else 0.0
        lap_hr = lap.get("averageHR")
        lap_max_hr = lap.get("maxHR")
        lap_cadence = lap.get("averageRunCadence")

        splits = []
        split_idx = 1
        while lap is not None:
            accum_dist = 0.0
            accum_dur = 0.0
            accum_elev = 0.0
            hr_weight = 0.0
            cad_weight = 0.0
            max_hr_val = 0.0
            
            while accum_dist < target_dist and lap is not None:
                needed = target_dist - accum_dist
                take_dist = min(needed, lap_rem_dist)
                fraction = take_dist / lap_rem_dist if lap_rem_dist > 0 else 0.0
                
                take_dur = lap_rem_dur * fraction
                take_elev = (lap_rem_elev or 0) * fraction
                
                accum_dist += take_dist
                accum_dur += take_dur
                accum_elev += take_elev
                if lap_hr is not None:
                    hr_weight += float(lap_hr) * take_dur
                if lap_max_hr is not None:
                    max_hr_val = max(max_hr_val, float(lap_max_hr))
                if lap_cadence is not None:
                    cad_weight += float(lap_cadence) * take_dur
                
                lap_rem_dist -= take_dist
                lap_rem_dur -= take_dur
                lap_rem_elev -= take_elev
                
                if lap_rem_dist <= 0.01:
                    lap = next(lap_iter, None)
                    if lap:
                        lap_rem_dist = float(lap.get("distance") or 0)
                        lap_rem_dur = float(lap.get("duration") or 0)
                        lap_rem_elev = float(lap.get("elevationGain") or 0)
                        lap_hr = lap.get("averageHR")
                        lap_max_hr = lap.get("maxHR")
                        lap_cadence = lap.get("averageRunCadence")
            
            if accum_dist > 0:
                avg_spd = accum_dist / accum_dur if accum_dur > 0 else 0.0
                avg_hr = hr_weight / accum_dur if accum_dur > 0 and hr_weight > 0 else None
                avg_cad = cad_weight / accum_dur if accum_dur > 0 and cad_weight > 0 else None
                
                splits.append({
                    "splitIndex": split_idx,
                    "distance": round(accum_dist, 2),
                    "duration": round(accum_dur, 2),
                    "averageSpeed": avg_spd,
                    "averageHR": round(avg_hr) if avg_hr else None,
                    "maxHR": round(max_hr_val) if max_hr_val > 0 else None,
                    "averageRunCadence": round(avg_cad) if avg_cad else None,
                    "elevationGain": round(accum_elev, 1),
                })
                split_idx += 1
                
        return splits

    @with_auto_retry
    def get_activity_splits(self, activity_id: int) -> Dict[str, Any]:
        """Fetch per-km / per-lap splits for an activity."""
        if self._garmin_instance:
            try:
                data = self._garmin_instance.get_activity_splits(activity_id)
                # garminconnect returns {"activityId": ..., "lapDTOs": [...]}
                if isinstance(data, dict) and "lapDTOs" in data:
                    return {"splits": self._normalize_to_1km_splits(data["lapDTOs"])}
                return {"splits": self._normalize_to_1km_splits(data)} if isinstance(data, list) else {"splits": []}
            except Exception as e:
                # Handle activities without split data.
                if "404" in str(e) or "204" in str(e):
                    return {"splits": []}
                pass
                
        url = f"{self.base_url}/activity-service/activity/{activity_id}/splits"
        try:
            resp = self.session.get(url)
            if resp.status_code == 200 and resp.text:
                res_data = resp.json()
                raw_laps = res_data.get("lapDTOs", res_data) if isinstance(res_data, dict) else res_data
                return {"splits": self._normalize_to_1km_splits(raw_laps) if isinstance(raw_laps, list) else []}
        except Exception:
            pass
        return {"splits": []}

    @with_auto_retry
    def download_activity_fit(self, activity_id: int) -> bytes:
        """Download raw binary FIT file for an activity.

        Garmin Connect's ORIGINAL download format sometimes returns a ZIP
        archive wrapping a single ``<id>_ACTIVITY.fit`` member (observed for
        activities recorded via the Garmin Connect mobile app) instead of raw
        FIT bytes. Transparently unwrap that case so callers always get raw
        FIT bytes.
        """
        if self._garmin_instance:
            raw = self._garmin_instance.download_activity(activity_id, dl_fmt=self._garmin_instance.ActivityDownloadFormat.ORIGINAL)
        else:
            url = f"{self.base_url}/download-service/files/activity/{activity_id}"
            resp = self.session.get(url)
            raw = resp.content if resp.status_code == 200 else b""
        return self._unwrap_fit_zip(raw)

    @staticmethod
    def _unwrap_fit_zip(raw: bytes) -> bytes:
        if not raw or not zipfile.is_zipfile(io.BytesIO(raw)):
            return raw
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = z.namelist()
            fit_names = [n for n in names if n.lower().endswith(".fit")]
            target = fit_names[0] if fit_names else (names[0] if names else None)
            if target is None:
                return raw
            return z.read(target)

    @with_auto_retry
    def get_activity_types(self) -> List[Dict[str, Any]]:
        """Fetch the catalog of valid Garmin Connect activity types."""
        if self._garmin_instance:
            return self._garmin_instance.get_activity_types()
        return []

    def resolve_activity_type(self, type_key: str) -> Dict[str, Any]:
        """Look up the type_id/parent_type_id catalog entry for a given type_key (e.g. 'hiking')."""
        for t in self.get_activity_types():
            if t.get("typeKey") == type_key:
                return t
        raise ValueError(f"Unknown activity type_key: {type_key!r}")

    @with_auto_retry
    def change_activity_type(self, activity_id: int, type_key: str) -> Dict[str, Any]:
        """Reclassify an existing activity to a different activity type."""
        if not self._garmin_instance:
            raise RuntimeError("Not authenticated with Garmin Connect.")
        t = self.resolve_activity_type(type_key)
        return self._garmin_instance.set_activity_type(
            activity_id, t.get("typeId"), t.get("typeKey"), t.get("parentTypeId")
        )
