# Design Specification: Activity GPX Export Feature

**Date**: 2026-10-25  
**Author**: Antigravity  
**Status**: Approved (Brainstorming Complete)

---

## 1. Goal & Overview

Provide a seamless, reliable way to download and export GPS workout activities (Running, Trail Running, Cycling, Walking, Hiking, etc.) into standard `.gpx` files. The feature is accessible across three user touchpoints:
1. **Web Dashboard**: Direct in-browser download via an "Export GPX" button in the Workout Details Modal.
2. **CLI**: Subcommand `garminsynapse export <activity_id> [--output ./] [--format gpx]` for terminal and automated workflows.
3. **MCP Server**: Native tool `export_activity_gpx(activity_id, output_dir)` for AI agent integration.

---

## 2. Architecture & Components

```
+-------------------------------------------------------------+
|                      User Interfaces                        |
|  [ Web Dashboard Modal ]   [ CLI Command ]   [ MCP Tool ]   |
+--------------+--------------------+----------------+--------+
               |                    |                |
               v                    v                v
      FastAPI Web Route       CLI Handler      MCP Tool Func
   GET /api/v1/.../export/gpx       |                |
               |                    |                |
               +--------------------+----------------+
                                    |
                                    v
                     +----------------------------+
                     |  Export & Cache Manager    |
                     |  (garmin_files/exports/)   |
                     +--------------+-------------+
                                    |
                        Cache miss / Stale?
                                    |
                                    v
                     +----------------------------+
                     |   GarminAPI (Core Client)  |
                     |   download_activity_gpx()  |
                     +--------------+-------------+
                                    |
                                    v
                     Garmin Connect Cloud Endpoint
               /download-service/export/gpx/activity/{id}
```

---

## 3. Detailed Component Specifications

### 3.1. Core API (`GarminAPI` in `src/garminsynapse/core/api.py`)
* **Method signature**: `download_activity_gpx(activity_id: int) -> bytes`
* **Implementation**:
  * Utilizes `@with_auto_retry`.
  * If `self._garmin_instance` is initialized, calls:
    `self._garmin_instance.download_activity(str(activity_id), dl_fmt=self._garmin_instance.ActivityDownloadFormat.GPX)`
  * Fallback to direct HTTP request on `f"{self.base_url}/download-service/export/gpx/activity/{activity_id}"`.
  * Validates that returned payload starts with XML/GPX headers (`<?xml` or `<gpx`). Returns empty bytes `b""` if no valid GPX data or if the activity has no GPS tracks.

### 3.2. Cache Layer (`garmin_files/exports/`)
* **Directory**: `garmin_files/exports/` (auto-created if missing).
* **Naming Scheme**: `{activity_id}.gpx`.
* **Caching Strategy**:
  1. Check if `garmin_files/exports/{activity_id}.gpx` exists and is non-empty (> 100 bytes).
  2. If present, read and return cached bytes immediately without API request.
  3. If missing, call `GarminAPI.download_activity_gpx()`. Upon receiving valid GPX bytes with `<trk>` or `<trkpt>`, atomically write to `garmin_files/exports/{activity_id}.gpx`.

### 3.3. Web Endpoint (`src/garminsynapse/web/routes.py`)
* **Route**: `GET /api/v1/activities/{activity_id}/export/gpx`
* **Query Parameters**: None (clean REST endpoint).
* **Authentication**: Enforces `DualAuthManager.get_active_tokens(auto_refresh=True)`. Returns 401 if unauthenticated.
* **Responses**:
  * **200 OK**: Content-Type `application/gpx+xml`. Header `Content-Disposition: attachment; filename="{clean_activity_name}_{activity_id}.gpx"`.
  * **422 Unprocessable Entity**: JSON `{"error": "no_gps_data", "message": "Activity does not contain GPS track data (e.g. indoor/strength workout)."}` when GPX has no trackpoints or Garmin returns empty data.
  * **404 Not Found**: If activity does not exist in local database or remote API.

### 3.4. Web UI (`src/garminsynapse/web/static/`)
* **Location**: Workout Details Modal (`#activity-modal`).
* **UI Elements**:
  * Action button next to Close button in `.modal-top-bar`:
    ```html
    <button id="modal-export-gpx-btn" class="btn-action-sporty" title="Export activity to GPX">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
        </svg>
        <span>Export GPX</span>
    </button>
    ```
* **Styles**:
  * Sporty accent, high-contrast border and text adhering to antislop rules.
  * Clear focus states and hover effects.
* **JavaScript Interaction (`app.js`)**:
  * In `openActivityModal(act)`:
    * If activity type is known indoor (e.g., `strength_training`, `yoga`, `pilates`), keep button available or show a subtle label, but let server handle GPS validation.
    * On click: triggers fetch with `blob()` download. If response is 422, displays a non-intrusive toast alert ("No GPS route data recorded for this workout"). If 200, triggers browser file save dialog.

### 3.5. CLI Command (`src/garminsynapse/cli.py`)
* **Command**:
  ```bash
  garminsynapse export <activity_id> [--output ./] [--format gpx]
  ```
* **Options**:
  * `<activity_id>`: Required integer argument.
  * `--output, -o`: Directory or target file path to save GPX (default: current working directory or `garmin_files/exports/`).
  * `--format, -f`: Export format, default `gpx` (extensible to `tcx` / `fit`).
* **Behavior**:
  * Reads from cache or calls `GarminAPI`.
  * Prints clear console messages with file size and destination.
  * Exits with code 0 on success, code 1 on non-GPS / API error.

### 3.6. MCP Server Tool (`src/garminsynapse/mcp/tools.py`)
* **Tool Name**: `export_activity_gpx`
* **Parameters**:
  * `activity_id`: `int` (Required)
  * `output_dir`: `Optional[str]` (Optional destination folder; defaults to `garmin_files/exports/`)
* **Output Structure**:
  ```json
  {
    "status": "success",
    "activity_id": 24548238787,
    "activity_name": "Cilacap Running",
    "file_path": "/root/garminsynapse/garmin_files/exports/24548238787.gpx",
    "file_size_bytes": 145320,
    "cached": true,
    "has_gps_data": true
  }
  ```

---

## 4. Error Handling & Edge Cases

| Scenario | Behavior |
|---|---|
| Indoor workout (Treadmill, Gym, Yoga) without GPS | Returns 422 with message "Activity does not contain GPS track data." Web shows warning toast; CLI exits gracefully. |
| Garmin session expired | `DualAuthManager.get_active_tokens(auto_refresh=True)` triggers auto-refresh. Returns 401 if refresh fails. |
| Network timeout / Garmin rate limit | `Throttler` and `@with_auto_retry` handle backoff. If exhausted, returns 503 Service Unavailable. |
| Malformed or empty GPX returned | Validator ensures XML contains `<gpx>` and at least one `<trkpt>` before writing to cache. |

---

## 5. Verification & Testing Plan

1. **Unit Tests**:
   * `test_download_activity_gpx`: Verify `GarminAPI.download_activity_gpx` returns valid bytes and handles errors.
   * `test_export_cache`: Verify local file caching prevents redundant API calls.
   * `test_web_export_gpx_route`: Test 200 attachment response and 422 for non-GPS activity.
   * `test_cli_export`: Test CLI command output and exit codes.
   * `test_mcp_export_tool`: Test MCP tool response schema and file creation.
2. **End-to-End Verification**:
   * Run real export for a running activity (e.g., Cilacap Running ID `24548238787`) and verify GPX content validity.
   * Test web dashboard UI download in browser.
