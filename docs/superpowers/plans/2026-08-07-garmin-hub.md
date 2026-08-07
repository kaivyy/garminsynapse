# Garmin Synapse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `garminsynapse`, a unified Python platform combining 5-stage `curl_cffi` + Playwright dual-auth, full 140+ Garmin Connect API endpoints, SQLite relational database & ETL pipeline, native MCP Server tools, and a premium web dashboard SPA.

**Architecture:** Single-process FastAPI server serving a glassmorphism SPA dashboard (`/`), REST API (`/api/v1`), and Python MCP Server (`/mcp` / stdio). Underlying layers handle dual auth (`curl_cffi` + Playwright fallback), 40+ table SQLite DB, and file-based ETL pipeline.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, SQLite, SQLAlchemy, `curl_cffi`, `playwright`, `mcp` SDK, `fitdecode`, Vanilla HTML5/CSS3/JS (Vite-ready SPA).

## Global Constraints

- Root project directory: `/root/garminsynapse`
- Database: SQLite 3.35.0+ at `/root/garminsynapse/garmin_data.db`
- Token storage: `~/.garminsynapse/tokens.json`
- Raw file archive: `/root/garminsynapse/garmin_files/` (`ingest`, `process`, `storage`, `quarantine`)
- Clean modular boundaries with full unit test coverage per task.

---

### Task 1: Package Scaffolding & PyProject Setup

**Files:**
- Create: `/root/garminsynapse/pyproject.toml`
- Create: `/root/garminsynapse/src/garminsynapse/__init__.py`
- Create: `/root/garminsynapse/tests/test_scaffold.py`

**Interfaces:**
- Produces: Package structure `garminsynapse` and dependency lock definitions.

- [ ] **Step 1: Write failing scaffold test**
- [ ] **Step 2: Create `pyproject.toml` with `fastapi`, `uvicorn`, `curl_cffi`, `sqlalchemy`, `mcp`, `playwright`, `fitdecode`, `pytest`**
- [ ] **Step 3: Create package structure under `/root/garminsynapse/src/garminsynapse`**
- [ ] **Step 4: Run tests to verify package initialization**
- [ ] **Step 5: Commit**

---

### Task 2: Dual Auth Engine (`garminsynapse.auth`)

**Files:**
- Create: `/root/garminsynapse/src/garminsynapse/auth/tokens.py`
- Create: `/root/garminsynapse/src/garminsynapse/auth/cffi_strategy.py`
- Create: `/root/garminsynapse/src/garminsynapse/auth/playwright_strategy.py`
- Test: `/root/garminsynapse/tests/test_auth.py`

**Interfaces:**
- Produces: `AuthManager.login(email, password)` returning valid session headers & OAuth tokens.

- [ ] **Step 1: Write failing auth unit test for token persistence and strategy selection**
- [ ] **Step 2: Implement `tokens.py` for reading/writing `~/.garminsynapse/tokens.json`**
- [ ] **Step 3: Implement `cffi_strategy.py` with 5-stage TLS impersonation login**
- [ ] **Step 4: Implement `playwright_strategy.py` for headless browser fallback**
- [ ] **Step 5: Run unit tests to verify auth manager logic**
- [ ] **Step 6: Commit**

---

### Task 3: Database & Schema Engine (`garminsynapse.db`)

**Files:**
- Create: `/root/garminsynapse/src/garminsynapse/db/schema.py`
- Create: `/root/garminsynapse/src/garminsynapse/db/manager.py`
- Test: `/root/garminsynapse/tests/test_db.py`

**Interfaces:**
- Produces: `DatabaseManager` providing connection pooling, raw DDL execution, upsert helpers, `downsample()`, and `prune()`.

- [ ] **Step 1: Write failing DB unit test for table creation and model upserting**
- [ ] **Step 2: Implement `schema.py` with 40+ table SQLAlchemy ORM models**
- [ ] **Step 3: Implement `manager.py` for DDL init, foreign key enforcement, downsampling, and pruning**
- [ ] **Step 4: Run DB unit tests**
- [ ] **Step 5: Commit**

---

### Task 4: Full API Core & FIT Encoder (`garminsynapse.core`)

**Files:**
- Create: `/root/garminsynapse/src/garminsynapse/core/api.py`
- Create: `/root/garminsynapse/src/garminsynapse/core/fit_encoder.py`
- Test: `/root/garminsynapse/tests/test_api.py`

**Interfaces:**
- Produces: `GarminAPI` class wrapping 140+ endpoints with retry decorator and token auto-refresh.

- [ ] **Step 1: Write failing test for API endpoint routing and error handling**
- [ ] **Step 2: Implement `api.py` with 13 endpoint categories**
- [ ] **Step 3: Implement `fit_encoder.py` for binary FIT weight scale uploads**
- [ ] **Step 4: Run API tests with mocked HTTP responses**
- [ ] **Step 5: Commit**

---

### Task 5: ETL Extractor & Processor (`garminsynapse.etl`)

**Files:**
- Create: `/root/garminsynapse/src/garminsynapse/etl/extractor.py`
- Create: `/root/garminsynapse/src/garminsynapse/etl/processor.py`
- Test: `/root/garminsynapse/tests/test_etl.py`

**Interfaces:**
- Produces: `GarminExtractor` and `GarminProcessor` for downloading raw files and populating SQLite DB.

- [ ] **Step 1: Write failing test for file extraction and parsing**
- [ ] **Step 2: Implement `extractor.py` for downloading FIT/TCX/JSON files**
- [ ] **Step 3: Implement `processor.py` with `fitdecode` parser and bulk upserts**
- [ ] **Step 4: Run ETL unit tests**
- [ ] **Step 5: Commit**

---

### Task 6: Native MCP Server (`garminsynapse.mcp`)

**Files:**
- Create: `/root/garminsynapse/src/garminsynapse/mcp/tools.py`
- Create: `/root/garminsynapse/src/garminsynapse/mcp/server.py`
- Test: `/root/garminsynapse/tests/test_mcp.py`

**Interfaces:**
- Produces: `MCPServer` exposing tools (`garmin_status`, `get_daily_summary`, `list_activities`, `query_garmin_db`, etc.).

- [ ] **Step 1: Write failing test for MCP tool execution and schemas**
- [ ] **Step 2: Implement `tools.py` tool definitions and handlers**
- [ ] **Step 3: Implement `server.py` supporting STDIO and SSE transport**
- [ ] **Step 4: Run MCP unit tests**
- [ ] **Step 5: Commit**

---

### Task 7: Premium Web Dashboard UI & REST API (`garminsynapse.web`)

**Files:**
- Create: `/root/garminsynapse/src/garminsynapse/web/app.py`
- Create: `/root/garminsynapse/src/garminsynapse/web/routes.py`
- Create: `/root/garminsynapse/src/garminsynapse/web/static/index.html`
- Create: `/root/garminsynapse/src/garminsynapse/web/static/css/style.css`
- Create: `/root/garminsynapse/src/garminsynapse/web/static/js/app.js`
- Test: `/root/garminsynapse/tests/test_web.py`

**Interfaces:**
- Produces: Running FastAPI web app at `/` with REST endpoints (`/api/v1/*`) and static dashboard SPA.

- [ ] **Step 1: Write failing REST API test for status and daily summary endpoints**
- [ ] **Step 2: Implement `routes.py` and `app.py`**
- [ ] **Step 3: Implement frontend SPA (`index.html`, `style.css` glassmorphism, `app.js` dashboard JS)**
- [ ] **Step 4: Run Web API integration tests**
- [ ] **Step 5: Commit**

---

### Task 8: End-to-End Verification & CLI Runner

**Files:**
- Create: `/root/garminsynapse/src/garminsynapse/cli.py`
- Test: `/root/garminsynapse/tests/test_e2e.py`

**Interfaces:**
- Produces: `garminsynapse` CLI entrypoint supporting `start-server`, `sync`, `mcp`, `downsample`, `prune`.

- [ ] **Step 1: Implement `cli.py` entrypoint**
- [ ] **Step 2: Run full test suite (`pytest`) and end-to-end verification**
- [ ] **Step 3: Final Commit**
