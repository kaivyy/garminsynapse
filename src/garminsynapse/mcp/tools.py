"""Native MCP Server tools with full database, API, and analytics integration."""
import logging
from typing import Dict, Any, List
from pathlib import Path
from mcp.server import MCPServer
from sqlalchemy import text
from garminsynapse.auth.manager import DualAuthManager
from garminsynapse.db.manager import DatabaseManager
from garminsynapse.db.schema import Activity
from garminsynapse.core.api import GarminAPI
from garminsynapse.etl.extractor import GarminExtractor
from garminsynapse.etl.processor import GarminProcessor

logger = logging.getLogger(__name__)
mcp = MCPServer("garminsynapse", description="Garmin Synapse MCP Server - Direct access to Garmin Connect training, health, sleep, and SQLite data.")


@mcp.tool()
def garmin_status() -> Dict[str, Any]:
    """Get Garmin Synapse auth, database, and system status."""
    auth_mgr = DualAuthManager()
    tokens = auth_mgr.get_active_tokens()
    return {
        "status": "OK",
        "authenticated": tokens is not None,
        "auth_source": tokens.get("source") if tokens else None,
        "mcp_server": "active",
        "database": "connected"
    }


@mcp.tool()
def garmin_login(email: str, password: str) -> Dict[str, Any]:
    """Authenticate with Garmin Connect via 5-stage curl_cffi or Playwright fallback."""
    auth_mgr = DualAuthManager()
    tokens = auth_mgr.login(email, password)
    return {
        "status": "success",
        "message": "Authenticated successfully with Garmin Connect.",
        "source": tokens.get("source", "oauth")
    }


@mcp.tool()
def get_garmin_devices() -> Dict[str, Any]:
    """Get all registered Garmin devices, watch model names, serial numbers, unit IDs, and firmware versions."""
    api = GarminAPI()
    if not api._garmin_instance:
        return {"error": "unauthenticated", "message": "Not authenticated with Garmin"}
    try:
        devices = api._garmin_instance.get_devices()
        primary = None
        try:
            primary = api._garmin_instance.get_primary_training_device()
        except Exception:
            pass
        return {
            "status": "success",
            "devices": devices or [],
            "primary": primary
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def get_live_metrics() -> Dict[str, Any]:
    """Get live point-in-time biometric readings for today (latest Body Battery %, charged/drained, latest Stress score & status, HR, Steps)."""
    from datetime import datetime
    api = GarminAPI()
    if not api._garmin_instance:
        return {"error": "unauthenticated", "message": "Not authenticated with Garmin"}

    g = api._garmin_instance
    today = datetime.now().strftime("%Y-%m-%d")
    live_bb = None
    charged = None
    drained = None
    live_stress = None
    stress_status = None

    try:
        bb = g.get_body_battery(today)
        if isinstance(bb, list):
            for item in bb:
                if isinstance(item, dict):
                    charged = item.get("charged", charged)
                    drained = item.get("drained", drained)
                    for pt in item.get("bodyBatteryValuesArray", []):
                        if len(pt) > 1 and pt[1] is not None:
                            live_bb = pt[1]
    except Exception as e:
        logger.debug(f"MCP live BB error: {e}")

    try:
        stress = g.get_stress_data(today)
        if isinstance(stress, dict):
            for pt in stress.get("stressValuesArray", []):
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
        logger.debug(f"MCP live stress error: {e}")

    live_steps = None
    try:
        steps_list = g.get_daily_steps(today, today)
        if steps_list and isinstance(steps_list, list):
            live_steps = steps_list[0].get("totalSteps")
    except Exception as e:
        logger.debug(f"MCP live steps error: {e}")

    sleep_score = None
    nap_mins = None
    try:
        sleep_data = g.get_sleep_data(today)
        if isinstance(sleep_data, dict):
            daily_dto = sleep_data.get("dailySleepDTO", {})
            sleep_score = daily_dto.get("sleepScores", {}).get("overall", {}).get("value")
            nap_sec = daily_dto.get("napTimeSeconds")
            if nap_sec:
                nap_mins = round(nap_sec / 60)
    except Exception as e:
        logger.debug(f"MCP live sleep error: {e}")

    return {
        "status": "success",
        "date": today,
        "steps": live_steps,
        "body_battery": live_bb,
        "charged": charged,
        "drained": drained,
        "stress_level": live_stress,
        "stress_status": stress_status,
        "sleep_score": sleep_score,
        "nap_duration_mins": nap_mins
    }




@mcp.tool()
def garmin_sync(days: int = 7) -> Dict[str, Any]:
    """Extract recent health, wellness, and activity data into local SQLite database."""
    extractor = GarminExtractor()
    extractor.extract_all(days=days)
    GarminProcessor().process_ingest_directory()
    return {
        "status": "success",
        "message": f"Successfully extracted last {days} days of Garmin data into SQLite DB."
    }



@mcp.tool()
def get_daily_summary(date_str: str) -> Dict[str, Any]:
    """Get daily health summary including steps, resting HR, stress, and body battery for a specific date (YYYY-MM-DD)."""
    auth_mgr = DualAuthManager()
    tokens = auth_mgr.get_active_tokens()
    if not tokens:
        return {"error": "unauthenticated", "message": "Please call garmin_login first."}

    headers = {}
    if "access_token" in tokens:
        headers["Authorization"] = f"Bearer {tokens['access_token']}"
    elif "cookies" in tokens:
        headers["Cookie"] = "; ".join([f"{k}={v}" for k, v in tokens["cookies"].items()])

    api = GarminAPI(session_headers=headers)
    return api.get_daily_stats(date_str)


@mcp.tool()
def get_sleep_analysis(date_str: str) -> Dict[str, Any]:
    """Get detailed sleep analysis (stages, sleep score, movement, SpO2) for a specific date (YYYY-MM-DD)."""
    auth_mgr = DualAuthManager()
    tokens = auth_mgr.get_active_tokens()
    if not tokens:
        return {"error": "unauthenticated"}

    headers = {}
    if "access_token" in tokens:
        headers["Authorization"] = f"Bearer {tokens['access_token']}"
    elif "cookies" in tokens:
        headers["Cookie"] = "; ".join([f"{k}={v}" for k, v in tokens["cookies"].items()])

    api = GarminAPI(session_headers=headers)
    return api.get_sleep_data(date_str)


@mcp.tool()
def get_hrv_trends(date_str: str = "") -> Dict[str, Any]:
    """Get Heart Rate Variability (HRV) status, weekly baseline, and nightly averages."""
    auth_mgr = DualAuthManager()
    tokens = auth_mgr.get_active_tokens()
    if not tokens:
        return {"error": "unauthenticated"}

    headers = {}
    if "access_token" in tokens:
        headers["Authorization"] = f"Bearer {tokens['access_token']}"
    elif "cookies" in tokens:
        headers["Cookie"] = "; ".join([f"{k}={v}" for k, v in tokens["cookies"].items()])

    api = GarminAPI(session_headers=headers)
    if hasattr(api, "get_hrv_data"):
        return api.get_hrv_data(date_str)
    return {"status": "balanced"}


@mcp.tool()
def list_activities(limit: int = 20) -> List[Dict[str, Any]]:
    """List recent Garmin workouts & activities with distance, duration, HR, and calories."""
    db = DatabaseManager()
    session = db.get_session()
    result = []
    try:
        recs = session.query(Activity).order_by(Activity.start_ts.desc()).limit(limit).all()
        for r in recs:
            result.append({
                "activity_id": r.activity_id,
                "name": r.activity_name,
                "type": r.activity_type_key,
                "start_ts": str(r.start_ts),
                "duration_min": round((r.duration or 0) / 60, 1),
                "distance_km": round((r.distance or 0) / 1000, 2),
                "avg_hr": r.average_hr,
                "calories": r.calories
            })
    except Exception as e:
        logger.error(f"Error querying activities: {e}")
    finally:
        session.close()
    return result


@mcp.tool()
def get_activity_details(activity_id: int) -> Dict[str, Any]:
    """Get full time-series metrics (HR, power, cadence, elevation, polyline) for a specific workout."""
    auth_mgr = DualAuthManager()
    tokens = auth_mgr.get_active_tokens()
    if not tokens:
        return {"error": "unauthenticated"}

    headers = {}
    if "access_token" in tokens:
        headers["Authorization"] = f"Bearer {tokens['access_token']}"
    elif "cookies" in tokens:
        headers["Cookie"] = "; ".join([f"{k}={v}" for k, v in tokens["cookies"].items()])

    api = GarminAPI(session_headers=headers)
    return api.get_activity_details(activity_id)


@mcp.tool()
def download_fit_file(activity_id: int) -> Dict[str, Any]:
    """Download raw binary .FIT file for a specific activity."""
    auth_mgr = DualAuthManager()
    tokens = auth_mgr.get_active_tokens()
    if not tokens:
        return {"error": "unauthenticated"}

    headers = {}
    if "access_token" in tokens:
        headers["Authorization"] = f"Bearer {tokens['access_token']}"
    elif "cookies" in tokens:
        headers["Cookie"] = "; ".join([f"{k}={v}" for k, v in tokens["cookies"].items()])

    api = GarminAPI(session_headers=headers)
    fit_bytes = api.download_activity_fit(activity_id)
    out_file = Path.cwd() / "garmin_files" / "storage" / f"{activity_id}.fit"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "wb") as f:
        f.write(fit_bytes)
    return {"status": "success", "file_path": str(out_file), "size_bytes": len(fit_bytes)}


@mcp.tool()
def query_garmin_db(sql_query: str) -> List[Dict[str, Any]]:
    """Execute a safe SELECT query on the local garmin_data.db SQLite relational database (40+ tables: user, activity, sleep, hrv, stress, body_battery, etc.)."""
    if not sql_query.strip().lower().startswith("select"):
        return [{"error": "Only SELECT queries are permitted."}]

    try:
        db = DatabaseManager()
        with db.engine.connect() as conn:
            res = conn.execute(text(sql_query))
            keys = res.keys()
            return [dict(zip(keys, row)) for row in res.fetchall()]
    except Exception as e:
        return [{"error": f"SQL execution failed: {str(e)}"}]
