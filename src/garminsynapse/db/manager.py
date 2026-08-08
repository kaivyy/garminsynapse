"""Database Manager handling SQLite connections, DDL creation, downsampling, and pruning."""
import logging
from pathlib import Path
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import event as sa_event
from garminsynapse.db.schema import Base

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path.cwd() / "garmin_data.db"


class DatabaseManager:
    """Manages SQLite database initialization, sessions, and maintenance."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={"check_same_thread": False}
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        @sa_event.listens_for(self.engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.close()

        self.init_db()

    def init_db(self) -> None:
        """Create all tables and enforce foreign keys."""
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON;"))
            conn.commit()
        Base.metadata.create_all(bind=self.engine)
        logger.info(f"Initialized database schema at {self.db_path}")

    def get_session(self) -> Session:
        """Provide a new SQLAlchemy session."""
        return self.SessionLocal()

    def downsample(self, days_keep_raw: int = 30) -> int:
        """Delete raw 1-second activity metrics older than threshold."""
        query = text("""
            DELETE FROM activity_ts_metric
            WHERE timestamp < datetime('now', '-' || :days || ' days')
        """)
        with self.engine.connect() as conn:
            res = conn.execute(query, {"days": days_keep_raw})
            conn.commit()
            logger.info(f"Downsampled/deleted {res.rowcount} raw ts metrics older than {days_keep_raw} days.")
            return res.rowcount

    def prune(self, days_keep: int = 365) -> int:
        """Prune old database records to bound disk usage."""
        child_query = text("""
            DELETE FROM activity_ts_metric
            WHERE activity_id IN (
                SELECT activity_id FROM activity
                WHERE start_ts < datetime('now', '-' || :days || ' days')
            )
        """)
        parent_query = text("""
            DELETE FROM activity
            WHERE start_ts < datetime('now', '-' || :days || ' days')
        """)
        with self.engine.connect() as conn:
            conn.execute(child_query, {"days": days_keep})
            res = conn.execute(parent_query, {"days": days_keep})
            conn.commit()
            logger.info(f"Pruned {res.rowcount} activities older than {days_keep} days.")
            return res.rowcount
