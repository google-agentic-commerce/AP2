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

SAMPLE_DIR="$(cd "$(dirname "$0")/../../../.." && pwd)"
cd "$SAMPLE_DIR"

echo "=========================================="
echo "AP2 TypeScript Sample - Human-Present Cards"
echo "=========================================="

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

USE_VERTEXAI=$(printf "%s" "${GOOGLE_GENAI_USE_VERTEXAI}" | tr '[:upper:]' '[:lower:]')
if [ -z "${GOOGLE_API_KEY}" ] && [ "${USE_VERTEXAI}" != "true" ]; then
  echo "Error: GOOGLE_API_KEY is not set."
  echo "Either export GOOGLE_API_KEY or set GOOGLE_GENAI_USE_VERTEXAI=true."
  echo "See ${SAMPLE_DIR}/.env.example for reference."
  exit 1
fi

if [ ! -d node_modules ]; then
  echo "Installing dependencies..."
  npm install
fi

echo ""
echo "Starting all agents (merchant, credentials, payment processor) and the"
echo "Shopping Agent web UI on http://localhost:3001 ..."
echo "Press Ctrl+C to stop."
echo ""

exec npm run dev
