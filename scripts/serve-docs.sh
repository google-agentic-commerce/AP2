#!/bin/bash

# Local Documentation Server Helper Script
# This script sets up and starts a local MkDocs server for AP2 documentation

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    printf "${BLUE}[INFO]${NC} %s\n" "$1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║                    AP2 Local Documentation Server                           ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Check if we're in the right directory
check_directory() {
    if [ ! -f "mkdocs.yml" ]; then
        print_error "mkdocs.yml not found. Please run this script from the AP2 repository root."
        exit 1
    fi
    print_status "Found mkdocs.yml - in correct directory"
}

# Check if Python is available
check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is required but not installed."
        print_status "Please install Python 3 and try again."
        exit 1
    fi
    print_status "Python 3 found: $(python3 --version)"
}

# Check if uv is available (preferred) or pip
check_package_manager() {
    if command -v uv &> /dev/null; then
        PACKAGE_MANAGER="uv"
        print_status "Using uv package manager"
    elif command -v pip &> /dev/null; then
        PACKAGE_MANAGER="pip"
        print_warning "uv not found, falling back to pip"
    else
        print_error "Neither uv nor pip found. Please install a Python package manager."
        exit 1
    fi
}

# Install documentation dependencies
install_dependencies() {
    print_status "Installing documentation dependencies..."

    if [ ! -f "requirements-docs.txt" ]; then
        print_error "requirements-docs.txt not found"
        exit 1
    fi

    if [ "$PACKAGE_MANAGER" = "uv" ]; then
        uv pip install -r requirements-docs.txt
    else
        pip install -r requirements-docs.txt
    fi

    print_success "Dependencies installed successfully"
}

# Start the MkDocs server
start_server() {
    print_status "Starting MkDocs development server..."
    print_status "Documentation will be available at: http://127.0.0.1:8000"
    print_status "Press Ctrl+C to stop the server"
    echo ""

    # Start MkDocs with live reloading
    # Start MkDocs with live reloading
    local cmd_prefix=""
    if [ "$PACKAGE_MANAGER" = "uv" ]; then
        cmd_prefix="uv run "
    fi
    ${cmd_prefix}mkdocs serve --dev-addr=127.0.0.1:8000
}

# Cleanup function
cleanup() {
    echo ""
    print_status "Server process terminated."
    print_success "Documentation server stopped"
}

# Set up cleanup on exit
trap cleanup EXIT

# Setup checks function to avoid duplication
setup_checks() {
    print_header
    print_status "Setting up AP2 local documentation server..."
    echo ""
    check_directory
    check_python
    check_package_manager
}

# Main execution
main() {
    setup_checks

    # Ask user if they want to install/update dependencies
    echo ""
    read -p "Install/update documentation dependencies? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        install_dependencies
    else
        print_warning "Skipping dependency installation"
        print_status "If you encounter issues, run: $PACKAGE_MANAGER install -r requirements-docs.txt"
    fi

    echo ""
    print_success "Setup complete!"
    echo ""
    start_server
}

# Handle script arguments
case "${1:-}" in
    --help|-h)
        echo "AP2 Local Documentation Server Helper"
        echo ""
        echo "Usage: $0 [options]"
        echo ""
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --install-only Install dependencies only, don't start server"
        echo ""
        echo "This script will:"
        echo "  1. Check that you're in the correct directory"
        echo "  2. Verify Python 3 is installed"
        echo "  3. Install MkDocs documentation dependencies"
        echo "  4. Start the local documentation server on http://127.0.0.1:8000"
        echo ""
        echo "The documentation server supports live reloading - changes to documentation"
        echo "files will automatically refresh in your browser."
        exit 0
        ;;
    --install-only)
        setup_checks
        install_dependencies
        print_success "Dependencies installed. Run '$0' to start the server."
        exit 0
        ;;
    "")
        main
        ;;
    *)
        print_error "Unknown option: $1"
        print_status "Use --help for usage information"
        exit 1
        ;;
esac
