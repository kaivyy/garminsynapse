#!/usr/bin/env bash
# =============================================================
#  Garmin Synapse — One-Click Installer
#  This script checks and installs ALL prerequisites so the
#  user never needs to install anything manually.
# =============================================================
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

info()    { echo -e "${CYAN}ℹ ${NC} $1"; }
success() { echo -e "${GREEN}✅${NC} $1"; }
warn()    { echo -e "${YELLOW}⚠️ ${NC} $1"; }
fail()    { echo -e "${RED}❌${NC} $1"; exit 1; }

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   🚀 Garmin Synapse Installer v0.1.0    ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${NC}"
echo ""

# ----------------------------------------------------------
# 1. Check Python >= 3.9
# ----------------------------------------------------------
info "Checking Python version..."
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 9 ]; then
        success "Python $PY_VERSION detected"
    else
        fail "Python >= 3.9 is required (found $PY_VERSION). Please upgrade: https://www.python.org/downloads/"
    fi
else
    fail "Python3 not found. Please install Python >= 3.9: https://www.python.org/downloads/"
fi

# ----------------------------------------------------------
# 2. Check pip
# ----------------------------------------------------------
info "Checking pip..."
if python3 -m pip --version &>/dev/null; then
    PIP_VERSION=$(python3 -m pip --version | awk '{print $2}')
    success "pip $PIP_VERSION detected"
else
    warn "pip not found. Attempting to install..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -qq && sudo apt-get install -y -qq python3-pip
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y python3-pip
    elif command -v pacman &>/dev/null; then
        sudo pacman -Sy --noconfirm python-pip
    elif command -v brew &>/dev/null; then
        brew install python3
    else
        fail "Cannot auto-install pip. Please install it manually: https://pip.pypa.io/en/stable/installation/"
    fi
    success "pip installed"
fi

# ----------------------------------------------------------
# 3. Check git (needed for editable install)
# ----------------------------------------------------------
info "Checking git..."
if command -v git &>/dev/null; then
    success "git $(git --version | awk '{print $3}') detected"
else
    warn "git not found. Attempting to install..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get update -qq && sudo apt-get install -y -qq git
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y git
    elif command -v pacman &>/dev/null; then
        sudo pacman -Sy --noconfirm git
    elif command -v brew &>/dev/null; then
        brew install git
    else
        fail "Cannot auto-install git. Please install it manually."
    fi
    success "git installed"
fi

# ----------------------------------------------------------
# 4. Install system dependencies for Playwright (if needed)
# ----------------------------------------------------------
info "Checking system dependencies for Playwright browsers..."
if command -v apt-get &>/dev/null; then
    # Playwright on Debian/Ubuntu needs these libs
    MISSING_PKGS=""
    for pkg in libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2; do
        if ! dpkg -s "$pkg" &>/dev/null 2>&1; then
            MISSING_PKGS="$MISSING_PKGS $pkg"
        fi
    done
    if [ -n "$MISSING_PKGS" ]; then
        warn "Installing missing system libraries for Playwright:$MISSING_PKGS"
        sudo apt-get update -qq && sudo apt-get install -y -qq $MISSING_PKGS || warn "Some system libs could not be installed (Playwright browser auth may not work, but curl_cffi login will still function)"
    fi
    success "System dependencies OK"
else
    info "Non-Debian system detected — Playwright will attempt to install its own deps"
fi

# ----------------------------------------------------------
# 5. Install Python package + all dependencies (from pyproject.toml)
# ----------------------------------------------------------
info "Installing Garmin Synapse and all Python dependencies..."
echo ""

# Try normal install first; fallback to --break-system-packages for PEP 668 environments
if python3 -m pip install -e ".[dev]" --quiet --progress-bar on 2>&1 | tail -5; then
    : # success
elif python3 -m pip install -e ".[dev]" --break-system-packages --quiet --progress-bar on 2>&1 | tail -5; then
    warn "Installed with --break-system-packages (consider using a virtual environment)"
else
    fail "Failed to install Python dependencies. Try: python3 -m venv .venv && source .venv/bin/activate && ./install.sh"
fi
echo ""
success "Python packages installed (fastapi, uvicorn, click, sqlalchemy, curl_cffi, playwright, fitdecode, mcp, garminconnect, defusedxml, requests, pydantic, pytest)"

# ----------------------------------------------------------
# 6. Install Playwright Chromium browser binary
# ----------------------------------------------------------
info "Installing Playwright Chromium browser (for fallback auth)..."
if python3 -m playwright install chromium 2>/dev/null; then
    success "Playwright Chromium browser installed"
else
    warn "Playwright browser install failed (optional — curl_cffi primary login will still work)"
fi

# Also install system deps for playwright if available
python3 -m playwright install-deps chromium 2>/dev/null || true

# ----------------------------------------------------------
# 7. Create working directories
# ----------------------------------------------------------
info "Creating data directories..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$SCRIPT_DIR/garmin_files/ingest"
mkdir -p "$SCRIPT_DIR/garmin_files/process"
mkdir -p "$SCRIPT_DIR/garmin_files/storage"
mkdir -p "$SCRIPT_DIR/garmin_files/quarantine"
success "Data directories created at $SCRIPT_DIR/garmin_files/"

# ----------------------------------------------------------
# 8. Create user config directory
# ----------------------------------------------------------
info "Creating config directory..."
mkdir -p "$HOME/.garminsynapse"
success "Config directory: $HOME/.garminsynapse/"

# ----------------------------------------------------------
# 9. Validate installation
# ----------------------------------------------------------
info "Validating installation..."
echo ""

VALIDATION_PASSED=true

# Check core imports
if python3 -c "
import sys
sys.path.insert(0, '${SCRIPT_DIR}/src')
from garminsynapse.auth.tokens import TokenManager
from garminsynapse.auth.cffi_strategy import CffiStrategy
from garminsynapse.auth.manager import DualAuthManager
from garminsynapse.core.api import GarminAPI
from garminsynapse.core.fit_encoder import FitEncoder
from garminsynapse.db.schema import User, Activity, Sleep, HRV, Stress, BodyBattery
from garminsynapse.db.manager import DatabaseManager
from garminsynapse.etl.extractor import GarminExtractor
from garminsynapse.etl.processor import GarminProcessor
from garminsynapse.cli import cli
print('  Core modules ........... OK')
" 2>/dev/null; then
    success "Core modules validated"
else
    warn "Some core modules failed to import"
    VALIDATION_PASSED=false
fi

# Check MCP (optional, needs 'mcp' package)
if python3 -c "
import sys
sys.path.insert(0, '${SCRIPT_DIR}/src')
from garminsynapse.mcp.tools import garmin_status
print('  MCP tools .............. OK')
" 2>/dev/null; then
    success "MCP server validated"
else
    warn "MCP module could not be validated (mcp package may need manual install)"
fi

# Check FastAPI web app
if python3 -c "
import sys
sys.path.insert(0, '${SCRIPT_DIR}/src')
from garminsynapse.web.app import app
print('  FastAPI web app ........ OK')
" 2>/dev/null; then
    success "Web dashboard validated"
else
    warn "Web dashboard could not be validated"
    VALIDATION_PASSED=false
fi

echo ""
echo -e "${BOLD}══════════════════════════════════════════${NC}"

if [ "$VALIDATION_PASSED" = true ]; then
    echo -e "${GREEN}${BOLD}  ✅ Installation completed successfully!${NC}"
else
    echo -e "${YELLOW}${BOLD}  ⚠️  Installation completed with warnings${NC}"
fi

echo -e "${BOLD}══════════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}▶ Start Web Dashboard:${NC}"
echo -e "    ${BOLD}garminsynapse start-server${NC}"
echo -e "    ${BOLD}# or: python3 -m garminsynapse.cli start-server${NC}"
echo ""
echo -e "  ${CYAN}▶ Start MCP Server (AI Agent):${NC}"
echo -e "    ${BOLD}garminsynapse mcp${NC}"
echo -e "    ${BOLD}# or: python3 -m garminsynapse.cli mcp${NC}"
echo ""
echo -e "  ${CYAN}▶ Sync Garmin Data:${NC}"
echo -e "    ${BOLD}garminsynapse sync --email you@mail.com --password yourpass${NC}"
echo ""
echo -e "  ${CYAN}▶ Run Tests:${NC}"
echo -e "    ${BOLD}pytest tests/ -v${NC}"
echo ""
echo -e "  ${CYAN}📖 Dashboard URL:${NC} http://localhost:6060"
echo ""
