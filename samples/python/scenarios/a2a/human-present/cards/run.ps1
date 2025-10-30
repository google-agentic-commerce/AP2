# PowerShell script to automate the execution of the card_payment example.
# It starts all necessary servers and agents in the background,
# and then runs the client.

# Exit immediately if any command exits with a non-zero status.
$ErrorActionPreference = "Stop"

# The directory containing the agents.
$AGENTS_DIR = "samples/python/src/roles"
# A directory to store logs.
$LOG_DIR = ".logs"

# Check if we're in the right directory
if (-not (Test-Path $AGENTS_DIR)) {
    Write-Host "Error: Directory '$AGENTS_DIR' not found." -ForegroundColor Red
    Write-Host "Please run this script from the root of the repository." -ForegroundColor Red
    exit 1
}

# Load .env file if it exists
if (Test-Path ".env") {
    Write-Host "Loading environment variables from .env file..."
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]*)\s*=\s*(.*)\s*$") {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            # Remove quotes if present
            $value = $value -replace '^["'']|["'']$', ''
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
            Write-Host "Set $name" -ForegroundColor Green
        }
    }
}

# Check for required API key
$USE_VERTEXAI = $env:GOOGLE_GENAI_USE_VERTEXAI
if (-not $env:GOOGLE_API_KEY -and $USE_VERTEXAI -ne "true") {
    Write-Host "Please set your GOOGLE_API_KEY environment variable before running." -ForegroundColor Red
    Write-Host "Alternatively, set GOOGLE_GENAI_USE_VERTEXAI=true to use Vertex AI with ADC." -ForegroundColor Yellow
    exit 1
}

# Set up and activate a virtual environment.
Write-Host "Setting up the Python virtual environment..." -ForegroundColor Cyan

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment with uv..."
    uv venv
}

# Activate virtual environment (Windows)
Write-Host "Activating virtual environment..."
& ".\.venv\Scripts\Activate.ps1"
Write-Host "Virtual environment activated." -ForegroundColor Green

Write-Host "Installing project in editable mode..."
uv pip install -e .

# Create a directory for log files.
if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null
}

# Store background process jobs for cleanup
$jobs = @()

# This function is called to clean up background processes
function Cleanup {
    Write-Host ""
    Write-Host "Shutting down background processes..." -ForegroundColor Yellow
    if ($jobs.Count -gt 0) {
        foreach ($job in $jobs) {
            if ($job.State -eq "Running") {
                Stop-Job $job -ErrorAction SilentlyContinue
                Remove-Job $job -ErrorAction SilentlyContinue
            }
        }
    }
    Write-Host "Cleanup complete." -ForegroundColor Green
}

# Register cleanup function to run on script exit
Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action { Cleanup } | Out-Null

# Handle Ctrl+C gracefully
$null = Register-ObjectEvent -InputObject ([Console]) -EventName CancelKeyPress -Action {
    Cleanup
    [Environment]::Exit(0)
}

# Explicitly sync to ensure the virtual environment is up to date.
Write-Host "Syncing virtual environment with uv sync..." -ForegroundColor Cyan
try {
    uv sync --package ap2-samples
    Write-Host "Virtual environment synced successfully." -ForegroundColor Green
} catch {
    Write-Host "Error: uv sync failed. Aborting deployment." -ForegroundColor Red
    exit 1
}

# Clear old logs.
Write-Host "Clearing the logs directory..." -ForegroundColor Cyan
if (Test-Path $LOG_DIR) {
    Remove-Item "$LOG_DIR\*" -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Starting remote servers and agents as background processes..." -ForegroundColor Cyan

# Base UV command (prevent parallel sync collisions)
$UV_RUN_CMD = "uv run --no-sync"

if (Test-Path ".env") {
    $UV_RUN_CMD += " --env-file .env"
}

Write-Host "-> Starting the Merchant Agent (port:8001 log:$LOG_DIR/merchant_agent.log)..." -ForegroundColor Yellow
$job1 = Start-Job -ScriptBlock {
    param($uvCmd, $logFile)
    Invoke-Expression "$uvCmd --package ap2-samples python -m roles.merchant_agent" > $logFile 2>&1
} -ArgumentList $UV_RUN_CMD, "$LOG_DIR/merchant_agent.log"
$jobs += $job1

Write-Host "-> Starting the Credentials Provider (port:8002 log:$LOG_DIR/credentials_provider_agent.log)..." -ForegroundColor Yellow
$job2 = Start-Job -ScriptBlock {
    param($uvCmd, $logFile)
    Invoke-Expression "$uvCmd --package ap2-samples python -m roles.credentials_provider_agent" > $logFile 2>&1
} -ArgumentList $UV_RUN_CMD, "$LOG_DIR/credentials_provider_agent.log"
$jobs += $job2

Write-Host "-> Starting the Card Processor Agent (port:8003 log:$LOG_DIR/mpp_agent.log)..." -ForegroundColor Yellow
$job3 = Start-Job -ScriptBlock {
    param($uvCmd, $logFile)
    Invoke-Expression "$uvCmd --package ap2-samples python -m roles.merchant_payment_processor_agent" > $logFile 2>&1
} -ArgumentList $UV_RUN_CMD, "$LOG_DIR/mpp_agent.log"
$jobs += $job3

Write-Host ""
Write-Host "All remote servers are starting." -ForegroundColor Green

# Give servers a moment to start
Start-Sleep -Seconds 3

Write-Host "Starting the Shopping Agent..." -ForegroundColor Cyan
Write-Host "The Shopping Agent will be available at: http://localhost:8080" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop all services." -ForegroundColor Yellow

try {
    Invoke-Expression "$UV_RUN_CMD --package ap2-samples adk web --host 0.0.0.0 $AGENTS_DIR"
} finally {
    Cleanup
}