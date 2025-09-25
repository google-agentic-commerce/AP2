#!/bin/bash

set -e

# Configuration
DOCS_HOST="${DOCS_HOST:-127.0.0.1}"
DOCS_PORT="${DOCS_PORT:-8000}"
DOCS_ADDR="${DOCS_HOST}:${DOCS_PORT}"

print_header() {
  echo "AP2 Documentation Server"
  echo "========================"
  echo
}

check_dependencies() {
  if ! command -v mkdocs &>/dev/null; then
    echo "Installing required packages..."
    pip install -q -r requirements-docs.txt
    echo "Dependencies installed"
  fi
}

verify_project_root() {
  if [ ! -f "mkdocs.yml" ]; then
    echo "Error: mkdocs.yml not found"
    echo "Please run this script from the project root."
    exit 1
  fi
}

start_server() {
  echo "Starting server..."
  echo "Documentation: http://${DOCS_ADDR}"
  echo "Press Ctrl+C to stop"
  echo
  mkdocs serve --dev-addr "${DOCS_ADDR}"
}

print_header
check_dependencies
verify_project_root
start_server
