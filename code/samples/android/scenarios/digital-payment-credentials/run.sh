#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

REFRESH_FLAG="--refresh-dependencies"
if [ "$1" == "-o" ]; then
  REFRESH_FLAG=""
fi

# Get the absolute path of the directory containing this script.
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

# Navigate to the root of the agentic payments repository.
REPO_ROOT=$(cd "$SCRIPT_DIR/../../../../../" && pwd)
SAMPLES_ROOT=$(cd "$SCRIPT_DIR/../../../" && pwd)

echo "Navigating to the root of the repository: $REPO_ROOT"
cd "$REPO_ROOT"

# Source .env if present (for GOOGLE_API_KEY, etc.)
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

# Shared temp directory for keys and state across all agents.
export TEMP_DB_DIR="${TEMP_DB_DIR:-$(pwd)/.temp-db}"
mkdir -p "$TEMP_DB_DIR"
export AGENT_PROVIDER_PUBLIC_KEY_PATH="$TEMP_DB_DIR/agent_provider_signing_key.pub"

# Extract public key from DPC provider certificate
echo "Extracting public key from DPC provider certificate..."
uv run python -c "from cryptography import x509; from cryptography.hazmat.primitives import serialization; cert = x509.load_pem_x509_certificate(open('$SAMPLES_ROOT/certs/ds_cert_sdjwt.pem', 'rb').read()); open('$AGENT_PROVIDER_PUBLIC_KEY_PATH', 'wb').write(cert.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))"

echo "Building the Android app..."
cd "$SAMPLES_ROOT/android/shopping_assistant"
./gradlew build $REFRESH_FLAG
echo "Android app built successfully."

cd "$REPO_ROOT"

if [ ! -d "$REPO_ROOT/.logs" ]; then
  mkdir "$REPO_ROOT/.logs"
fi

echo "Killing existing processes on ports 8001 and 8002..."
lsof -ti:8001 | xargs kill -9 2>/dev/null || true
lsof -ti:8002 | xargs kill -9 2>/dev/null || true

trap 'echo "Shutting down background processes..."; kill $(jobs -p) 2>/dev/null || true' EXIT

echo "Starting the Credential Provider Agent (port 8002) in the background..."
uv run --package ap2-samples python -m roles.credentials_provider_agent >"$REPO_ROOT/.logs/credential_provider_agent.log" 2>&1 &

echo "Starting the Merchant server (port 8001) in the background..."
uv run --package ap2-samples python -m roles.merchant_agent >"$REPO_ROOT/.logs/merchant_agent.log" 2>&1 &

echo "Waiting 5 seconds for servers to initialize..."
sleep 5

echo "Setting up reverse port forwarding..."
adb reverse --remove-all 2>/dev/null || true
adb reverse tcp:8001 tcp:8001
adb reverse tcp:8002 tcp:8002

echo "Installing the app on the connected device/emulator..."
adb install -r "$SAMPLES_ROOT/android/shopping_assistant/app/build/outputs/apk/debug/app-debug.apk"

echo "Launching the app..."
adb shell am start -n "com.example.a2achatassistant/.MainActivity"

echo "Servers are running and app is launched! Press CTRL+C to quit."
wait

