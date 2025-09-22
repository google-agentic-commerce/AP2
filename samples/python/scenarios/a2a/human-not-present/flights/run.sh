#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -e

# Get the directory of this script to find the custom CLI runner
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
LOG_DIR=".logs" # Define the log directory

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
echo "Setting up a clean Python virtual environment..."
deactivate || true
rm -rf .venv
uv venv
source .venv/bin/activate
echo "Virtual environment activated."
echo "Syncing virtual environment with all dependencies (using cache)..."
uv sync --package ap2-samples

# This function is called automatically when the script exits
cleanup() {
	echo ""
	echo "--> Shutting down background merchant agent..."
	kill "$merchant_pid" 2>/dev/null
	wait "$merchant_pid" 2>/dev/null
	echo "--> Cleanup complete."
}
trap cleanup EXIT

# Ensure the .logs directory exists before starting the merchant server
mkdir -p "$LOG_DIR"
rm -f "$LOG_DIR"/*
# ----------------------------------------

# Start the flight merchant agent in the background.
echo "--> Starting Flight Merchant Agent in the background (log: $LOG_DIR/flight_merchant.log)..."
.venv/bin/python -m roles.merchant_agent_flights >"$LOG_DIR/flight_merchant.log" 2>&1 &
merchant_pid=$!
sleep 3

echo ""
echo "Starting the custom CLI for the Flight Shopping Demo..."
.venv/bin/python "${SCRIPT_DIR}/run_cli.py"
