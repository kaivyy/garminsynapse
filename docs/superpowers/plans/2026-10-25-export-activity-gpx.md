# Activity GPX Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement activity GPX export and download across Core API, Local File Cache, FastAPI Web Route, Web Dashboard UI, CLI, and MCP Server.

**Architecture:** A centralized `GarminAPI.download_activity_gpx` core method fetches official GPX streams from Garmin Connect's `/download-service/export/gpx/activity/{id}` with smart local caching in `garmin_files/exports/{id}.gpx`. This is exposed via FastAPI streaming route, a sporty button in the web dashboard modal, a Click CLI command, and a native MCP tool.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Click, MCP Server, Vanilla JS & CSS.

## Global Constraints
- Target directory for cached GPX files: `garmin_files/exports/{activity_id}.gpx`
- Non-GPS activities (e.g., strength training, treadmill, yoga) must return HTTP 422 with a clean message and not write invalid files to cache.
- Antislop UI guidelines for Web Dashboard: high contrast, clean SVGs, clear active/hover/focus states.
- All new tests must pass using `pytest`.

---

### Task 1: Core API & Cache Manager

**Files:**
- Modify: `src/garminsynapse/core/api.py`
- Test: `tests/test_gpx_export_core.py`

**Interfaces:**
- Produces: `GarminAPI.download_activity_gpx(activity_id: int, use_cache: bool = True) -> bytes`
- Produces: `garmin_files/exports/{activity_id}.gpx`

- [ ] **Step 1: Write the failing test**
Create `tests/test_gpx_export_core.py` to test `download_activity_gpx` with mocked remote responses and verify local caching behavior.

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_gpx_export_core.py -v`
Expected: FAIL with `AttributeError: 'GarminAPI' object has no attribute 'download_activity_gpx'`.

- [ ] **Step 3: Implement `download_activity_gpx` in `GarminAPI`**
Add the method with cache checking, API download, validation for `<gpx` and `<trk`, and saving to cache.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_gpx_export_core.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
`git add src/garminsynapse/core/api.py tests/test_gpx_export_core.py && git commit -m "feat(core): add download_activity_gpx method with smart local caching"`

---

### Task 2: Web API Route for GPX Download

**Files:**
- Modify: `src/garminsynapse/web/routes.py`
- Test: `tests/test_gpx_export_web.py`

**Interfaces:**
- Consumes: `GarminAPI.download_activity_gpx(activity_id)`
- Produces: `GET /api/v1/activities/{activity_id}/export/gpx`

- [ ] **Step 1: Write the failing test**
Create `tests/test_gpx_export_web.py` to test the FastAPI endpoint for 200 attachment response, 422 for non-GPS activities, and 401 unauthenticated.

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_gpx_export_web.py -v`
Expected: FAIL with 404 or route not found.

- [ ] **Step 3: Implement endpoint in `src/garminsynapse/web/routes.py`**
Implement `@router.get("/activities/{activity_id}/export/gpx")` with clean filename header and error handling.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_gpx_export_web.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
`git add src/garminsynapse/web/routes.py tests/test_gpx_export_web.py && git commit -m "feat(web): add GPX activity export endpoint with file streaming"`

---

### Task 3: CLI Subcommand `garminsynapse export`

**Files:**
- Modify: `src/garminsynapse/cli.py`
- Test: `tests/test_gpx_export_cli.py`

**Interfaces:**
- Consumes: `GarminAPI.download_activity_gpx(activity_id)`
- Produces: CLI command `export`

- [ ] **Step 1: Write the failing test**
Create `tests/test_gpx_export_cli.py` using Click's `CliRunner`.

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_gpx_export_cli.py -v`
Expected: FAIL with `No such command 'export'`.

- [ ] **Step 3: Implement `export` command in `src/garminsynapse/cli.py`**
Add `@cli.command()` for `export` with `--output` and `--format` options.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_gpx_export_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
`git add src/garminsynapse/cli.py tests/test_gpx_export_cli.py && git commit -m "feat(cli): add export command for activity GPX"`

---

### Task 4: MCP Server Tool `export_activity_gpx`

**Files:**
- Modify: `src/garminsynapse/mcp/tools.py`
- Test: `tests/test_gpx_export_mcp.py`

**Interfaces:**
- Produces: MCP tool `export_activity_gpx(activity_id: int, output_dir: Optional[str] = None)`

- [ ] **Step 1: Write the failing test**
Create `tests/test_gpx_export_mcp.py` testing the MCP tool function.

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_gpx_export_mcp.py -v`
Expected: FAIL with `cannot import name 'export_activity_gpx'`.

- [ ] **Step 3: Implement `export_activity_gpx` in `src/garminsynapse/mcp/tools.py`**
Add tool decorated with `@mcp.tool()`.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_gpx_export_mcp.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**
`git add src/garminsynapse/mcp/tools.py tests/test_gpx_export_mcp.py && git commit -m "feat(mcp): add export_activity_gpx MCP tool"`

---

### Task 5: Web Dashboard UI Integration

**Files:**
- Modify: `src/garminsynapse/web/static/index.html`
- Modify: `src/garminsynapse/web/static/css/style.css`
- Modify: `src/garminsynapse/web/static/js/app.js`

**Interfaces:**
- Button `#modal-export-gpx-btn` in `#activity-modal`
- JS event listener triggering `/api/v1/activities/{act.id}/export/gpx` with blob download

- [ ] **Step 1: Add HTML button and CSS styling**
Add sporty "Export GPX" action button to the modal header in `index.html` and corresponding CSS in `style.css`.

- [ ] **Step 2: Add JS click handler in `app.js`**
Handle download via `fetch()` and Blob, with toast notification when an activity has no GPS coordinates.

- [ ] **Step 3: Verify static files syntax and browser behavior**
Check that files parse cleanly and buttons are responsive.

- [ ] **Step 4: Commit**
`git add src/garminsynapse/web/static/ && git commit -m "feat(ui): add sporty Export GPX button and download UX in activity modal"`

---

### Task 6: End-to-End Verification, Service Restart & Push

**Files:**
- Modify: `README.md`
- Restart: PM2 `garminsynapse` service

- [ ] **Step 1: Run full test suite**
Run: `pytest tests/ -v`
Confirm all unit and integration tests pass.

- [ ] **Step 2: Test live export via CLI or API**
Export an existing activity from the database and verify that a valid GPX XML is produced.

- [ ] **Step 3: Update README and documentation**
Document the new GPX export feature in CLI, Web UI, and MCP server documentation.

- [ ] **Step 4: Restart PM2 service**
Run: `pm2 restart garminsynapse` and verify HTTP 200 at `http://127.0.0.1:6060/api/v1/status`.

- [ ] **Step 5: Commit and Push to GitHub**
Commit all changes and push `main` to `origin/main`.
