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

.PHONY: all build clean test run-merchant run-credentials run-processor run-all help fmt lint

all: fmt lint build

build:
	@echo "Building all agents..."
	@mkdir -p bin
	@go build -o bin/merchant_agent ./cmd/merchant_agent
	@go build -o bin/credentials_provider_agent ./cmd/credentials_provider_agent
	@go build -o bin/merchant_payment_processor_agent ./cmd/merchant_payment_processor_agent
	@echo "Build complete!"

clean:
	@echo "Cleaning build artifacts..."
	@rm -rf bin
	@echo "Clean complete!"

test:
	@echo "Running tests..."
	@go test ./...

fmt:
	@echo "Formatting code..."
	@go fmt ./...

lint:
	@echo "Running linter..."
	@go vet ./...

run-merchant:
	@echo "Starting Merchant Agent on port 8001..."
	@go run ./cmd/merchant_agent

run-credentials:
	@echo "Starting Credentials Provider Agent on port 8002..."
	@go run ./cmd/credentials_provider_agent

run-processor:
	@echo "Starting Merchant Payment Processor Agent on port 8003..."
	@go run ./cmd/merchant_payment_processor_agent

run-all:
	@echo "Starting all agents..."
	@bash scenarios/a2a/human-present/cards/run.sh

deps:
	@echo "Downloading dependencies..."
	@go mod download
	@go mod tidy

help:
	@echo "Available targets:"
	@echo "  make build         - Build all agent binaries"
	@echo "  make clean         - Remove build artifacts"
	@echo "  make test          - Run tests"
	@echo "  make fmt           - Format code"
	@echo "  make lint          - Run linter"
	@echo "  make deps          - Download and tidy dependencies"
	@echo "  make run-merchant  - Run merchant agent"
	@echo "  make run-credentials - Run credentials provider agent"
	@echo "  make run-processor - Run payment processor agent"
	@echo "  make run-all       - Run all agents (background)"
