#!/bin/bash
# ---------------------------------------------------------------------------
# Run all servers for the TypeScript A2A human-not-present flow (Card) and
# open the web-client (reused from the v0.2 Python tree).
#
# Prerequisites: Node.js >= 20, npm
# Usage:         ./run.sh   (run from anywhere)
# ---------------------------------------------------------------------------

set -eu

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly TS_SAMPLES_ROOT="$(cd "$SCRIPT_DIR/../../../../" && pwd)"
readonly REPO_ROOT="$(cd "$TS_SAMPLES_ROOT/../../../" && pwd)"
readonly LOG_DIR="$SCRIPT_DIR/.logs"
readonly TEMP_DB_DIR="$SCRIPT_DIR/.temp-db"

readonly WEB_CLIENT_PORT=5173
readonly AGENT_PORT=8080
readonly MERCHANT_TRIGGER_PORT=8081
readonly CREDENTIALS_PROVIDER_PORT=8082
readonly PAYMENT_PROCESSOR_PORT=8083

mkdir -p "$LOG_DIR" "$TEMP_DB_DIR"

if [ -f "$REPO_ROOT/.env" ]; then
  set -a
  source "$REPO_ROOT/.env"
  set +a
fi

export LOGS_DIR="$LOG_DIR"
export TEMP_DB_DIR
export MERCHANT_TRIGGER_STATE_PATH="$TEMP_DB_DIR/merchant_trigger_state.json"
export AGENT_PORT MERCHANT_TRIGGER_PORT CREDENTIALS_PROVIDER_PORT PAYMENT_PROCESSOR_PORT

rm -f "$LOG_DIR"/*.log "$TEMP_DB_DIR"/*.json 2>/dev/null || true

pids=()

cleanup() {
  echo ""
  echo "Shutting down..."
  if [[ ${#pids[@]} -gt 0 ]]; then
    kill -TERM "${pids[@]}" 2>/dev/null || true
    sleep 1
    kill -KILL "${pids[@]}" 2>/dev/null || true
  fi
  echo "Done."
}
trap cleanup EXIT

kill_port() {
  local port="$1"
  local pid
  pid=$(lsof -ti tcp:"${port}" || true)
  if [ -n "$pid" ]; then
    echo "Killing process $pid on port $port"
    kill -9 $pid 2>/dev/null || true
  fi
}

start_service() {
  local name="$1" cmd="$2" port="$3"
  echo "Starting ${name} (port ${port})..."
  (cd "$TS_SAMPLES_ROOT" && eval "$cmd") >"$LOG_DIR/${name}.log" 2>&1 &
  pids+=("$!")
}

wait_for_url() {
  local url="$1"
  local timeout="${2:-30}"
  local attempts=$(( timeout * 2 ))
  for (( i = 1; i <= attempts; i++ )); do
    if curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q "200\|404"; then
      return 0
    fi
    sleep 0.5
  done
  echo "ERROR: Timed out after ${timeout}s waiting for $url" >&2
  exit 1
}

echo "Ensuring TypeScript deps are installed..."
(cd "$TS_SAMPLES_ROOT" && npm install --no-fund --no-audit --silent)

export FLOW=card

kill_port $MERCHANT_TRIGGER_PORT
start_service "merchant-trigger" \
  "npx tsx src/roles/merchant-agent-mcp/trigger-server.ts" \
  $MERCHANT_TRIGGER_PORT

kill_port $CREDENTIALS_PROVIDER_PORT
start_service "credentials-provider-trigger" \
  "npx tsx src/roles/credentials-provider-mcp/trigger-server.ts" \
  $CREDENTIALS_PROVIDER_PORT

kill_port $PAYMENT_PROCESSOR_PORT
start_service "payment-processor-trigger" \
  "npx tsx src/roles/merchant-payment-processor-mcp/trigger-server.ts" \
  $PAYMENT_PROCESSOR_PORT

kill_port $AGENT_PORT
start_service "shopping-agent-v2" \
  "npx tsx src/roles/shopping-agent-v2/server.ts" \
  $AGENT_PORT

echo "Waiting for shopping agent..."
wait_for_url "http://localhost:$AGENT_PORT/a2a/shopping_agent/.well-known/agent-card.json" 60

# Optional: reuse the v0.2 web-client if present at sibling worktree.
WEB_CLIENT_DIR_DEFAULT="/tmp/ap2-v02/code/web-client"
WEB_CLIENT_DIR="${WEB_CLIENT_DIR:-$WEB_CLIENT_DIR_DEFAULT}"

if [ -d "$WEB_CLIENT_DIR" ]; then
  kill_port $WEB_CLIENT_PORT
  echo "Installing web-client deps..."
  (cd "$WEB_CLIENT_DIR" && npm install --no-fund --no-audit --silent)
  echo "Starting web-client (port $WEB_CLIENT_PORT)..."
  ( cd "$WEB_CLIENT_DIR" \
      && VITE_AGENT_URL="http://localhost:$AGENT_PORT/a2a/shopping_agent" \
         VITE_MERCHANT_TRIGGER_URL="http://localhost:$MERCHANT_TRIGGER_PORT" \
         VITE_FLOW=card \
         npm run dev -- --port $WEB_CLIENT_PORT \
  ) >"$LOG_DIR/web-client.log" 2>&1 &
  pids+=("$!")
  wait_for_url "http://localhost:$WEB_CLIENT_PORT" 30
  echo ""
  echo "Opening http://localhost:$WEB_CLIENT_PORT"
  command -v open >/dev/null 2>&1 && open "http://localhost:$WEB_CLIENT_PORT" || true
else
  echo ""
  echo "Web-client not found at $WEB_CLIENT_DIR — skipping."
  echo "Set WEB_CLIENT_DIR or check out v0.2 (git worktree add /tmp/ap2-v02 v0.2.0)."
fi

echo ""
echo "To simulate a drop:"
echo "  curl -X POST \"http://localhost:$MERCHANT_TRIGGER_PORT/trigger-price-drop?item_id=<item_id>&price=<price>&stock=10\""
echo ""
echo "Press Ctrl+C to stop all servers."
wait
