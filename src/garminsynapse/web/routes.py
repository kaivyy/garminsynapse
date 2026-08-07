"""FastAPI REST API routes for Garmin Synapse Web Dashboard."""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from garminsynapse.auth.manager import DualAuthManager
from garminsynapse.db.manager import DatabaseManager
from garminsynapse.db.schema import Activity, Sleep, HRV, Stress, BodyBattery, UserProfile
from garminsynapse.etl.extractor import GarminExtractor

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


@router.get("/summary")
def summary():
    """Complete health and training metrics summary from SQLite database."""
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
        sleep_rec = session.query(Sleep).order_by(Sleep.sleep_id.desc()).first()
        if sleep_rec and sleep_rec.sleep_score:
            sleep_score = sleep_rec.sleep_score
            
        hrv_rec = session.query(HRV).order_by(HRV.calendar_date.desc()).first()
        if hrv_rec:
            hrv_status = hrv_rec.weekly_avg
            
        stress_rec = session.query(Stress).order_by(Stress.calendar_date.desc()).first()
        if stress_rec:
            stress_level = stress_rec.average_stress_level
            
        battery_rec = session.query(BodyBattery).order_by(BodyBattery.calendar_date.desc()).first()
        if battery_rec:
            body_battery = battery_rec.charged_value
    except Exception as e:
        logger.debug(f"Error querying summary metrics: {e}")
    finally:
        session.close()

    return JSONResponse({
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
def activities():
    """List recent activities from SQLite database."""
    auth_mgr = DualAuthManager()
    if not auth_mgr.get_active_tokens():
        return JSONResponse({"error": "unauthenticated"}, status_code=401)

    db = DatabaseManager()
    session = db.get_session()
    result = []
    try:
        recs = session.query(Activity).order_by(Activity.start_ts.desc()).limit(20).all()
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
    """Trigger manual data extraction sync."""
    auth_mgr = DualAuthManager()
    if not auth_mgr.get_active_tokens():
        return JSONResponse({"error": "unauthenticated"}, status_code=401)

    try:
        extractor = GarminExtractor()
        extractor.extract_all(days=14)
        return JSONResponse({"status": "success", "message": "Extracted real Garmin Connect data into SQLite database."})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
