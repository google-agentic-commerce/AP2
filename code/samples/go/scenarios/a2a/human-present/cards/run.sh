#!/bin/bash
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -e

echo "=========================================="
echo "AP2 Go Sample - Starting All Agents"
echo "=========================================="
echo ""

cd "$(dirname "$0")/../../../.."

echo "Installing dependencies..."
go mod download

echo ""
echo "Building agents..."
make build

echo ""
echo "Starting agents in background..."
echo ""

./bin/merchant_agent &
MERCHANT_PID=$!
echo "✓ Merchant Agent started (PID: $MERCHANT_PID) on http://localhost:8001"

./bin/credentials_provider_agent &
CREDENTIALS_PID=$!
echo "✓ Credentials Provider Agent started (PID: $CREDENTIALS_PID) on http://localhost:8002"

./bin/merchant_payment_processor_agent &
PROCESSOR_PID=$!
echo "✓ Merchant Payment Processor Agent started (PID: $PROCESSOR_PID) on http://localhost:8003"

echo ""
echo "=========================================="
echo "All agents are running!"
echo "=========================================="
echo ""
echo "Agent endpoints:"
echo "  - Merchant:              http://localhost:8001/a2a/merchant_agent"
echo "  - Credentials Provider:  http://localhost:8002/a2a/credentials_provider"
echo "  - Payment Processor:     http://localhost:8003/a2a/merchant_payment_processor_agent"
echo ""
echo "Press Ctrl+C to stop all agents"
echo ""

trap 'echo ""; echo "Stopping agents..."; kill $MERCHANT_PID $CREDENTIALS_PID $PROCESSOR_PID 2>/dev/null; exit' INT TERM

wait
