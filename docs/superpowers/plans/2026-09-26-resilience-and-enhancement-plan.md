# GarminSynapse Resilience & Enhancement Implementation Plan

> **For agentic workers:** Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement comprehensive resilience, crash protection, Garmin API rate-limit throttling, cross-process locking, and observability features for `garminsynapse` based on [2026-09-26-resilience-and-enhancement-spec.md](file:///root/garminsynapse/docs/superpowers/specs/2026-09-26-resilience-and-enhancement-spec.md).

**Architecture:** 
1. Entrypoint & supervisor hardening (`run.sh`, `ecosystem.config.cjs`).
2. API gateway throttling & backoff engine (`core/throttler.py`, `core/api.py`, `etl/extractor.py`).
3. Cross-process file locking for auth (`auth/manager.py`) and SQLite WAL engine configuration (`db/session.py`).
4. Observability endpoints (`/healthz`, `/api/status`) and background alerting (`web/app.py`).

**Tech Stack:** Python 3.12, Virtualenv, FastAPI, SQLite (WAL), PM2, `fcntl`.

---

## Task Breakdown

### Task 1: Process Hardening & PM2 Crash Protection

**Files:**
- Create: `/root/garminsynapse/run.sh`
- Modify: `/root/garminsynapse/ecosystem.config.cjs`
- Test: `/root/garminsynapse/tests/test_runtime_config.py`

**Interfaces:**
- `run.sh`: Enforces `ulimit -c 0` and virtual environment execution (`.venv/bin/python`).
- `ecosystem.config.cjs`: PM2 supervisor with `exp_backoff_restart_delay: 2000`, `max_restarts: 15`, `min_uptime: '20s'`.

- [ ] **Step 1: Write unit test validating `ecosystem.config.cjs` syntax and presence of backoff keys**
- [ ] **Step 2: Create `/root/garminsynapse/run.sh` with executable permissions (`chmod +x`)**
- [ ] **Step 3: Update `ecosystem.config.cjs` to target `./run.sh` with `interpreter: 'none'`**
- [ ] **Step 4: Verify PM2 process configuration using `pm2 describe garminsynapse`**
- [ ] **Step 5: Commit changes**

---

### Task 2: API Throttling & Exponential Backoff Engine

**Files:**
- Create: `/root/garminsynapse/src/garminsynapse/core/throttler.py`
- Modify: `/root/garminsynapse/src/garminsynapse/core/api.py`
- Modify: `/root/garminsynapse/src/garminsynapse/etl/extractor.py`
- Test: `/root/garminsynapse/tests/test_throttler.py`

**Interfaces:**
- `Throttler.ensure_not_rate_limited()`: Raises or waits if in active cooldown.
- `Throttler.mark_rate_limited(cooldown_seconds)`: Sets rate limit cooldown timestamp.
- `with_auto_retry`: Decorator with exponential backoff and jitter on 429/5xx.
- `_adaptive_sleep()`: Random jittered delay (1.0s – 2.0s) between Garmin endpoint queries.

- [ ] **Step 1: Write unit tests for `Throttler` state management and cooldown expiry**
- [ ] **Step 2: Implement `src/garminsynapse/core/throttler.py`**
- [ ] **Step 3: Update `src/garminsynapse/core/api.py` with enhanced `with_auto_retry`**
- [ ] **Step 4: Update `src/garminsynapse/etl/extractor.py` to use `_adaptive_sleep()` between daily endpoints**
- [ ] **Step 5: Run tests using pytest to ensure retry and throttling logic behaves correctly**
- [ ] **Step 6: Commit changes**

---

### Task 3: Cross-Process Concurrency Safety (File Lock & SQLite WAL)

**Files:**
- Modify: `/root/garminsynapse/src/garminsynapse/auth/manager.py`
- Modify: `/root/garminsynapse/src/garminsynapse/db/session.py` (or SQLite connection factory)
- Test: `/root/garminsynapse/tests/test_concurrency.py`

**Interfaces:**
- `file_lock(token_lock_path)`: Context manager using `fcntl.flock` to serialize token writes across distinct OS processes.
- SQLite PRAGMA listener: Injects `journal_mode = WAL`, `busy_timeout = 5000`, `synchronous = NORMAL`.

- [ ] **Step 1: Write unit test validating file lock acquisition and release under concurrent access**
- [ ] **Step 2: Update `AuthManager` in `src/garminsynapse/auth/manager.py` to acquire file lock during login & token refresh**
- [ ] **Step 3: Configure SQLite PRAGMA listeners on the SQLAlchemy database engine**
- [ ] **Step 4: Run tests to verify token persistence and concurrent SQLite write/read safety**
- [ ] **Step 5: Commit changes**

---

### Task 4: Observability, Health Endpoints & Status API

**Files:**
- Modify: `/root/garminsynapse/src/garminsynapse/web/app.py`
- Test: `/root/garminsynapse/tests/test_health_endpoints.py`

**Interfaces:**
- `GET /healthz`: Fast 200 OK liveness check.
- `GET /api/status`: JSON diagnostic report containing database connectivity, token validity, rate-limit state, and last sync timestamp.

- [ ] **Step 1: Write integration tests for `/healthz` and `/api/status` using FastAPI `TestClient`**
- [ ] **Step 2: Implement `/healthz` endpoint in `src/garminsynapse/web/app.py`**
- [ ] **Step 3: Implement `/api/status` endpoint collecting engine, database, and auth telemetry**
- [ ] **Step 4: Add consecutive sync failure counter and logging alerts**
- [ ] **Step 5: Run tests to verify endpoint responses and schema accuracy**
- [ ] **Step 6: Commit changes**

---

### Task 5: End-to-End Verification & PM2 Reload

**Files:**
- Verify: Full test suite (`pytest`)
- PM2 reload: `pm2 reload garminsynapse`

- [ ] **Step 1: Execute full test suite `pytest tests/`**
- [ ] **Step 2: Reload PM2 process with updated config: `pm2 reload ecosystem.config.cjs`**
- [ ] **Step 3: Test live health endpoints: `curl -f http://127.0.0.1:8000/healthz` and `curl -f http://127.0.0.1:8000/api/status`**
- [ ] **Step 4: Inspect PM2 logs to ensure clean startup without warnings or errors**
- [ ] **Step 5: Run `graphify update .` to synchronize codebase knowledge graph**
