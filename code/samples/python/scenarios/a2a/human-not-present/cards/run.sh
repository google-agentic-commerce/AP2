#!/bin/bash
# ---------------------------------------------------------------------------
# Run all servers for the A2A human-not-present flow (Card) and open the web client.
#
# Prerequisites: Node.js (npm), uv (astral.sh), curl
# Usage:         ./run.sh   (run from anywhere)
# ---------------------------------------------------------------------------

set -eu

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly LOG_DIR="$SCRIPT_DIR/.logs"
readonly WEB_CLIENT_PORT=5173
readonly AGENT_PORT=8080
readonly MERCHANT_TRIGGER_PORT=8081
readonly CREDENTIALS_PROVIDER_PORT=8082
readonly PAYMENT_PROCESSOR_PORT=8083
mkdir -p "$LOG_DIR"

if [ -f "$SCRIPT_DIR/../../../../../../../.env" ]; then
  set -a
  source "$SCRIPT_DIR/../../../../../../../.env"
  set +a
fi

if [ -f "$SCRIPT_DIR/../../../../src/roles/shopping_agent_v2/.env" ]; then
  set -a
  source "$SCRIPT_DIR/../../../../src/roles/shopping_agent_v2/.env"
  set +a
fi

export TEMP_DB_DIR="$SCRIPT_DIR/.temp-db"
export LOGS_DIR="$SCRIPT_DIR/.logs"

rm -rf "$TEMP_DB_DIR" "$LOGS_DIR"
mkdir -p "$TEMP_DB_DIR"
mkdir -p "$LOGS_DIR"

export MERCHANT_TRIGGER_STATE_PATH="$TEMP_DB_DIR/merchant_trigger_state.json"
export AP2_TOKEN_STORE_PATH="$TEMP_DB_DIR/ap2_token_store.json"
export MERCHANT_INVENTORY_PATH="$TEMP_DB_DIR/merchant_inventory.json"
export AGENT_PUBLIC_KEY_PATH="$TEMP_DB_DIR/agent_signing_key.pub"
export MERCHANT_SIGNING_KEY_PATH="$TEMP_DB_DIR/merchant_signing_key.pem"

pids=()

cleanup() {
  echo ""
  echo "Shutting down..."
  if [[ ${#pids[@]} -gt 0 ]]; then
    kill -TERM "${pids[@]}" 2>/dev/null || true
    sleep 1
    kill -KILL "${pids[@]}" 2>/dev/null || true
    wait "${pids[@]}" 2>/dev/null || true
  fi
  echo "Done."
}

trap cleanup EXIT

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# kill_port PORT
#   Kills any process listening on the given port.
kill_port() {
  local port="$1"
  local pid
  pid=$(lsof -ti tcp:"${port}" || true)
  if [ -n "$pid" ]; then
    echo "Killing process $pid on port $port"
    kill -9 $pid 2>/dev/null || true
  fi
}


# start_service NAME DIR COMMAND PORT
#   Launches COMMAND inside DIR in the background, redirects output to a log
#   file named after NAME, and records the PID for cleanup.
start_service() {
  local name="$1" dir="$2" cmd="$3" port="$4"
  echo "Starting ${name} (port ${port})..."
  (cd "$SCRIPT_DIR/$dir" && eval "$cmd") >"$LOG_DIR/${name}.log" 2>&1 &
  pids+=("$!")
}

# wait_for_url URL [TIMEOUT_SECONDS]
#   Polls URL every 0.5s until it returns HTTP 200 or the timeout expires.
wait_for_url() {
  local url="$1"
  local timeout="${2:-15}"
  local attempts=$(( timeout * 2 ))

  for (( i = 1; i <= attempts; i++ )); do
    if curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q 200; then
      return 0
    fi
    sleep 0.5
  done

  echo "ERROR: Timed out after ${timeout}s waiting for $url" >&2
  exit 1
}

# ---------------------------------------------------------------------------
# Launch services (order matters)
# ---------------------------------------------------------------------------

echo "Syncing workspace dependencies..."
(cd "$SCRIPT_DIR/../../../../" && uv sync --quiet 2>/dev/null) || true

export FLOW=card

kill_port $MERCHANT_TRIGGER_PORT
start_service "merchant-trigger" "../../../../src/roles/merchant_agent_mcp" \
  "uv run python trigger_server.py" $MERCHANT_TRIGGER_PORT
sleep 1

# Card flow: start legacy credential-provider and payment-processor trigger servers.
kill_port $CREDENTIALS_PROVIDER_PORT
start_service "credentials-provider" "../../../../src/roles/credentials_provider_mcp" \
  "uv run python trigger_server.py" $CREDENTIALS_PROVIDER_PORT
sleep 1

kill_port $PAYMENT_PROCESSOR_PORT
start_service "merchant-payment-processor" "../../../../src/roles/merchant_payment_processor_mcp" \
  "uv run python trigger_server.py" $PAYMENT_PROCESSOR_PORT
sleep 1

kill_port $AGENT_PORT
start_service "agent" "../../../../src/roles/shopping_agent_v2" \
  "uv run python run_server.py" $AGENT_PORT

echo "Waiting for agent..."
wait_for_url "http://localhost:$AGENT_PORT/a2a/shopping_agent/.well-known/agent-card.json" 120

kill_port $WEB_CLIENT_PORT
(cd "$SCRIPT_DIR/../../../../../../web-client" && npm install --no-fund --no-audit)
start_service "web-client" "../../../../../../web-client" \
  "VITE_FLOW=card npm run dev -- --port $WEB_CLIENT_PORT" $WEB_CLIENT_PORT


echo "Waiting for web client..."
wait_for_url "http://localhost:$WEB_CLIENT_PORT" 30

echo ""
echo "To simulate a drop going live (after signing a mandate), run:"
echo "  curl -X POST \"http://localhost:$MERCHANT_TRIGGER_PORT/trigger-price-drop?item_id=<item_id>&price=<price>&stock=10\""
echo ""
echo "Opening http://localhost:$WEB_CLIENT_PORT"
if command -v open >/dev/null 2>&1; then
  open "http://localhost:$WEB_CLIENT_PORT"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "http://localhost:$WEB_CLIENT_PORT"
else
  echo "Open http://localhost:$WEB_CLIENT_PORT in your browser."
fi

echo ""
echo "Press Ctrl+C to stop all servers."
wait
