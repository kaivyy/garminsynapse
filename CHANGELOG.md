# 📋 Changelog

All notable changes to **GarminSynapse** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [v0.1.0] - 2026-08-08

### 🌟 Initial Release Overview
**GarminSynapse v0.1.0** is the inaugural release of the unified health engine, relational database, native FastMCP server, and responsive web dashboard for Garmin Connect.

---

### 🚀 Added

#### 🛡️ Dual-Engine Authentication Core (`garminsynapse.auth`)
* **Primary Engine (`curl_cffi`)**: 5-stage browser TLS handshake impersonation (`portal+cffi`, `portal+requests`, `mobile+cffi`, `mobile+requests`, `widget+cffi`) to bypass Cloudflare bot protection without launching a browser GUI.
* **Fallback Engine (`playwright`)**: Automated headless Chromium browser fallback for Cloudflare Turnstile CAPTCHA and MFA challenge resolution.
* **Persistent Token Manager**: Secure, local JSON token storage (`~/.garminsynapse/tokens.json`) with auto-login capabilities without storing plaintext passwords.

#### 🗄️ Relational Database & ETL Pipeline (`garminsynapse.db` & `garminsynapse.etl`)
* **SQLAlchemy Schema**: 40+ normalized relational tables for Daily Health Stats, Sleep Stages (Deep/Light/REM), Heart Rate, Stress, Body Battery, HRV Baseline, Respiration Rate, SpO2, Training Status, and Activities.
* **Automated GarminExtractor**: Bulk-fetches daily wellness data and activities across customizable date ranges into `garmin_files/ingest`.
* **GarminProcessor Engine**: Parses raw JSON and binary `.FIT` activity files using `fitdecode` and `defusedxml` into SQLite (`garmin_data.db`).
* **Database Maintenance**: Integrated `downsample` (compress 1-second time-series metrics) and `prune` (purge old historical records) routines.

#### 🤖 Native FastMCP Server Protocol (`garminsynapse.mcp`)
Exposes 10 native tools for AI Clients (Claude Desktop, Cursor, AGY, Claude Code):
1. `garmin_status`: System, database, and auth health status.
2. `garmin_login`: Remote Garmin Connect authentication.
3. `garmin_sync`: Background data extraction trigger.
4. `get_daily_summary`: Daily steps, RHR, stress, and body battery.
5. `get_sleep_analysis`: Sleep stages, sleep score, and oxygen saturation.
6. `get_hrv_trends`: Heart Rate Variability status and weekly baseline.
7. `list_activities`: Query logged workouts with distance, duration, HR, and calories.
8. `get_activity_details`: Per-second workout metrics and polyline map data.
9. `download_fit_file`: Downloads raw binary `.FIT` activity files.
10. `query_garmin_db`: Safe `SELECT` SQL query interface on the local SQLite DB.

#### 🌐 Glassmorphism Web Dashboard & REST API (`garminsynapse.web`)
* **Responsive SPA UI**: Built with modern HTML5/CSS3/JavaScript featuring dark mode glassmorphism aesthetics, responsive HSL accents, and smooth micro-animations.
* **8 Health Overview Cards**: Real-time display for Daily Steps, Resting Heart Rate, Sleep Score, Body Battery, HRV Baseline, Stress Level, Respiration Rate, and SpO2.
* **Custom Date Range Filter Bar**: Interactive date pickers (`Start Date` / `End Date`) and quick preset buttons (`Today`, `Last 7 Days`, `Last 30 Days`, `All Time`).
* **Interactive Workout Detail Modal**: Clicking any workout row opens a modal with workout splits, max HR, elevation gain, and duration.
* **Garmin Login Modal**: Built-in login screen for initial credential entry and token generation.
* **FastAPI REST Endpoints**: High-performance JSON endpoints on **port 6060** (`/api/v1/status`, `/api/v1/summary`, `/api/v1/activities`, `/api/v1/activity/{id}`, `/api/v1/auth/login`, `/api/v1/sync`).

#### 📦 CLI & Installation Automation
* **Click CLI (`garminsynapse.cli`)**: Subcommands `start-server`, `sync`, `mcp`, `downsample`, and `prune`.
* **Automated Installer (`install.sh`)**: 1-click setup script that installs dependencies, Playwright Chromium binaries, and creates required folder structures.
