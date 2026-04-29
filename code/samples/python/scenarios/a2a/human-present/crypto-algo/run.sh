#!/bin/bash

# A script to automate the execution of the crypto-algo (on-chain USDC) AP2 example.
# It starts all necessary servers and agents in the background.

set -e

export PAYMENT_METHOD=CRYPTO_ALGO

AGENTS_DIR="code/samples/python/src/roles"
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

if [ -z "${ALGOVOI_API_KEY}" ]; then
  echo "Please set your ALGOVOI_API_KEY environment variable before running."
  exit 1
fi

echo "Setting up the Python virtual environment..."

if [ ! -d ".venv" ]; then
  uv venv
fi

case "$OSTYPE" in
  msys* | cygwin*)
    source .venv/Scripts/activate
    ;;
  *)
    source .venv/bin/activate
    ;;
esac
echo "Virtual environment activated."

mkdir -p "$LOG_DIR"

cleanup() {
  echo ""
  echo "Shutting down background processes..."
  if [ ${#pids[@]} -ne 0 ]; then
    kill "${pids[@]}" 2>/dev/null
    wait "${pids[@]}" 2>/dev/null
  fi
  echo "Cleanup complete."
}

trap cleanup EXIT

echo "Syncing virtual environment with uv sync..."
if uv sync --package ap2-samples; then
  echo "Virtual environment synced successfully."
else
  echo "Error: uv sync failed. Aborting."
  exit 1
fi

echo "Clearing the logs directory..."
if [ -d "$LOG_DIR" ]; then
  find "$LOG_DIR" -mindepth 1 -delete
fi

pids=()

echo ""
echo "Starting remote servers and agents as background processes..."

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

echo "-> Starting the Merchant Payment Processor Agent (port:8003 log:$LOG_DIR/mpp_agent.log)..."
$UV_RUN_CMD --package ap2-samples python -m roles.merchant_payment_processor_agent >"$LOG_DIR/mpp_agent.log" 2>&1 &
pids+=($!)

echo ""
echo "All remote servers are starting."

echo "Starting the Shopping Agent..."
$UV_RUN_CMD --package ap2-samples adk web --host 0.0.0.0 $AGENTS_DIR/shopping_agent
