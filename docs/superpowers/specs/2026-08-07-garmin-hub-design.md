# Garmin Synapse - Unified Architecture Design Document

**Date**: 2026-08-07  
**Project**: `garminsynapse`  
**Status**: Approved  

---

## 1. Executive Summary

`garminsynapse` is a unified, high-performance Garmin Connect platform that combines the best architectural strengths of four existing Garmin repositories (`garth`, `python-garminconnect`, `garmin-health-data`, and `garmin-connect-mcp`).

It provides:
1. **Dual-Engine Authentication**: A fast, programmatic `curl_cffi` 5-strategy TLS-impersonation login with an automatic `playwright` headless browser fallback for Cloudflare Turnstile CAPTCHA and MFA challenges.
2. **Full API Wrapper**: 140+ Garmin Connect API endpoints covering health, workouts, activities, weight FIT uploads, challenges, and golf.
3. **Resilient ETL & SQLite Database Engine**: Automated file archiving (FIT, TCX, JSON), multi-stage pipeline (`ingest`, `process`, `storage`, `quarantine`), full 40+ table SQLite relational schema with cascade foreign keys, and bounded storage downsampling/pruning.
4. **Native MCP Server**: Model Context Protocol (MCP) server supporting STDIO and SSE transports, exposing health metrics, activities, FIT files, and safe read-only SQL querying directly to AI agents.
5. **Modern Premium Web Dashboard**: A single-process FastAPI web server serving a responsive Single-Page Application (SPA) with dark mode glassmorphism UI, real-time health gauges, activity maps, and MCP status indicators.

---

## 2. System Architecture

```mermaid
flowchart TD
    subgraph Clients & Consumers
        LLM["AI Agents (Claude Code, Cursor, AGY)"]
        USER["User Web Browser"]
    end

    subgraph Interface Layer (FastAPI Web + MCP)
        WEB_UI["Dashboard SPA (HTML5/CSS3/Vanilla JS)"]
        REST["REST API (/api/v1/*)"]
        MCP_SRV["MCP Server (STDIO & SSE Transport)"]
    end

    subgraph Core Engine Layer
        AUTH["Dual-Engine Auth Manager"]
        API["Garmin API Wrapper (140+ Endpoints)"]
        ETL["ETL & Storage Pipeline"]
    end

    subgraph Auth Providers
        CFFI["curl_cffi (5-Strategy Browser TLS Impersonation)"]
        PW["Playwright Chromium (CAPTCHA / Manual MFA)"]
    end

    subgraph Storage Layer
        DB["SQLite Database (garmin_data.db)"]
        FILES["Raw File Archive (FIT / TCX / JSON)"]
    end

    LLM <--> MCP_SRV
    USER <--> WEB_UI
    WEB_UI <--> REST
    REST <--> API
    REST <--> DB
    MCP_SRV <--> API
    MCP_SRV <--> DB

    API --> AUTH
    AUTH --> CFFI
    AUTH -- "On 429 / CAPTCHA" --> PW
    
    ETL --> API
    ETL --> DB
    ETL --> FILES
```

---

## 3. Detailed Component Specifications

### 3.1 Dual-Engine Authentication Manager (`garminsynapse.auth`)

* **Primary Engine (`curl_cffi`)**:
  * Implements 5 fallback login strategies sequentially: `portal+cffi`, `portal+requests`, `mobile+cffi`, `mobile+requests`, `widget+cffi`.
  * Emulates browser TLS fingerprints (`chrome131`, `safari_ios`).
  * Handles OAuth1 ticket acquisition and DI OAuth2 token exchange (`diauth.garmin.com`) with rotating client IDs.
  * Proactive 15-minute token refresh prior to expiration and auto-retry on HTTP 401.

* **Fallback Engine (`playwright`)**:
  * Activated automatically when `curl_cffi` encounters HTTP 429 (Cloudflare WAF block) or interactive Turnstile CAPTCHA.
  * Launches a Playwright Chromium context, guides interactive login or cookie capture, and extracts session cookies and CSRF tokens to `~/.garminsynapse/tokens.json`.

---

### 3.2 Database Engine & ETL Pipeline (`garminsynapse.db` & `garminsynapse.etl`)

* **SQLite Schema (40+ Tables)**:
  * User & Profile: `user`, `user_profile`.
  * Activities & Metrics: `activity`, `activity_ts_metric`, `activity_split_metric`, `activity_lap_metric`, `running_metrics`, `cycling_metrics`.
  * Wellness: `sleep`, `sleep_level`, `hrv`, `stress`, `body_battery`, `respiration`, `spo2`, `steps`, `floors`.
  * Performance: `training_status`, `training_readiness`, `running_tolerance`, `personal_record`, `race_predictions`.
  * Weight & Cycle: `body_composition`, `weigh_in`, `menstrual_cycle_day`.

* **Storage Bounding**:
  * `downsample`: Aggregates 1-second activity metrics into time-bucketed averages, reducing DB growth by 90%+.
  * `prune`: Deletes raw time-series rows older than retention limits while preserving activity summaries and FIT files.
  * Pipeline lifecycle: `ingest` ➔ `process` ➔ `storage` ➔ `quarantine`.

---

### 3.3 Full API Wrapper (`garminsynapse.core.api`)

Wraps 140+ Garmin Connect endpoints into 13 organized categories:
1. User & Profile
2. Daily Health & Wellness
3. Advanced Health Metrics
4. Historical Data & Trends
5. Activities & Workouts (including FIT/TCX typed uploads)
6. Body Composition & Weight (with binary FIT weight scale encoder)
7. Goals & Badges
8. Device & Technical
9. Gear & Equipment
10. Hydration & Wellness
11. System & Export
12. Training Plans
13. Golf

All calls are guarded by `@with_auto_retry` exponential backoff and automatic token refresh.

---

### 3.4 MCP Server Protocol (`garminsynapse.mcp`)

Exposes MCP tools over STDIO and SSE transports using Python `mcp` SDK:

* `garmin_status`: Returns current auth, database, and sync status.
* `garmin_login`: Executes login or triggers Playwright fallback.
* `garmin_sync`: Triggers ETL data extraction for a given date range.
* `get_daily_summary`: Retrieves step, calorie, HR, stress, and sleep summaries.
* `get_sleep_analysis`: Detailed sleep stages, score, and SpO2 breakdown.
* `get_hrv_trends`: Heart rate variability status and weekly baseline.
* `list_activities`: Filterable list of logged workouts.
* `get_activity_details`: Detailed time-series sensor data for a specific workout.
* `download_fit_file`: Downloads and returns raw `.FIT` activity files.
* `query_garmin_db`: Allows safe, read-only SQL `SELECT` execution on `garmin_data.db`.

---

### 3.5 Web Dashboard UI (`garminsynapse.web`)

* **Tech Stack**: FastAPI backend serving a Vite/Vanilla JS Single-Page Application (SPA).
* **Design Tokens**: Dark mode, HSL tailored vibrant accents, glassmorphism cards, Inter/Outfit typography, micro-interactions.
* **Views**:
  1. **Overview**: Real-time health gauges (Steps, HR, Sleep score, Body battery, Stress).
  2. **Activities Feed**: Workout list with HR zone breakdowns, lap splits, and GPS polyline indicators.
  3. **Health Analytics**: Interactive charts for HRV trends, sleep stages, and VO2 max.
  4. **System & MCP**: Auth status, manual sync triggers, Playwright toggle, and active MCP sessions.

---

## 4. Project Directory Layout

```
/root/garminsynapse/
├── pyproject.toml
├── README.md
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-08-07-garminsynapse-design.md
├── src/
│   └── garminsynapse/
│       ├── __init__.py
│       ├── auth/
│       │   ├── __init__.py
│       │   ├── cffi_strategy.py
│       │   ├── playwright_strategy.py
│       │   └── tokens.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── api.py
│       │   └── fit_encoder.py
│       ├── db/
│       │   ├── __init__.py
│       │   ├── schema.py
│       │   └── manager.py
│       ├── etl/
│       │   ├── __init__.py
│       │   ├── extractor.py
│       │   └── processor.py
│       ├── mcp/
│       │   ├── __init__.py
│       │   ├── server.py
│       │   └── tools.py
│       └── web/
│           ├── __init__.py
│           ├── app.py
│           ├── routes.py
│           └── static/
│               ├── index.html
│               ├── css/
│               │   └── style.css
│               └── js/
│                   └── app.js
```

---

## 5. Next Steps

1. Review and confirm this written design document.
2. Invoke `writing-plans` skill to generate a step-by-step implementation plan.
