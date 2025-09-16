#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

REFRESH_FLAG="--refresh-dependencies"
if [ "$1" == "-o" ]; then
  REFRESH_FLAG=""
fi

# Get the absolute path of the directory containing this script.
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)


# Navigate to the root of the agenticpayments repository.
REPO_ROOT=$(cd "$SCRIPT_DIR/../../../../" && pwd)

echo "Navigating to the root of the repository: $REPO_ROOT"
cd "$REPO_ROOT"

# Build the Android app
echo "Building the Android app..."
cd "$REPO_ROOT/samples/android/shopping_assistant"
./gradlew build $REFRESH_FLAG
echo "Android app built successfully."

echo "Installing the app on the connected device/emulator..."
adb install -r app/build/outputs/apk/debug/app-debug.apk

echo "Setting up reverse port forwarding (device:8001 -> host:8001)..."
adb reverse tcp:8001 tcp:8001

echo "Launching the app..."
adb shell am start -n "com.example.a2achatassistant/.MainActivity"

# Go back to the repo root
cd "$REPO_ROOT"

# Ensure .logs directory exists before starting merchant server
if [ ! -d "$REPO_ROOT/.logs" ]; then
  echo "Creating .logs directory..."
  mkdir "$REPO_ROOT/.logs"
fi

# Start the merchant server
echo "Starting the merchant server..."
uv run --package ap2-samples python -m roles.merchant_agent

