#!/bin/bash

# Runs the AP2-Haggle negotiation scenario end-to-end. The four standard AP2
# services (merchant, credentials provider, merchant payment processor,
# shopping agent web UI) start in the background, and the merchant is seeded
# with a small inventory config so its seller-strategist has concrete
# cost_floor / competitor intel to negotiate against.

set -e

PAYMENT_METHOD="CARD"
SCENARIO_DIR="samples/python/scenarios/a2a/negotiation"
export HAGGLE_MERCHANT_CONFIG="${PWD}/${SCENARIO_DIR}/config/inventory.json"
# Default Claude model used by both negotiator sub-agents; override as needed.
export HAGGLE_CLAUDE_MODEL="${HAGGLE_CLAUDE_MODEL:-claude-sonnet-4-6}"
export PAYMENT_METHOD

AGENTS_DIR="samples/python/src/roles"
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
  echo "Please set your GOOGLE_API_KEY environment variable (required by ADK / Gemini orchestration)."
  exit 1
fi

if [ -z "${ANTHROPIC_API_KEY}" ]; then
  echo "Please set your ANTHROPIC_API_KEY environment variable — the haggle sub-agents call Claude."
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

echo "Installing project in editable mode..."
uv pip install -e .

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
  rm -f "$LOG_DIR"/*
fi

pids=()
echo ""
echo "Starting remote servers and agents as background processes..."
UV_RUN_CMD="uv run --no-sync"
if [ -f ".env" ]; then
  UV_RUN_CMD="$UV_RUN_CMD --env-file .env"
fi

echo "-> Merchant Agent (port:8001 log:$LOG_DIR/merchant_agent.log) — HAGGLE_MERCHANT_CONFIG=$HAGGLE_MERCHANT_CONFIG"
HAGGLE_MERCHANT_CONFIG="$HAGGLE_MERCHANT_CONFIG" HAGGLE_CLAUDE_MODEL="$HAGGLE_CLAUDE_MODEL" ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  $UV_RUN_CMD --package ap2-samples python -m roles.merchant_agent >"$LOG_DIR/merchant_agent.log" 2>&1 &
pids+=($!)

echo "-> Credentials Provider (port:8002 log:$LOG_DIR/credentials_provider_agent.log)"
$UV_RUN_CMD --package ap2-samples python -m roles.credentials_provider_agent >"$LOG_DIR/credentials_provider_agent.log" 2>&1 &
pids+=($!)

echo "-> Merchant Payment Processor (port:8003 log:$LOG_DIR/mpp_agent.log)"
$UV_RUN_CMD --package ap2-samples python -m roles.merchant_payment_processor_agent >"$LOG_DIR/mpp_agent.log" 2>&1 &
pids+=($!)

echo ""
echo "All remote servers are starting."
echo "Starting the Shopping Agent web UI (port:8000)..."
HAGGLE_CLAUDE_MODEL="$HAGGLE_CLAUDE_MODEL" ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  $UV_RUN_CMD --package ap2-samples adk web --host 0.0.0.0 $AGENTS_DIR
