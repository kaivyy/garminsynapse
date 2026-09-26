import time
from pathlib import Path
from sqlalchemy import text
from garminsynapse.auth.tokens import TokenManager
from garminsynapse.db.manager import DatabaseManager


def test_token_manager_file_lock(tmp_path):
    token_file = tmp_path / "tokens.json"
    tm = TokenManager(token_file=token_file)
    
    assert hasattr(tm, "lock"), "TokenManager must provide a lock() context manager"
    
    # Test lock acquisition and release
    with tm.lock():
        lock_file = token_file.parent / "tokens.lock"
        assert lock_file.exists()


def test_database_pragmas_wal_and_busy_timeout(tmp_path):
    db_path = tmp_path / "test.db"
    db_mgr = DatabaseManager(db_path=db_path)
    
    with db_mgr.engine.connect() as conn:
        journal_mode = conn.execute(text("PRAGMA journal_mode;")).scalar()
        busy_timeout = conn.execute(text("PRAGMA busy_timeout;")).scalar()
        
        assert str(journal_mode).lower() == "wal", f"Expected WAL mode, got {journal_mode}"
        assert busy_timeout >= 5000, f"Expected busy_timeout >= 5000, got {busy_timeout}"
