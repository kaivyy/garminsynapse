# ⚡ GarminSynapse

Unified Engine, Relational Database, Native MCP Server & Web Dashboard for Garmin Connect.

---

## 🌟 Overview

**GarminSynapse** is an all-in-one platform for extracting, storing, analyzing, and serving Garmin Connect health and training data to AI Agents (via **Model Context Protocol - MCP**) and human users (via a **Responsive Glassmorphism Web Dashboard** running on port **6060**).

### Key Features
* 🛡️ **Dual-Engine Authentication**: Fast 5-stage `curl_cffi` browser TLS impersonation with automatic Playwright Chromium fallback for Cloudflare Turnstile CAPTCHA.
* 🗄️ **Relational SQLite Storage**: 40+ normalized tables for Daily Health Stats, Sleep Stages, Heart Rate, Stress, Body Battery, HRV Baseline, Respiration, SpO2, Training Status, and Activities.
* 🤖 **Native MCP Server Protocol**: Exposes 10 powerful MCP tools (`garmin_status`, `garmin_login`, `garmin_sync`, `get_daily_summary`, `get_sleep_analysis`, `get_hrv_trends`, `list_activities`, `get_activity_details`, `download_fit_file`, `query_garmin_db`) via STDIO & SSE transports.
* 🌐 **Glassmorphism Web Dashboard**: Responsive SPA UI built with modern HTML5/CSS3/JavaScript featuring health gauges, interactive activity feeds, manual sync trigger, and authentic Garmin login modal on **port 6060**.
* ⚡ **180+ Garmin API Wrapper**: Full coverage of Garmin Connect endpoints including FIT binary weight encoding.

---

## ⚡ Satset Quick Start (Installation)

### 1. Clone & Automated Setup

```bash
git clone https://github.com/your-username/garminsynapse.git
cd garminsynapse
./install.sh
```

### 2. Run Web Dashboard & REST API (Port 6060)

```bash
python3 -m garminsynapse.cli start-server --host 0.0.0.0 --port 6060
```
Open your browser at `http://<IP-Tailscale-Server>:6060` or `http://localhost:6060`.

### 3. Run Native MCP Server (For AI Agents)

```bash
python3 -m garminsynapse.cli mcp
```

### 4. Sync Data via CLI

```bash
python3 -m garminsynapse.cli sync --days 14
```

---

## 🤖 MCP Integration Guide

### Claude Desktop Configuration
Add the following snippet to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "garminsynapse": {
      "command": "python3",
      "args": ["-m", "garminsynapse.cli", "mcp"],
      "env": {
        "PYTHONPATH": "${workspaceFolder}/src"
      }
    }
  }
}
```

### Cursor & AGY Setup
In your Editor Settings -> Model Context Protocol (MCP) -> Add New Command:
* **Name**: `garminsynapse`
* **Command**: `python3 -m garminsynapse.cli mcp`

---

## 🛠️ MCP Tools Reference

| Tool Name | Parameters | Description |
|---|---|---|
| `garmin_status` | None | Check auth, database, and MCP status |
| `garmin_login` | `email`, `password` | Authenticate with Garmin Connect |
| `garmin_sync` | `days` (default 7) | Extract recent Garmin metrics to SQLite |
| `get_daily_summary` | `date_str` (`YYYY-MM-DD`) | Get daily steps, RHR, stress, body battery |
| `get_sleep_analysis` | `date_str` (`YYYY-MM-DD`) | Get sleep stages, sleep score, SpO2 |
| `get_hrv_trends` | `date_str` | Get HRV status and weekly baseline |
| `list_activities` | `limit` (default 20) | List recent workouts (distance, duration, HR, calories) |
| `get_activity_details` | `activity_id` | Get detailed time-series metrics & map polyline |
| `download_fit_file` | `activity_id` | Download raw binary `.FIT` file to local storage |
| `query_garmin_db` | `sql_query` | Execute safe SELECT query on SQLite DB (40+ tables) |

---

## 📡 REST API Endpoints (Port 6060)

* `GET /api/v1/status` - System health and auth state.
* `POST /api/v1/auth/login` - Authenticate Garmin Connect account.
* `POST /api/v1/auth/logout` - Clear stored session tokens.
* `GET /api/v1/summary` - Get daily health gauges.
* `GET /api/v1/activities` - List recent activities.
* `POST /api/v1/sync` - Trigger background sync.

---

## 🧹 Database Maintenance

To keep disk usage bounded over time:

```bash
# Downsample raw 1-second time-series metrics older than 30 days
python3 -m garminsynapse.cli downsample --days-keep-raw 30

# Prune activities older than 1 year
python3 -m garminsynapse.cli prune --days-keep 365
```

---

## 📄 License
MIT License.
