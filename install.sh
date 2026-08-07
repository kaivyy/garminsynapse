#!/usr/bin/env bash
set -e

echo "🚀 Installing Garmin Synapse..."

# 1. Install Python dependencies
pip install -e .

# 2. Install Playwright browser binaries
playwright install chromium

# 3. Create file archive directories
mkdir -p garmin_files/ingest garmin_files/process garmin_files/storage garmin_files/quarantine

echo "✅ Garmin Synapse installation completed successfully!"
echo "💡 Run Web Dashboard (Port 6060):  python3 -m garminsynapse.cli start-server"
echo "🤖 Run MCP Server for AI Agent:     python3 -m garminsynapse.cli mcp"
