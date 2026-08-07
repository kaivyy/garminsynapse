"""Unit tests for DatabaseManager and schema models."""
import pytest
from pathlib import Path
from garminsynapse.db.manager import DatabaseManager
from garminsynapse.db.schema import User, Activity


def test_database_init(tmp_path: Path):
    db_file = tmp_path / "test_garmin.db"
    db = DatabaseManager(db_path=db_file)
    assert db_file.exists()

    session = db.get_session()
    user = User(user_id=12345, full_name="Test Runner")
    session.add(user)
    session.commit()

    saved_user = session.query(User).filter_by(user_id=12345).first()
    assert saved_user is not None
    assert saved_user.full_name == "Test Runner"
    session.close()


def test_downsample_and_prune(tmp_path: Path):
    db_file = tmp_path / "test_garmin.db"
    db = DatabaseManager(db_path=db_file)
    downsampled = db.downsample(days_keep_raw=30)
    pruned = db.prune(days_keep=365)
    assert downsampled >= 0
    assert pruned >= 0
