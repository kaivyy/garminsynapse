"""FastAPI REST API routes for Garmin Synapse Web Dashboard."""
import logging
from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func
from garminsynapse.auth.manager import DualAuthManager
from garminsynapse.db.manager import DatabaseManager
from garminsynapse.db.schema import Activity, Sleep, HRV, Stress, BodyBattery, UserProfile, DailySummary
from garminsynapse.etl.extractor import GarminExtractor
from garminsynapse.etl.processor import GarminProcessor
from garminsynapse.core.api import GarminAPI

logger = logging.getLogger(__name__)
router = APIRouter()


def _run_background_sync(days: int = 7):
    """Run extraction and ETL processing in background so login returns immediately."""
    try:
        extractor = GarminExtractor()
        extractor.extract_all(days=days)
        GarminProcessor().process_ingest_directory()
        logger.info(f"Background sync for {days} days completed successfully.")
    except Exception as sync_err:
        logger.warning(f"Background sync warning: {sync_err}")


class LoginRequest(BaseModel):
    email: str
    password: Optional[str] = None
    mfa_code: Optional[str] = None


@router.get("/status")
def status():
    """System health & Auth status with seamless auto-refresh if expired."""
    auth_mgr = DualAuthManager()
    tokens = auth_mgr.get_active_tokens(auto_refresh=True)
    return JSONResponse({
        "status": "OK",
        "authenticated": tokens is not None,
        "mcp_server": "active",
        "database": "connected"
    })


@router.post("/auth/login")
def login(req: LoginRequest, background_tasks: BackgroundTasks):
    """Authenticate with Garmin Connect and trigger data extraction in the background.

    Two-step MFA flow:
      1. POST {email, password} -> if the account requires MFA, responds with
         {"status": "mfa_required"} instead of erroring.
      2. POST {email, mfa_code} -> completes the login using the code.
    """
    auth_mgr = DualAuthManager()
    try:
        if req.mfa_code:
            tokens = auth_mgr.login_resume(req.email, req.mfa_code)
        else:
            if not req.password:
                raise HTTPException(status_code=400, detail="password is required to start login")
            result = auth_mgr.login_start(req.email, req.password)
            if result.get("needs_mfa"):
                return JSONResponse({
                    "status": "mfa_required",
                    "message": "Enter the MFA code sent to your device.",
                    "email": req.email
                })
            tokens = result

        # Schedule extraction in background to avoid blocking the HTTP response
        background_tasks.add_task(_run_background_sync, 7)

        return JSONResponse({
            "status": "success",
            "message": "Authenticated successfully with Garmin Connect.",
            "source": tokens.get("source", "oauth")
        })
    except HTTPException:
        raise
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
        # Fall back to stale cache on error.
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

    try:
        steps_list = g.get_daily_steps(today, today)
        if steps_list and isinstance(steps_list, list):
            steps = steps_list[0].get("totalSteps")
    except Exception as se:
        logger.debug(f"Live daily steps error: {se}")

    try:
        summary = g.get_user_summary(today)
        if isinstance(summary, dict):
            if steps is None:
                steps = summary.get("totalSteps")
            live_hr = summary.get("restingHeartRate") or summary.get("minHeartRate")
    except Exception:
        pass

    sleep_score = None
    sleep_duration_mins = None
    nap_duration_mins = None
    try:
        sleep_data = g.get_sleep_data(today)
        if isinstance(sleep_data, dict):
            daily_dto = sleep_data.get("dailySleepDTO", {})
            sleep_score = daily_dto.get("sleepScores", {}).get("overall", {}).get("value")
            sleep_sec = daily_dto.get("sleepTimeSeconds")
            if sleep_sec:
                sleep_duration_mins = round(sleep_sec / 60)
            nap_sec = daily_dto.get("napTimeSeconds")
            if nap_sec:
                nap_duration_mins = round(nap_sec / 60)
    except Exception as sle:
        logger.debug(f"Live sleep/nap error: {sle}")

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
        "sleep_score": sleep_score,
        "sleep_duration_mins": sleep_duration_mins,
        "nap_duration_mins": nap_duration_mins,
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
    if not auth_mgr.get_active_tokens(auto_refresh=True):
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
        start_d = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
        end_d = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None
        is_range = bool((start_d and end_d and start_d != end_d) or (not start_d and not end_d))

        daily_q = session.query(DailySummary)
        if start_d and end_d:
            daily_q = daily_q.filter(DailySummary.calendar_date.between(start_d, end_d))
        all_daily = daily_q.order_by(DailySummary.calendar_date.desc()).all()
        daily_rec = all_daily[0] if all_daily else None

        sleep_q = session.query(Sleep)
        if start_d and end_d:
            sleep_q = sleep_q.filter(Sleep.calendar_date.between(start_d, end_d))
        all_sleep = sleep_q.order_by(Sleep.calendar_date.desc()).all()
        sleep_rec = all_sleep[0] if all_sleep else None

        hrv_q = session.query(HRV)
        if start_d and end_d:
            hrv_q = hrv_q.filter(HRV.calendar_date.between(start_d, end_d))
        all_hrv = hrv_q.order_by(HRV.calendar_date.desc()).all()
        hrv_rec = all_hrv[0] if all_hrv else None

        stress_q = session.query(Stress)
        if start_d and end_d:
            stress_q = stress_q.filter(Stress.calendar_date.between(start_d, end_d))
        all_stress = stress_q.order_by(Stress.calendar_date.desc()).all()
        stress_rec = all_stress[0] if all_stress else None

        battery_q = session.query(BodyBattery)
        if start_d and end_d:
            battery_q = battery_q.filter(BodyBattery.calendar_date.between(start_d, end_d))
        all_battery = battery_q.order_by(BodyBattery.calendar_date.desc()).all()
        battery_rec = all_battery[0] if all_battery else None

        # If single-day requested is today and there is no record for today yet,
        # fallback to the most recent day that has data.
        today_d = datetime.now().date()
        is_today = (start_d == today_d and end_d == today_d) or (start_d == today_d and not end_d)
        if not is_range and is_today and not daily_rec and not sleep_rec and not stress_rec:
            daily_rec = session.query(DailySummary).order_by(DailySummary.calendar_date.desc()).first()
            sleep_rec = session.query(Sleep).order_by(Sleep.calendar_date.desc()).first()
            hrv_rec = session.query(HRV).order_by(HRV.calendar_date.desc()).first()
            stress_rec = session.query(Stress).filter(Stress.avg_stress_level.isnot(None)).order_by(Stress.calendar_date.desc()).first()
            battery_rec = session.query(BodyBattery).filter(BodyBattery.charged.isnot(None)).order_by(BodyBattery.calendar_date.desc()).first()

        prof = session.query(UserProfile).filter_by(latest=True).first()
        if prof:
            vo2_max = prof.vo2_max_running or prof.vo2_max_cycling

        if is_range and all_daily:
            steps_list = [r.steps for r in all_daily if r.steps is not None]
            total_steps = sum(steps_list)
            avg_steps = round(total_steps / len(steps_list)) if steps_list else 0
            steps = total_steps
            
            dists = [r.total_distance_meters for r in all_daily if r.total_distance_meters is not None]
            total_distance_km = round(sum(dists) / 1000.0, 2)
            
            cals = [r.total_calories for r in all_daily if r.total_calories is not None]
            total_calories = sum(cals)
            
            rhrs = [r.resting_hr for r in all_daily if r.resting_hr is not None]
            resting_hr = round(sum(rhrs) / len(rhrs)) if rhrs else None
            
            resps = [r.avg_respiration for r in all_daily if r.avg_respiration is not None]
            respiration_rate = round(sum(resps) / len(resps), 1) if resps else None
            
            spo2s = [r.avg_spo2 for r in all_daily if r.avg_spo2 is not None]
            spo2 = round(sum(spo2s) / len(spo2s), 1) if spo2s else None
            
            sleep_scores = [r.sleep_score for r in all_sleep if r.sleep_score is not None]
            sleep_score = round(sum(sleep_scores) / len(sleep_scores)) if sleep_scores else None
            
            stress_vals = [r.avg_stress_level for r in all_stress if r.avg_stress_level is not None]
            stress_level = round(sum(stress_vals) / len(stress_vals)) if stress_vals else None
            
            bat_vals = [r.charged for r in all_battery if r.charged is not None]
            body_battery = round(sum(bat_vals) / len(bat_vals)) if bat_vals else None
            
            hrv_vals = [r.weekly_avg or r.last_night_avg for r in all_hrv if (r.weekly_avg or r.last_night_avg) is not None]
            hrv_status = round(sum(hrv_vals) / len(hrv_vals)) if hrv_vals else None
            days_count = len(all_daily)
        else:
            if daily_rec:
                if daily_rec.steps is not None: steps = daily_rec.steps
                if daily_rec.resting_hr is not None: resting_hr = daily_rec.resting_hr
                if daily_rec.avg_respiration is not None: respiration_rate = daily_rec.avg_respiration
                if daily_rec.avg_spo2 is not None: spo2 = daily_rec.avg_spo2
            if sleep_rec and sleep_rec.sleep_score:
                sleep_score = sleep_rec.sleep_score
            if hrv_rec:
                hrv_status = hrv_rec.weekly_avg
            if stress_rec:
                stress_level = stress_rec.avg_stress_level
            if battery_rec:
                body_battery = battery_rec.charged
            total_steps = steps
            avg_steps = steps
            total_distance_km = round((daily_rec.total_distance_meters or 0) / 1000.0, 2) if daily_rec else 0.0
            total_calories = daily_rec.total_calories if daily_rec and daily_rec.total_calories else 0
            days_count = 1

    except Exception as e:
        logger.debug(f"Error querying summary metrics: {e}")
    finally:
        session.close()

    return JSONResponse({
        "start_date": start_date,
        "end_date": end_date,
        "is_range": is_range,
        "days_count": days_count,
        "steps": steps,
        "total_steps": total_steps,
        "avg_steps": avg_steps,
        "total_distance_km": total_distance_km,
        "total_calories": total_calories,
        "resting_hr": resting_hr,
        "sleep_score": sleep_score,
        "body_battery": body_battery,
        "hrv_status": hrv_status,
        "stress_level": stress_level,
        "respiration_rate": respiration_rate,
        "spo2": spo2,
        "vo2_max": vo2_max
    })


@router.get("/readiness")
def training_readiness(date_str: Optional[str] = None, date: Optional[str] = None):
    """Fetch Training Readiness score and recovery factor breakdown."""
    import json
    from pathlib import Path
    target_d = date or date_str or datetime.now().strftime("%Y-%m-%d")
    ingest_dir = Path.home() / "garminsynapse" / "garmin_files" / "ingest"
    if not ingest_dir.exists():
        ingest_dir = Path("/root/garminsynapse/garmin_files/ingest")
    
    data_item = None
    # 1. Try local ingest file first
    ingest_file = ingest_dir / f"{target_d}_READINESS.json"
    if ingest_file.exists():
        try:
            with open(ingest_file, "r", encoding="utf-8") as f:
                content = json.load(f)
                if isinstance(content, list) and content:
                    data_item = content[0]
                elif isinstance(content, dict):
                    data_item = content
        except Exception:
            pass

    # 2. Try Garmin API
    if not data_item:
        api = GarminAPI()
        if api._garmin_instance and hasattr(api._garmin_instance, "get_training_readiness"):
            try:
                res = api._garmin_instance.get_training_readiness(target_d)
                if isinstance(res, list) and res:
                    data_item = res[0]
                elif isinstance(res, dict):
                    data_item = res
                
                # If target was today and empty, fallback to yesterday
                if not data_item and not (date or date_str):
                    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                    res = api._garmin_instance.get_training_readiness(yesterday)
                    if isinstance(res, list) and res:
                        data_item = res[0]
                        target_d = yesterday
            except Exception as e:
                logger.debug(f"Error calling live get_training_readiness: {e}")

    # 3. If still not found, search newest _READINESS.json
    if not data_item and ingest_dir.exists():
        readiness_files = sorted(ingest_dir.glob("*_READINESS.json"), reverse=True)
        for rf in readiness_files:
            try:
                with open(rf, "r", encoding="utf-8") as f:
                    content = json.load(f)
                    if isinstance(content, list) and content and content[0].get("score") is not None:
                        data_item = content[0]
                        target_d = rf.stem.split("_")[0]
                        break
            except Exception:
                continue

    if data_item:
        score = data_item.get("score") or data_item.get("trainingReadiness")
        level = data_item.get("level") or ""
        feedback = data_item.get("feedbackShort") or data_item.get("feedbackLong") or level
        clean_feedback = feedback.replace("_", " ").title() if feedback else "Optimal Recovery"
        return JSONResponse({
            "status": "success",
            "date": target_d,
            "score": score,
            "level": level,
            "feedback": clean_feedback,
            "data": data_item
        })

    return JSONResponse({"status": "unavailable", "message": "No readiness data available", "score": None})


@router.get("/predictions")
def race_predictions():
    """Fetch race predictions (5K, 10K, Half Marathon, Marathon) for user."""
    api = GarminAPI()
    if not api._garmin_instance:
        return JSONResponse({"status": "error", "message": "Not authenticated with Garmin"})
    try:
        if hasattr(api._garmin_instance, "get_race_predictions"):
            res = api._garmin_instance.get_race_predictions()
            return JSONResponse({"status": "success", "data": res})
        return JSONResponse({"status": "unavailable", "message": "Race predictions not supported on this model"})
    except Exception as e:
        return JSONResponse({"status": "unavailable", "message": "No running activity recorded yet to compute race predictions"})



@router.get("/badges")
def badges():
    """Fetch user's earned Garmin Connect badges & achievements."""
    api = GarminAPI()
    if not api._garmin_instance:
        return JSONResponse({"status": "error", "message": "Not authenticated with Garmin"})
    try:
        if hasattr(api._garmin_instance, "get_earned_badges"):
            res = api._garmin_instance.get_earned_badges()
            return JSONResponse({"status": "success", "data": res})
        return JSONResponse({"status": "unavailable", "message": "Badges not available"})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)})


@router.get("/profile")
def user_profile():
    """Fetch Garmin social and biometric profile."""
    api = GarminAPI()
    if not api._garmin_instance:
        return JSONResponse({"status": "error", "message": "Not authenticated with Garmin"})
    try:
        res = api.get_user_profile()
        return JSONResponse({"status": "success", "data": res})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)})


@router.get("/activities")
def activities(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=500)
):
    """List activities from SQLite database with optional custom date range filtering."""
    auth_mgr = DualAuthManager()
    if not auth_mgr.get_active_tokens(auto_refresh=True):
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
                "duration_sec": r.duration,
                "distance": f"{(r.distance or 0) / 1000:.2f}",
                "distance_m": r.distance,
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
    if not auth_mgr.get_active_tokens(auto_refresh=True):
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
    
    if now - _LAST_SYNC_TIME < _SYNC_COOLDOWN_SECONDS:
        remaining = int(_SYNC_COOLDOWN_SECONDS - (now - _LAST_SYNC_TIME))
        return JSONResponse({
            "status": "cooldown",
            "message": f"Sync rate limit protection active. Please wait {remaining} seconds before syncing again."
        })

    auth_mgr = DualAuthManager()
    if not auth_mgr.get_active_tokens(auto_refresh=True):
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



@router.get("/activities/{activity_id}/splits")
def get_activity_splits_route(activity_id: int):
    """Get per-km or per-lap splits for a specific activity."""
    auth_mgr = DualAuthManager()
    tokens = auth_mgr.get_active_tokens(auto_refresh=True)
    if not tokens:
        return JSONResponse({"error": "unauthenticated"}, status_code=401)
    
    headers = tokens.get("headers", {})
    if not headers:
        if "access_token" in tokens:
            headers["Authorization"] = f"Bearer {tokens['access_token']}"
        elif "cookies" in tokens:
            headers["Cookie"] = "; ".join([f"{k}={v}" for k, v in tokens["cookies"].items()])
        
    api = GarminAPI(session_headers=headers)
    try:
        data = api.get_activity_splits(activity_id)
        return data
    except Exception as e:
        logger.error(f"Error fetching splits for activity {activity_id}: {e}")
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": str(e)}, status_code=500)
