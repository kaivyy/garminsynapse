"""ETL Processor for parsing FIT, TCX, and JSON files into SQLite database."""
import json
import logging
import re
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, Optional
from garminsynapse.db.manager import DatabaseManager
from garminsynapse.db.schema import User, UserProfile, Activity, ActivityTsMetric, Sleep, HRV, Stress, BodyBattery, DailySummary

logger = logging.getLogger(__name__)

DEFAULT_INGEST_DIR = Path.cwd() / "garmin_files" / "ingest"
DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")


class GarminProcessor:
    """Parses raw downloaded health & activity files into SQLite records."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

    def _extract_user_id(self, session, data: dict) -> int:
        """Extract user_id from various Garmin JSON schemas with fallback to existing User."""
        uid = (
            data.get("userProfilePK")
            or data.get("userProfilePk")
            or data.get("userProfileId")
            or data.get("userId")
            or data.get("id")
        )
        if uid:
            return int(uid)
        
        from garminsynapse.db.schema import UserProfile, User
        prof = session.query(UserProfile).first()
        if prof and prof.user_id:
            return int(prof.user_id)
            
        u = session.query(User).filter(User.user_id != 0).first()
        if u:
            return int(u.user_id)
            
        return 0

    def _ensure_user_exists(self, session, user_id: int):
        """Ensure User record exists for FK constraints."""
        if not user_id:
            user_id = 0
        u = session.query(User).filter_by(user_id=user_id).first()
        if not u:
            u = User(user_id=user_id)
            session.add(u)
            session.flush()

    def process_ingest_directory(self, ingest_dir: Optional[Path] = None) -> int:
        """Process all JSON and FIT files in ingest folder into SQLite DB."""
        target_dir = Path(ingest_dir) if ingest_dir else DEFAULT_INGEST_DIR
        processed_count = 0

        for file_path in target_dir.glob("*.json"):
            try:
                if file_path.name == "activities_list.json":
                    self.process_activities_list(file_path)
                elif file_path.name == "user_profile.json":
                    self.process_user_profile(file_path)
                else:
                    self.process_json_summary(file_path)
                processed_count += 1
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")

        for fit_path in target_dir.glob("*.fit"):
            try:
                self.process_fit_file(fit_path)
                processed_count += 1
            except Exception as e:
                logger.error(f"Error processing {fit_path}: {e}")

        return processed_count

    def process_user_profile(self, json_path: Path) -> None:
        """Parse user_profile.json and upsert into UserProfile table."""
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return

        session = self.db_manager.get_session()
        try:
            user_id = self._extract_user_id(session, data)
            self._ensure_user_exists(session, user_id)
            user_data = data.get("userData", {})

            existing = session.query(UserProfile).filter_by(user_id=user_id, latest=True).first()
            gender = user_data.get("gender")
            weight = user_data.get("weight")
            if weight and weight > 1000:
                weight = round(weight / 1000, 2)  # Convert grams to kg
            height = user_data.get("height")
            vo2_run = user_data.get("vo2MaxRunning")
            vo2_bike = user_data.get("vo2MaxCycling")

            if existing:
                existing.gender = gender
                existing.weight = weight
                existing.height = height
                existing.vo2_max_running = vo2_run
                existing.vo2_max_cycling = vo2_bike
            else:
                session.add(UserProfile(
                    user_id=user_id,
                    gender=gender,
                    weight=weight,
                    height=height,
                    vo2_max_running=vo2_run,
                    vo2_max_cycling=vo2_bike,
                    latest=True
                ))
            session.commit()
            logger.info(f"Processed UserProfile record for user {user_id}")
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to process user profile {json_path}: {e}")
        finally:
            session.close()

    def process_json_summary(self, json_path: Path) -> None:
        """Parse JSON health summary file and upsert records."""
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        session = self.db_manager.get_session()
        try:
            date_match = DATE_PATTERN.search(json_path.name)
            cal_date_str = date_match.group(1) if date_match else None

            if "dailySleepDTO" in data:
                sleep_dto = data["dailySleepDTO"]
                user_id = self._extract_user_id(session, sleep_dto)
                self._ensure_user_exists(session, user_id)

                cal_str = cal_date_str or sleep_dto.get("calendarDate") or datetime.utcnow().strftime("%Y-%m-%d")
                parsed_date = datetime.strptime(cal_str, "%Y-%m-%d").date()

                scores = sleep_dto.get("sleepScores")
                sleep_score_val = None
                if isinstance(scores, dict):
                    overall = scores.get("overall")
                    if isinstance(overall, dict):
                        sleep_score_val = overall.get("value")

                existing_sleep = session.query(Sleep).filter_by(user_id=user_id, calendar_date=parsed_date).first()
                nap_sec = sleep_dto.get("napTimeSeconds")

                if existing_sleep:
                    existing_sleep.total_sleep_seconds = sleep_dto.get("sleepTimeSeconds")
                    existing_sleep.sleep_score = sleep_score_val
                    if nap_sec is not None:
                        existing_sleep.nap_seconds = nap_sec
                else:
                    session.add(Sleep(
                        user_id=user_id,
                        calendar_date=parsed_date,
                        total_sleep_seconds=sleep_dto.get("sleepTimeSeconds"),
                        nap_seconds=nap_sec,
                        sleep_score=sleep_score_val
                    ))
                session.commit()
                logger.info(f"Processed sleep JSON record for {parsed_date}")

            elif "_STATS" in json_path.name and isinstance(data, dict):
                user_id = self._extract_user_id(session, data)
                self._ensure_user_exists(session, user_id)
                cal_str = cal_date_str or data.get("calendarDate") or datetime.utcnow().strftime("%Y-%m-%d")
                parsed_date = datetime.strptime(cal_str, "%Y-%m-%d").date()

                existing = session.query(DailySummary).filter_by(user_id=user_id, calendar_date=parsed_date).first()
                steps = data.get("totalSteps")
                step_goal = data.get("dailyStepGoal", 10000)
                dist = data.get("totalDistance")
                rhr = data.get("restingHeartRate")
                min_hr = data.get("minHeartRate")
                max_hr = data.get("maxHeartRate")
                cals = data.get("totalKilocalories")
                spo2_val = data.get("averageSpo2") or data.get("averageSpO2")

                if existing:
                    if steps is not None: existing.steps = steps
                    if step_goal is not None: existing.step_goal = step_goal
                    if dist is not None: existing.total_distance_meters = dist
                    if rhr is not None: existing.resting_hr = rhr
                    if min_hr is not None: existing.min_hr = min_hr
                    if max_hr is not None: existing.max_hr = max_hr
                    if cals is not None: existing.total_calories = cals
                    if spo2_val is not None: existing.avg_spo2 = spo2_val
                else:
                    session.add(DailySummary(
                        user_id=user_id,
                        calendar_date=parsed_date,
                        steps=steps,
                        step_goal=step_goal,
                        total_distance_meters=dist,
                        resting_hr=rhr,
                        min_hr=min_hr,
                        max_hr=max_hr,
                        total_calories=cals,
                        avg_spo2=spo2_val
                    ))

                # Also populate Stress and BodyBattery from _STATS if available
                avg_stress = data.get("averageStressLevel") or data.get("avgStressLevel")
                max_stress = data.get("maxStressLevel")
                if avg_stress is not None or max_stress is not None:
                    existing_stress = session.query(Stress).filter_by(user_id=user_id, calendar_date=parsed_date).first()
                    if existing_stress:
                        if avg_stress is not None: existing_stress.avg_stress_level = avg_stress
                        if max_stress is not None: existing_stress.max_stress_level = max_stress
                    else:
                        session.add(Stress(user_id=user_id, calendar_date=parsed_date,
                            avg_stress_level=avg_stress, max_stress_level=max_stress))

                bb_charged = data.get("bodyBatteryChargedValue")
                bb_drained = data.get("bodyBatteryDrainedValue")
                if bb_charged is not None or bb_drained is not None:
                    existing_bb = session.query(BodyBattery).filter_by(user_id=user_id, calendar_date=parsed_date).first()
                    if existing_bb:
                        if bb_charged is not None: existing_bb.charged = bb_charged
                        if bb_drained is not None: existing_bb.drained = bb_drained
                    else:
                        session.add(BodyBattery(user_id=user_id, calendar_date=parsed_date,
                            charged=bb_charged, drained=bb_drained))

                session.commit()
                logger.info(f"Processed DailySummary record for {parsed_date}")

            elif "_RESPIRATION" in json_path.name and isinstance(data, dict):
                user_id = self._extract_user_id(session, data)
                self._ensure_user_exists(session, user_id)
                cal_str = cal_date_str or data.get("calendarDate") or datetime.utcnow().strftime("%Y-%m-%d")
                parsed_date = datetime.strptime(cal_str, "%Y-%m-%d").date()

                avg_resp = data.get("avgWakingRespirationValue") or data.get("avgSleepRespirationValue") or data.get("avgRespirationValue")
                if avg_resp is not None:
                    existing = session.query(DailySummary).filter_by(user_id=user_id, calendar_date=parsed_date).first()
                    if existing:
                        existing.avg_respiration = avg_resp
                    else:
                        session.add(DailySummary(user_id=user_id, calendar_date=parsed_date, avg_respiration=avg_resp))
                    session.commit()

            elif "_SPO2" in json_path.name and isinstance(data, dict):
                user_id = self._extract_user_id(session, data)
                self._ensure_user_exists(session, user_id)
                cal_str = cal_date_str or data.get("calendarDate") or datetime.utcnow().strftime("%Y-%m-%d")
                parsed_date = datetime.strptime(cal_str, "%Y-%m-%d").date()

                avg_spo2 = data.get("averageSpO2") or data.get("averageSingleSpO2")
                if avg_spo2 is not None:
                    existing = session.query(DailySummary).filter_by(user_id=user_id, calendar_date=parsed_date).first()
                    if existing:
                        existing.avg_spo2 = avg_spo2
                    else:
                        session.add(DailySummary(user_id=user_id, calendar_date=parsed_date, avg_spo2=avg_spo2))
                    session.commit()

            elif "_STRESS" in json_path.name and isinstance(data, dict):
                user_id = self._extract_user_id(session, data)
                self._ensure_user_exists(session, user_id)
                cal_str = cal_date_str or data.get("calendarDate") or datetime.utcnow().strftime("%Y-%m-%d")
                parsed_date = datetime.strptime(cal_str, "%Y-%m-%d").date()
                existing = session.query(Stress).filter_by(user_id=user_id, calendar_date=parsed_date).first()
                avg_stress = data.get("avgStressLevel") or data.get("averageStressLevel") or data.get("overallStressLevel")
                max_stress = data.get("maxStressLevel")
                if existing:
                    if avg_stress is not None: existing.avg_stress_level = avg_stress
                    if max_stress is not None: existing.max_stress_level = max_stress
                else:
                    session.add(Stress(user_id=user_id, calendar_date=parsed_date,
                        avg_stress_level=avg_stress,
                        max_stress_level=max_stress))
                session.commit()

            elif "_HRV" in json_path.name and isinstance(data, dict):
                user_id = self._extract_user_id(session, data)
                self._ensure_user_exists(session, user_id)
                cal_str = cal_date_str or datetime.utcnow().strftime("%Y-%m-%d")
                parsed_date = datetime.strptime(cal_str, "%Y-%m-%d").date()
                existing = session.query(HRV).filter_by(user_id=user_id, calendar_date=parsed_date).first()
                summary = data.get("hrvSummary", data)
                weekly = summary.get("weeklyAvg") if isinstance(summary, dict) else None
                nightly = summary.get("lastNightAvg") if isinstance(summary, dict) else None
                status_str = summary.get("status") if isinstance(summary, dict) else None
                if existing:
                    existing.weekly_avg = weekly
                    existing.last_night_avg = nightly
                    existing.status = status_str
                else:
                    session.add(HRV(user_id=user_id, calendar_date=parsed_date,
                        weekly_avg=weekly, last_night_avg=nightly, status=status_str))
                session.commit()

            elif "_BODY_BATTERY" in json_path.name:
                items = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
                for item in items:
                    if not isinstance(item, dict): continue
                    cal_str = cal_date_str or item.get("date") or item.get("calendarDate") or datetime.utcnow().strftime("%Y-%m-%d")
                    parsed_date = datetime.strptime(cal_str, "%Y-%m-%d").date()
                    user_id = self._extract_user_id(session, item)
                    self._ensure_user_exists(session, user_id)
                    charged_val = item.get("charged")
                    drained_val = item.get("drained")
                    existing = session.query(BodyBattery).filter_by(user_id=user_id, calendar_date=parsed_date).first()
                    if existing:
                        if charged_val is not None: existing.charged = charged_val
                        if drained_val is not None: existing.drained = drained_val
                    else:
                        session.add(BodyBattery(user_id=user_id, calendar_date=parsed_date,
                            charged=charged_val, drained=drained_val))
                session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to process JSON summary {json_path}: {e}")
        finally:
            session.close()

    def process_activities_list(self, json_path: Path) -> None:
        """Parse activities_list.json and upsert into Activity table."""
        with open(json_path, "r", encoding="utf-8") as f:
            activities = json.load(f)

        if not isinstance(activities, list):
            return

        session = self.db_manager.get_session()
        try:
            for act in activities:
                act_id = act.get("activityId")
                if not act_id:
                    continue
                user_id = act.get("ownerId", 0)
                self._ensure_user_exists(session, user_id)

                start_ts_str = act.get("startTimeLocal") or act.get("startTimeGMT")
                parsed_ts = None
                if start_ts_str:
                    try:
                        parsed_ts = datetime.strptime(start_ts_str.split(".")[0].replace("T", " "), "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        parsed_ts = datetime.utcnow()

                activity_record = Activity(
                    activity_id=act_id,
                    user_id=user_id,
                    activity_name=act.get("activityName", "Workout"),
                    activity_type_key=(act.get("activityType") or {}).get("typeKey", "activity"),
                    start_ts=parsed_ts or datetime.utcnow(),
                    duration=act.get("duration"),
                    distance=act.get("distance"),
                    average_hr=act.get("averageHR"),
                    calories=act.get("calories")
                )
                session.merge(activity_record)
            session.commit()
            logger.info(f"Upserted {len(activities)} activities into SQLite DB.")
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to process activities list {json_path}: {e}")
        finally:
            session.close()

    def process_fit_file(self, fit_path: Path) -> None:
        """Parse binary FIT activity file using fitdecode and store time series records."""
        try:
            import fitdecode
            act_id_match = re.search(r"(\d+)", fit_path.stem)
            activity_id = int(act_id_match.group(1)) if act_id_match else None
            if not activity_id:
                return

            session = self.db_manager.get_session()
            records_added = 0
            try:
                with fitdecode.FitReader(str(fit_path)) as fit:
                    for frame in fit:
                        if frame.frame_type == fitdecode.FIT_FRAME_DATA and frame.name == "record":
                            ts = frame.get_value("timestamp")
                            if not ts:
                                continue
                            lat = frame.get_value("position_lat")
                            lon = frame.get_value("position_long")
                            # Convert semicircles to degrees if needed
                            if lat and abs(lat) > 180: lat = lat * (180 / (2**31))
                            if lon and abs(lon) > 180: lon = lon * (180 / (2**31))
                            
                            metric = ActivityTsMetric(
                                activity_id=activity_id,
                                timestamp=ts if isinstance(ts, datetime) else datetime.utcnow(),
                                latitude=lat,
                                longitude=lon,
                                elevation=frame.get_value("enhanced_altitude") or frame.get_value("altitude"),
                                heart_rate=frame.get_value("heart_rate"),
                                speed=frame.get_value("enhanced_speed") or frame.get_value("speed"),
                                cadence=frame.get_value("cadence"),
                                power=frame.get_value("power")
                            )
                            session.merge(metric)
                            records_added += 1
                session.commit()
                logger.info(f"Processed {records_added} time-series frames from FIT file {fit_path}")
            except Exception as fe:
                session.rollback()
                logger.warning(f"Error parsing frames in {fit_path}: {fe}")
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Failed to decode FIT file {fit_path}: {e}")

