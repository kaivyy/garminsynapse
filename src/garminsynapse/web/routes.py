"""FastAPI REST API routes for Garmin Synapse Web Dashboard."""
import logging
from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func
from garminsynapse.auth.manager import DualAuthManager
from garminsynapse.db.manager import DatabaseManager
from garminsynapse.db.schema import Activity, Sleep, HRV, Stress, BodyBattery, UserProfile
from garminsynapse.etl.extractor import GarminExtractor
from garminsynapse.etl.processor import GarminProcessor
from garminsynapse.core.api import GarminAPI

logger = logging.getLogger(__name__)
router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


@router.get("/status")
def status():
    """System health & Auth status."""
    auth_mgr = DualAuthManager()
    tokens = auth_mgr.get_active_tokens()
    return JSONResponse({
        "status": "OK",
        "authenticated": tokens is not None,
        "mcp_server": "active",
        "database": "connected"
    })


@router.post("/auth/login")
def login(req: LoginRequest):
    """Authenticate with Garmin Connect and trigger real data extraction."""
    auth_mgr = DualAuthManager()
    try:
        tokens = auth_mgr.login(req.email, req.password)
        
        # Trigger background data sync upon successful login
        try:
            extractor = GarminExtractor()
            extractor.extract_all(days=7)
            GarminProcessor().process_ingest_directory()
        except Exception as sync_err:
            logger.warning(f"Initial post-login sync warning: {sync_err}")

        return JSONResponse({
            "status": "success",
            "message": "Authenticated successfully with Garmin Connect.",
            "source": tokens.get("source", "oauth")
        })
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/auth/logout")
def logout():
    """Clear saved tokens."""
    auth_mgr = DualAuthManager()
    auth_mgr.logout()
    return JSONResponse({"status": "success", "message": "Logged out successfully."})


# In-memory caches to protect Garmin API from repeated hits
_DEVICE_CACHE = {"data": None, "timestamp": 0}
_DEVICE_CACHE_TTL = 3600 * 6  # 6 hours cache for hardware devices
_LAST_SYNC_TIME = 0
_SYNC_COOLDOWN_SECONDS = 300  # 5 minutes cooldown between manual syncs


@router.get("/devices")
def get_devices(force: bool = False):
    """Fetch registered Garmin devices and primary watch info with smart caching."""
    import time
    now = time.time()
    
    # Return cached device data if valid and not forced
    if not force and _DEVICE_CACHE["data"] and (now - _DEVICE_CACHE["timestamp"] < _DEVICE_CACHE_TTL):
        return JSONResponse(_DEVICE_CACHE["data"])

    api = GarminAPI()
    try:
        if api._garmin_instance:
            devices = api._garmin_instance.get_devices()
            primary = None
            try:
                primary = api._garmin_instance.get_primary_training_device()
            except Exception:
                pass
            res_data = {
                "status": "success",
                "devices": devices or [],
                "primary": primary
            }
            _DEVICE_CACHE["data"] = res_data
            _DEVICE_CACHE["timestamp"] = now
            return JSONResponse(res_data)
        return JSONResponse({"status": "error", "message": "Not authenticated with Garmin", "devices": [], "primary": None})
    except Exception as e:
        logger.error(f"Failed to fetch devices: {e}")
        # If cache exists on error, return stale cache
        if _DEVICE_CACHE["data"]:
            return JSONResponse(_DEVICE_CACHE["data"])
        return JSONResponse({"status": "error", "message": str(e), "devices": [], "primary": None})


_LIVE_CACHE = {"data": None, "timestamp": 0}
_LIVE_CACHE_TTL = 60  # 60 seconds cache to be gentle with Garmin API


@router.get("/live")
def get_live_metrics():
    """Fetch live/latest biometric readings for today (Body Battery, Stress, HR, Steps)."""
    import time
    now = time.time()
    if _LIVE_CACHE["data"] and (now - _LIVE_CACHE["timestamp"] < _LIVE_CACHE_TTL):
        return JSONResponse(_LIVE_CACHE["data"])

    api = GarminAPI()
    if not api._garmin_instance:
        return JSONResponse({"status": "error", "message": "Not authenticated with Garmin"})

    g = api._garmin_instance
    today = datetime.now().strftime("%Y-%m-%d")

    live_body_battery = None
    bb_charged = None
    bb_drained = None
    live_stress = None
    stress_status = None
    live_hr = None
    steps = None

    # Body Battery
    try:
        bb = g.get_body_battery(today)
        if isinstance(bb, list) and bb:
            for item in bb:
                if isinstance(item, dict):
                    bb_charged = item.get("charged", bb_charged)
                    bb_drained = item.get("drained", bb_drained)
                    vals = item.get("bodyBatteryValuesArray", [])
                    for pt in vals:
                        if len(pt) > 1 and pt[1] is not None:
                            live_body_battery = pt[1]
    except Exception as e:
        logger.debug(f"Live BB fetch error: {e}")

    # Stress
    try:
        stress = g.get_stress_data(today)
        if isinstance(stress, dict):
            s_vals = stress.get("stressValuesArray", [])
            for pt in s_vals:
                if len(pt) > 1 and pt[1] is not None and pt[1] >= 0:
                    live_stress = pt[1]
            if live_stress is not None:
                if live_stress <= 25:
                    stress_status = "Rest"
                elif live_stress <= 50:
                    stress_status = "Low"
                elif live_stress <= 75:
                    stress_status = "Medium"
                else:
                    stress_status = "High"
    except Exception as e:
        logger.debug(f"Live stress fetch error: {e}")

    # Daily Summary
    try:
        summary = g.get_user_summary(today)
        if isinstance(summary, dict):
            steps = summary.get("totalSteps")
            live_hr = summary.get("restingHeartRate") or summary.get("minHeartRate")
    except Exception:
        pass

    res_data = {
        "status": "success",
        "date": today,
        "body_battery": live_body_battery,
        "charged": bb_charged,
        "drained": bb_drained,
        "stress_level": live_stress,
        "stress_status": stress_status,
        "heart_rate": live_hr,
        "steps": steps,
        "last_updated": datetime.now().isoformat()
    }
    _LIVE_CACHE["data"] = res_data
    _LIVE_CACHE["timestamp"] = now
    return JSONResponse(res_data)





@router.get("/summary")
def summary(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)")
):
    """Complete health and training metrics summary with optional custom date range filtering."""
    auth_mgr = DualAuthManager()
    if not auth_mgr.get_active_tokens():
        return JSONResponse({"error": "unauthenticated"}, status_code=401)

    db = DatabaseManager()
    session = db.get_session()
    
    steps = 0
    resting_hr = None
    sleep_score = None
    body_battery = None
    hrv_status = None
    stress_level = None
    respiration_rate = None
    spo2 = None
    vo2_max = None

    try:
        # Parse dates if provided
        start_d = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
        end_d = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None

        # Sleep query
        sleep_q = session.query(Sleep)
        if start_d and end_d:
            sleep_q = sleep_q.filter(Sleep.calendar_date.between(start_d, end_d))
        sleep_rec = sleep_q.order_by(Sleep.sleep_id.desc()).first()
        if sleep_rec and sleep_rec.sleep_score:
            sleep_score = sleep_rec.sleep_score
            
        # HRV query
        hrv_q = session.query(HRV)
        if start_d and end_d:
            hrv_q = hrv_q.filter(HRV.calendar_date.between(start_d, end_d))
        hrv_rec = hrv_q.order_by(HRV.calendar_date.desc()).first()
        if hrv_rec:
            hrv_status = hrv_rec.weekly_avg
            
        # Stress query
        stress_q = session.query(Stress)
        if start_d and end_d:
            stress_q = stress_q.filter(Stress.calendar_date.between(start_d, end_d))
        stress_rec = stress_q.order_by(Stress.calendar_date.desc()).first()
        if stress_rec:
            stress_level = stress_rec.avg_stress_level
            
        # Body Battery query
        battery_q = session.query(BodyBattery)
        if start_d and end_d:
            battery_q = battery_q.filter(BodyBattery.calendar_date.between(start_d, end_d))
        battery_rec = battery_q.order_by(BodyBattery.calendar_date.desc()).first()
        if battery_rec:
            body_battery = battery_rec.charged

    except Exception as e:
        logger.debug(f"Error querying summary metrics: {e}")
    finally:
        session.close()

    return JSONResponse({
        "start_date": start_date,
        "end_date": end_date,
        "steps": steps,
        "resting_hr": resting_hr,
        "sleep_score": sleep_score,
        "body_battery": body_battery,
        "hrv_status": hrv_status,
        "stress_level": stress_level,
        "respiration_rate": respiration_rate,
        "spo2": spo2,
        "vo2_max": vo2_max
    })


@router.get("/activities")
def activities(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(20, ge=1, le=100)
):
    """List activities from SQLite database with optional custom date range filtering."""
    auth_mgr = DualAuthManager()
    if not auth_mgr.get_active_tokens():
        return JSONResponse({"error": "unauthenticated"}, status_code=401)

    db = DatabaseManager()
    session = db.get_session()
    result = []
    try:
        q = session.query(Activity)
        if start_date and end_date:
            try:
                start_dt = datetime.strptime(f"{start_date} 00:00:00", "%Y-%m-%d %H:%M:%S")
                end_dt = datetime.strptime(f"{end_date} 23:59:59", "%Y-%m-%d %H:%M:%S")
                q = q.filter(Activity.start_ts.between(start_dt, end_dt))
            except Exception as pe:
                logger.warning(f"Date range parse warning: {pe}")

        recs = q.order_by(Activity.start_ts.desc()).limit(limit).all()
        for r in recs:
            result.append({
                "id": str(r.activity_id),
                "name": r.activity_name,
                "type": r.activity_type_key,
                "start_ts": str(r.start_ts),
                "duration": f"{int((r.duration or 0) / 60)} min",
                "distance": f"{(r.distance or 0) / 1000:.2f}",
                "avg_hr": r.average_hr,
                "max_hr": r.max_hr,
                "calories": r.calories
            })
    except Exception as e:
        logger.error(f"Error querying activities: {e}")
    finally:
        session.close()

    return JSONResponse(result)


@router.get("/activity/{activity_id}")
def activity_details(activity_id: int):
    """Fetch details of a single activity."""
    auth_mgr = DualAuthManager()
    if not auth_mgr.get_active_tokens():
        return JSONResponse({"error": "unauthenticated"}, status_code=401)

    db = DatabaseManager()
    session = db.get_session()
    try:
        act = session.query(Activity).filter_by(activity_id=activity_id).first()
        if not act:
            raise HTTPException(status_code=404, detail="Activity not found.")
        return JSONResponse({
            "id": str(act.activity_id),
            "name": act.activity_name,
            "type": act.activity_type_key,
            "start_ts": str(act.start_ts),
            "duration_sec": act.duration,
            "distance_m": act.distance,
            "avg_hr": act.average_hr,
            "max_hr": act.max_hr,
            "calories": act.calories,
            "elapsed_duration": act.elapsed_duration,
            "elevation_gain": act.elevation_gain
        })
    finally:
        session.close()


@router.post("/sync")
def sync():
    """Trigger manual data extraction sync with rate-limiting cooldown."""
    global _LAST_SYNC_TIME
    import time
    now = time.time()
    
    # Enforce minimum cooldown between manual syncs
    if now - _LAST_SYNC_TIME < _SYNC_COOLDOWN_SECONDS:
        remaining = int(_SYNC_COOLDOWN_SECONDS - (now - _LAST_SYNC_TIME))
        return JSONResponse({
            "status": "cooldown",
            "message": f"Sync rate limit protection active. Please wait {remaining} seconds before syncing again."
        })

    auth_mgr = DualAuthManager()
    if not auth_mgr.get_active_tokens():
        return JSONResponse({"error": "unauthenticated"}, status_code=401)

    try:
        _LAST_SYNC_TIME = now
        extractor = GarminExtractor()
        extractor.extract_all(days=7)
        GarminProcessor().process_ingest_directory()
        return JSONResponse({"status": "success", "message": "Extracted Garmin Connect data into SQLite database."})
    except Exception as e:
        logger.error(f"Sync error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

