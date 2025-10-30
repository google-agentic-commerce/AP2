# PowerShell script for digital payment credentials Android scenario
# Builds Android app, installs it, and starts the merchant server

# Exit immediately if any command exits with a non-zero status.
$ErrorActionPreference = "Stop"

# Check for optional parameter
$REFRESH_FLAG = "--refresh-dependencies"
if ($args[0] -eq "-o") {
    $REFRESH_FLAG = ""
}

# Get the absolute path of the directory containing this script.
$SCRIPT_DIR = $PSScriptRoot

# Navigate to the root of the repository (4 levels up from this script)
$REPO_ROOT = Split-Path -Path (Split-Path -Path (Split-Path -Path (Split-Path -Path $SCRIPT_DIR)))

Write-Host "Navigating to the root of the repository: $REPO_ROOT" -ForegroundColor Cyan
Set-Location $REPO_ROOT

# Build the Android app
Write-Host "Building the Android app..." -ForegroundColor Cyan
Set-Location "$REPO_ROOT\samples\android\shopping_assistant"

# Check if gradlew.bat exists, otherwise use gradlew
$gradlewCmd = if (Test-Path ".\gradlew.bat") { ".\gradlew.bat" } else { ".\gradlew" }

try {
    & $gradlewCmd build $REFRESH_FLAG
    Write-Host "Android app built successfully." -ForegroundColor Green
} catch {
    Write-Host "Error building Android app: $_" -ForegroundColor Red
    exit 1
}

Write-Host "Installing the app on the connected device/emulator..." -ForegroundColor Yellow

# Check if adb is available
try {
    $adbVersion = adb version
    Write-Host "ADB found: $($adbVersion -split "`n" | Select-Object -First 1)" -ForegroundColor Green
} catch {
    Write-Host "Error: ADB (Android Debug Bridge) not found in PATH." -ForegroundColor Red
    Write-Host "Please install Android SDK Platform Tools and add them to your PATH." -ForegroundColor Yellow
    Write-Host "Download from: https://developer.android.com/studio/releases/platform-tools" -ForegroundColor Blue
    exit 1
}

# Check if device/emulator is connected
$devices = adb devices
if ($devices -like "*device*" -or $devices -like "*emulator*") {
    Write-Host "Android device/emulator detected." -ForegroundColor Green
} else {
    Write-Host "No Android device or emulator detected." -ForegroundColor Red
    Write-Host "Please connect a device or start an emulator." -ForegroundColor Yellow
    exit 1
}

try {
    adb install -r app\build\outputs\apk\debug\app-debug.apk
    Write-Host "App installed successfully." -ForegroundColor Green
} catch {
    Write-Host "Error installing app: $_" -ForegroundColor Red
    exit 1
}

Write-Host "Setting up reverse port forwarding (device:8001 -> host:8001)..." -ForegroundColor Yellow
try {
    adb reverse tcp:8001 tcp:8001
    Write-Host "Port forwarding set up successfully." -ForegroundColor Green
} catch {
    Write-Host "Warning: Could not set up port forwarding: $_" -ForegroundColor Yellow
}

Write-Host "Launching the app..." -ForegroundColor Cyan
try {
    adb shell am start -n "com.example.a2achatassistant/.MainActivity"
    Write-Host "App launched successfully." -ForegroundColor Green
} catch {
    Write-Host "Warning: Could not launch app: $_" -ForegroundColor Yellow
    Write-Host "You may need to launch the app manually on your device." -ForegroundColor Yellow
}

# Go back to the repo root
Set-Location $REPO_ROOT

# Ensure .logs directory exists before starting merchant server
$LOGS_DIR = "$REPO_ROOT\.logs"
if (-not (Test-Path $LOGS_DIR)) {
    Write-Host "Creating .logs directory..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Path $LOGS_DIR -Force | Out-Null
}

# Check for required environment variables
if (Test-Path ".env") {
    Write-Host "Loading environment variables from .env file..." -ForegroundColor Cyan
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]*)\s*=\s*(.*)\s*$") {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            # Remove quotes if present
            $value = $value -replace '^["'']|["'']$', ''
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

# Check for required API key
$USE_VERTEXAI = $env:GOOGLE_GENAI_USE_VERTEXAI
if (-not $env:GOOGLE_API_KEY -and $USE_VERTEXAI -ne "true") {
    Write-Host "Warning: GOOGLE_API_KEY not set and GOOGLE_GENAI_USE_VERTEXAI is not true." -ForegroundColor Yellow
    Write-Host "Please set your GOOGLE_API_KEY environment variable or configure Vertex AI." -ForegroundColor Yellow
    Write-Host "The merchant server may not work properly without proper authentication." -ForegroundColor Yellow
}

# Start the merchant server
Write-Host ""
Write-Host "Starting the merchant server..." -ForegroundColor Cyan
Write-Host "The merchant server will be available at: http://localhost:8001" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server." -ForegroundColor Yellow

try {
    uv run --package ap2-samples python -m roles.merchant_agent
} catch {
    Write-Host "Error starting merchant server: $_" -ForegroundColor Red
    exit 1
}