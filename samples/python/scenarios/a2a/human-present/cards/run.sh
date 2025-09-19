#!/bin/bash

# A script to automate the execution of the card_payment example.
# It starts all necessary servers and agents in the background,
# and then runs the client.

# Exit immediately if any command exits with a non-zero status.
set -e

# The directory containing the agents.
AGENTS_DIR="samples/python/src/roles"
# A directory to store logs.
LOG_DIR=".logs"

if [ ! -d "$AGENTS_DIR" ]; then
  echo "Error: Directory '$AGENTS_DIR' not found."
  echo "Please run this script from the root of the repository."
  exit 1
fi

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

USE_VERTEXAI=$(printf "%s" "${GOOGLE_GENAI_USE_VERTEXAI}" | tr '[:upper:]' '[:lower:]')
if [ -z "${GOOGLE_API_KEY}" ] && [ "${USE_VERTEXAI}" != "true" ]; then
  echo "Please set your GOOGLE_API_KEY environment variable before running."
  echo "Alternatively, set GOOGLE_GENAI_USE_VERTEXAI=true to use Vertex AI with ADC."
  exit 1
fi

# Set up and activate a virtual environment.
echo "Setting up the Python virtual environment..."

if [ ! -d ".venv" ]; then
  uv venv
fi

source .venv/bin/activate
echo "Virtual environment activated."

echo "Installing project in editable mode..."
uv pip install -e .

# Create a directory for log files.
mkdir -p "$LOG_DIR"

# This function is called automatically when the script exits (for any reason)
# to ensure all background processes are terminated.
cleanup() {
  echo ""
  echo "Shutting down background processes..."
  if [ ${#pids[@]} -ne 0 ]; then
    # Kill all processes using their PIDs stored in the array.
    # The 2>/dev/null suppresses "Terminated" messages or errors if a process is already gone.
    kill "${pids[@]}" 2>/dev/null
    wait "${pids[@]}" 2>/dev/null
  fi
  echo "Cleanup complete."
}

# Trap the EXIT signal to call the cleanup function. This ensures cleanup
# runs whether the script finishes successfully, fails, or is interrupted.
trap cleanup EXIT

# Explicitly sync to ensures the virtual environment is up to date.
echo "Syncing virtual environment with uv sync..."
if uv sync --package ap2-samples; then
  echo "Virtual environment synced successfully."
else
  echo "Error: uv sync failed. Aborting deployment."
  exit 1
fi

# Clear old logs.
echo "Clearing the logs directory..."
if [ -d "$LOG_DIR" ]; then
  rm -f "$LOG_DIR"/*
fi

# Start all the remote agents & servers.
pids=()

echo ""
echo "Starting remote servers and agents as background processes..."

# uv sync is explicitly run before starting any agents.
# Prevent servers starting in parallel from colliding by trying to sync again.
UV_RUN_CMD="uv run --no-sync"

if [ -f ".env" ]; then
  UV_RUN_CMD="$UV_RUN_CMD --env-file .env"
fi

echo "-> Starting the Merchant Agent (port:8001 log:$LOG_DIR/merchant_agent.log)..."
$UV_RUN_CMD --package ap2-samples python -m roles.merchant_agent >"$LOG_DIR/merchant_agent.log" 2>&1 &
pids+=($!)

echo "-> Starting the Credentials Provider (port:8002 log:$LOG_DIR/credentials_provider_agent.log)..."
$UV_RUN_CMD --package ap2-samples python -m roles.credentials_provider_agent >"$LOG_DIR/credentials_provider_agent.log" 2>&1 &
pids+=($!)

echo "-> Starting the Card Processor Agent (port:8003 log:$LOG_DIR/mpp_agent.log)..."
$UV_RUN_CMD --package ap2-samples python -m roles.merchant_payment_processor_agent >"$LOG_DIR/mpp_agent.log" 2>&1 &
pids+=($!)

echo ""
echo "All remote servers are starting."

echo "Starting the Shopping Agent..."
$UV_RUN_CMD --package ap2-samples adk web --host 0.0.0.0 $AGENTS_DIR
