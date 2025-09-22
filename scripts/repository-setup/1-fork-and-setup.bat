@echo off
REM AI Shopping Concierge - Repository Setup Script (Windows)
REM This script helps you fork the AP2 repo and set up the development environment

echo 🚀 AI Shopping Concierge - Repository Setup (Windows)
echo =======================================================

REM Configuration
set "UPSTREAM_REPO=https://github.com/google-agentic-commerce/AP2.git"
set "GITHUB_USERNAME=%1"
if "%GITHUB_USERNAME%"=="" set "GITHUB_USERNAME=ankitap"
set "PRODUCT_REPO=ai-shopping-concierge-ap2"
set "FORK_REPO=https://github.com/%GITHUB_USERNAME%/AP2.git"
set "PRODUCT_REPO_URL=https://github.com/%GITHUB_USERNAME%/%PRODUCT_REPO%.git"

echo 📋 Configuration:
echo    Upstream: %UPSTREAM_REPO%
echo    Your Fork: %FORK_REPO%
echo    Product Repo: %PRODUCT_REPO_URL%
echo.

REM Step 1: Verify git is installed
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Git is not installed. Please install git first.
    echo    Download from: https://git-scm.com/download/windows
    pause
    exit /b 1
)

echo ✅ Git is available

REM Step 2: Check if we're in the AP2 directory
if not exist "pyproject.toml" (
    echo ❌ Please run this script from the AP2 repository root directory
    pause
    exit /b 1
)

if not exist ".git" (
    echo ❌ This doesn't appear to be a git repository
    pause
    exit /b 1
)

echo ✅ Running from AP2 repository

REM Step 3: Set up remotes for the forked AP2 repo
echo 🔧 Setting up git remotes...

REM Add upstream remote (Google's original repo)
git remote get-url upstream >nul 2>&1
if %errorlevel% equ 0 (
    echo    ⚠️  Upstream remote already exists, updating...
    git remote set-url upstream "%UPSTREAM_REPO%"
) else (
    echo    ➕ Adding upstream remote...
    git remote add upstream "%UPSTREAM_REPO%"
)

REM Update origin to point to your fork
echo    🔄 Updating origin to your fork...
git remote set-url origin "%FORK_REPO%"

REM Verify remotes
echo ✅ Git remotes configured:
git remote -v

echo.
echo 📝 MANUAL STEPS REQUIRED:
echo =========================
echo.
echo 1. 🍴 Fork the AP2 repository:
echo    - Go to: https://github.com/google-agentic-commerce/AP2
echo    - Click 'Fork' button
echo    - Choose your GitHub account (%GITHUB_USERNAME%)
echo.
echo 2. 🆕 Create your product repository:
echo    - Go to: https://github.com/new
echo    - Repository name: %PRODUCT_REPO%
echo    - Description: 'AI Shopping Concierge built on AP2 Protocol'
echo    - Make it Public
echo    - Add README, .gitignore (Python), and LICENSE
echo.
echo 3. 🔑 Set up authentication:
echo    - Configure SSH keys: https://docs.github.com/en/authentication/connecting-to-github-with-ssh
echo    - Or use Personal Access Token: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token
echo.
echo 4. ▶️  Run the next script:
echo    scripts\repository-setup\2-sync-and-verify.bat
echo.

echo 💡 TIP: Make sure to replace '%GITHUB_USERNAME%' with your actual GitHub username!
echo.
echo Press any key to continue...
pause >nul