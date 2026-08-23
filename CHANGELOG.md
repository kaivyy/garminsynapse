# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.2.3] - 2026-08-23

### 🚀 Features & Enhancements
- **Garmin Nap & Daytime Sleep Tracking**:
  - Integrated `napTimeSeconds` and `dailyNapDTOS` parsing in `/api/v1/live` and MCP tools.
  - Added smart rendering in the Web Dashboard Sleep Score card to display daytime naps (e.g. `1h 19m (Nap)`) when overnight sleep is not yet recorded.

## [v0.2.2] - 2026-08-23

### 🚀 Features & Enhancements
- **Direct Daily Steps Integration**:
  - Connected `get_daily_steps()` to `/api/v1/live` and MCP tool `get_live_metrics`, allowing step data to be pulled in real-time even for new Garmin accounts without a configured public display name.
  - Added seamless fallback in `GarminAPI.get_daily_stats()` to retrieve actual step counts and step goals directly from user summary endpoints.

## [v0.2.1] - 2026-08-23

### 🚀 Features & Enhancements
- **Live Real-Time Biometric Engine**:
  - Added `/api/v1/live` REST API endpoint with point-in-time extraction for today's Body Battery %, charged/drained energy, Stress score (Rest/Low/Medium/High), and real-time steps.
  - Added `get_live_metrics` MCP tool enabling AI agents to read point-in-time wellness status.
  - Integrated live sensor values seamlessly into Web Dashboard cards.
- **Garmin Hardware & Device Tracking**:
  - Added native integration for Garmin devices (`get_devices()` and `get_primary_training_device()`).
  - Added `/api/v1/devices` REST endpoint and `get_garmin_devices` MCP tool to expose registered hardware, active watch model, serial number, unit ID, and firmware version.
  - Added **Connected Garmin Device** glassmorphism card to the Web Dashboard UI with real-time pairing status indicator.
- **Smart In-Memory Caching & Account Security**:
  - Implemented in-memory TTL caching on device queries (6 hours) and live metrics (60s) to eliminate redundant Garmin API calls during navigation/refresh.
  - Added 5-minute cooldown timer (`_SYNC_COOLDOWN_SECONDS`) on `POST /sync` to prevent API spamming and protect accounts from HTTP 429 rate limiting.
  - Added polite request throttling (0.3s backoff interval) inside `GarminExtractor` bulk history loops.
- **Full OAuth Client State Persistence**:
  - Upgraded `CffiStrategy` to serialize and store `garmin.client.dumps()` directly in `tokens.json`.
  - Upgraded `GarminAPI` to seamlessly restore live authenticated sessions via `garmin.client.loads(client_state)` without re-triggering login flows.
  - Added PM2 ecosystem config (`ecosystem.config.js`) for background service management.
- **Native MCP (Model Context Protocol) Upgrades**:
  - Added `get_garmin_devices` MCP tool to retrieve connected Garmin watch model, serial number, unit ID, and firmware.
  - Added `get_live_metrics` MCP tool to provide AI agents with real-time biometric readings (Body Battery, Stress level & status, Steps, HR).
  - Exposes 11 comprehensive MCP tools for AI assistants (Claude, Cursor, Antigravity/AGY).

### 🐛 Bug Fixes
- Fixed `NameError: name 'GarminAPI' is not defined` missing import inside `web/routes.py`.
- Fixed session initialization bug where `_garmin_instance` failed to restore on subsequent API invocations without raw password inputs.

## [v0.1.0] - 2026-08-08

### 🚀 Features & Architecture
- **Unified Garmin Connect Engine**: First release of Garmin Synapse, built as a modern, high-performance wrapper around the Garmin Connect API.
- **Dual Authentication Strategy**:
  - Implemented robust `curl_cffi` 5-stage login engine impersonating Chrome TLS fingerprints to bypass basic Cloudflare checks.
  - Implemented automatic **Playwright Headless Browser fallback** for advanced CAPTCHA / Turnstile bypass when API-based auth receives HTTP 429.
  - Atomic token caching and session persistence (`~/.garminsynapse/tokens.json`) with secure `0600` file permissions.
- **SQLite Database Architecture**:
  - Designed a 40+ table normalized schema using `SQLAlchemy` covering comprehensive health metrics: `User`, `Activity`, `Sleep`, `HRV`, `Stress`, `BodyBattery`, `ActivityTsMetric`, etc.
  - Implemented `DatabaseManager` with automatic schema initialization and SQLite `PRAGMA foreign_keys=ON` enforcement.
  - Provided `downsample()` utility to compress raw 1-second metrics to reduce DB size.
  - Provided `prune()` utility to garbage collect activities older than configurable retention limits.
- **Robust ETL Pipeline (Extract, Transform, Load)**:
  - Developed `GarminExtractor` to pull bulk historical JSON data and binary `.FIT` / `.TCX` files.
  - Developed `GarminProcessor` featuring `fitdecode` logic to parse binary data directly into local DB time-series rows.
  - Upsert patterns (`session.merge`) for idempotency, ensuring zero duplicates during sync.
- **Native MCP (Model Context Protocol) Server**:
  - Exposes 8+ powerful MCP tools using `mcp.server.fastmcp`.
  - Tools include: `garmin_status`, `garmin_login`, `garmin_sync`, `get_daily_summary`, `get_sleep_analysis`, `get_hrv_trends`, `list_activities`, `get_activity_details`, `download_fit_file`.
  - Added safe `query_garmin_db` tool for autonomous agents to run read-only `SELECT` analytical queries.
- **FastAPI Web Dashboard**:
  - `uvicorn` based high-performance REST API serving metrics at `/api/v1/...`.
  - Single Page Application (SPA) static frontend built with Vanilla JS, HTML, and CSS.
  - **Modern Sporty UI**: Responsive dark/light mode, glassmorphism, animated pulse indicators, Garmin branding, and CSS Grid-based health cards.

### 🐛 Bug Fixes (Major 23+ Bug Audit Sweep)
- **Architecture**: Created missing `__init__.py` files across all 7 internal modules (`auth`, `core`, `db`, `etl`, `mcp`, `web`, `tests`) fixing `ModuleNotFoundError` during imports.
- **Database**:
  - Fixed `IntegrityError` by allowing `Activity.end_ts` to be nullable.
  - Added `elapsed_duration` and `elevation_gain` to Activity schema.
  - Added `UniqueConstraint` on daily records (`Sleep`, `HRV`, `Stress`, `BodyBattery`) to prevent duplicate row insertions on every ETL run.
  - Enforced `PRAGMA foreign_keys=ON` per-connection via SQLAlchemy event listener.
  - Fixed `prune()` function crashing on FK constraint violations by explicitly deleting child time-series rows first.
- **ETL Processor**:
  - Fixed multiple chained `.get()` `NoneType` crashes (`AttributeError`) when Garmin API returned `null` for `sleepScores` or `activityType`.
  - Expanded JSON processing to actually parse `STRESS`, `HRV`, and `HEART_RATE` (Body Battery) files instead of ignoring them.
  - Fixed `datetime.strptime` bug that crashed when parsing ISO 8601 timestamps containing the letter "T".
- **Authentication**:
  - Resolved `asyncio.run()` crash on Playwright fallback when executing within an already running event loop (e.g., inside FastAPI worker) by routing through `ThreadPoolExecutor`.
  - Improved security by setting `0600` permissions on stored `tokens.json`.
- **Web & UI**:
  - Fixed critical JS timezone bug (`toISOString()` forcing UTC), resolving issues where UTC+ timezones rendered "Today" as yesterday.
  - Fixed attribute mismatch bugs in `/summary` route where `average_stress_level` and `charged_value` resulted in silent null returns.
- **CLI & MCP**:
  - Fixed MCP STDIO handshake corruption by piping `click.echo` startup logs to `stderr` instead of `stdout`.
  - Fixed Port 8000 vs 6060 mismatches across configs.
  - Appended `GarminProcessor().process_ingest_directory()` inside sync commands so extracted data is actually inserted into the database.
- **Core Encoder**:
  - Fixed binary FIT encoder `data_size` header bug ensuring `.FIT` files generated for Weight Scales are valid.

### 🧪 Testing & Packaging
- Fixed 5 broken test files in `pytest` suite ensuring 100% pass rate.
- Moved `pyproject.toml` configurations into proper modern Python packaging format, dropping `requirements.txt` in favor of declarative `[project.dependencies]`.
- Updated `install.sh` to correctly trigger `pip install -e .` with full dependencies.
