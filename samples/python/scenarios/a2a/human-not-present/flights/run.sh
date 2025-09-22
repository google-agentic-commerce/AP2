#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -e

# Get the directory of this script to find the custom CLI runner
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

if [ -z "${GOOGLE_API_KEY}" ]; then
  echo "Please set your GOOGLE_API_KEY environment variable before running."
  exit 1
fi

# --- Environment Setup ---
# This ensures a clean, project-specific environment for every run
# without deleting the shared, global package cache.
echo "Setting up a clean Python virtual environment..."
deactivate || true # Deactivate if active, ignore error if not
rm -rf .venv
uv venv
source .venv/bin/activate
echo "Virtual environment activated."

# A single, reliable command to install everything.
# This will be VERY FAST on subsequent runs because it uses the uv cache.
echo "Syncing virtual environment with all dependencies (using cache)..."
uv sync --package ap2-samples

echo ""
echo "Starting the custom CLI for the Flight Shopping Demo..."

# Execute the custom Python runner script directly using the venv's python.
.venv/bin/python "${SCRIPT_DIR}/run_cli.py"
