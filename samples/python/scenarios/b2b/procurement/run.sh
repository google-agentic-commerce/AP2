#!/bin/bash

# A script to run the B2B Procurement Agent demo using AP2 mandates.

set -e
cd "$(dirname "$0")"

# Setup Python virtual environment if not already present
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  uv venv .venv
fi

# Activate venv (Scripts for Windows, bin for Linux/Mac)
source .venv/Scripts/activate || source .venv/bin/activate
echo "Virtual environment activated."

# Install AP2 project (editable mode) from repo root
echo "Installing AP2 project in editable mode..."
uv pip install -e ../../../../..

# Install FastAPI + Uvicorn if not already installed
uv pip install fastapi uvicorn

# Run the procurement agent service
echo "Starting B2B Procurement Agent on http://localhost:8010 ..."
uv run uvicorn samples.python.scenarios.b2b.procurement.main:app --reload --host 0.0.0.0 --port 8010
