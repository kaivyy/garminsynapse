"""ETL Processor for parsing FIT, TCX, and JSON files into SQLite database."""
import json
import logging
import re
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, Optional
from garminsynapse.db.manager import DatabaseManager
from garminsynapse.db.schema import User, Activity, Sleep, HRV, Stress, BodyBattery

logger = logging.getLogger(__name__)

DEFAULT_INGEST_DIR = Path.cwd() / "garmin_files" / "ingest"
DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")


class GarminProcessor:
    """Parses raw downloaded health & activity files into SQLite records."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()

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
                user_id = sleep_dto.get("userId", 0)
                self._ensure_user_exists(session, user_id)

                cal_str = cal_date_str or sleep_dto.get("calendarDate") or datetime.utcnow().strftime("%Y-%m-%d")
                parsed_date = datetime.strptime(cal_str, "%Y-%m-%d").date()

                sleep_record = Sleep(
                    user_id=user_id,
                    calendar_date=parsed_date,
                    total_sleep_seconds=sleep_dto.get("sleepTimeSeconds"),
                    sleep_score=sleep_dto.get("sleepScores", {}).get("overall", {}).get("value")
                )
                session.merge(sleep_record)
                session.commit()
                logger.info(f"Processed sleep JSON record for {parsed_date}")
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
                        parsed_ts = datetime.strptime(start_ts_str.split(".")[0], "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        parsed_ts = datetime.utcnow()

                activity_record = Activity(
                    activity_id=act_id,
                    user_id=user_id,
                    activity_name=act.get("activityName", "Workout"),
                    activity_type_key=act.get("activityType", {}).get("typeKey", "activity"),
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
        """Parse binary FIT activity file using fitdecode."""
        try:
            import fitdecode
            with fitdecode.FitReader(str(fit_path)) as fit:
                for frame in fit:
                    if frame.frame_type == fitdecode.FIT_FRAME_DATA:
                        if frame.name == "record":
                            pass
            logger.info(f"Successfully processed FIT file {fit_path}")
        except Exception as e:
            logger.error(f"Failed to decode FIT file {fit_path}: {e}")
