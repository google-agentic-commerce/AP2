#!/bin/bash
# Exit on error and treat unset vars as errors
set -euo pipefail

# Directory of this script (so we can invoke run_cli.py reliably)
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOG_DIR=".logs" # run_cli.py writes logs here

# Load environment variables if present
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

# Require an API key
if [ -z "${GOOGLE_API_KEY:-}" ]; then
  echo "Please set your GOOGLE_API_KEY environment variable before running."
  exit 1
fi

# --- Environment Setup ---
echo "Setting up a clean Python virtual environment..."
# Deactivate if we're already in a venv; ignore if not
deactivate >/dev/null 2>&1 || true
rm -rf .venv
uv venv
source .venv/bin/activate
echo "Virtual environment activated."

echo "Syncing virtual environment with all dependencies (using cache)..."
uv sync --package ap2-samples

# Ensure the .logs directory exists (run_cli.py relies on it)
mkdir -p "$LOG_DIR"
rm -f "$LOG_DIR"/*

echo ""
echo "Starting the custom CLI for the Flight Shopping Demo..."
# Delegate all agent lifecycle to run_cli.py (it will start/stop the merchant)
python "${SCRIPT_DIR}/run_cli.py"
