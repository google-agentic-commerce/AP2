#!/bin/bash

# Sync AnkitaParakh/AP2-shopping-concierge fork with upstream AP2
# This script keeps your fork up-to-date with the latest changes from Google's AP2 repo

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
GITHUB_USERNAME="AnkitaParakh"
PRODUCT_REPO="AP2-shopping-concierge"
UPSTREAM_REPO="https://github.com/google-agentic-commerce/AP2.git"
FORK_REPO="https://github.com/$GITHUB_USERNAME/$PRODUCT_REPO.git"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if we're in the right directory
if [[ ! -f "$PROJECT_DIR/pyproject.toml" ]] || [[ ! -d "$PROJECT_DIR/.git" ]]; then
    log_error "Not in AP2 repository root. Please run from AP2 directory."
    exit 1
fi

cd "$PROJECT_DIR"

# Display current status
echo "🔄 AP2 Fork Sync Status"
echo "======================="
echo "Upstream: $UPSTREAM_REPO"
echo "Fork: $FORK_REPO"
echo "Current directory: $(pwd)"
echo "Current branch: $(git branch --show-current)"
echo ""

# Function to check git status
check_git_status() {
    if [[ -n "$(git status --porcelain)" ]]; then
        log_error "Working directory is not clean. Please commit or stash your changes."
        git status --short
        exit 1
    fi
}

# Function to sync a specific branch
sync_branch() {
    local branch_name="$1"
    local create_if_missing="${2:-false}"
    
    log_info "Syncing branch: $branch_name"
    
    # Check if branch exists locally
    if git show-ref --verify --quiet "refs/heads/$branch_name"; then
        log_info "Switching to existing branch: $branch_name"
        git checkout "$branch_name"
    elif [[ "$create_if_missing" == "true" ]]; then
        log_info "Creating new branch: $branch_name"
        git checkout -b "$branch_name"
    else
        log_warning "Branch $branch_name doesn't exist locally. Skipping..."
        return 0
    fi
    
    # Fetch latest changes from upstream
    log_info "Fetching from upstream..."
    git fetch upstream "$branch_name"
    
    # Check if upstream branch exists
    if ! git show-ref --verify --quiet "refs/remotes/upstream/$branch_name"; then
        log_warning "Upstream branch $branch_name doesn't exist. Skipping merge..."
        return 0
    fi
    
    # Merge upstream changes
    log_info "Merging upstream/$branch_name into $branch_name"
    if git merge "upstream/$branch_name" --no-edit; then
        log_success "Successfully merged upstream changes"
        
        # Push to fork
        log_info "Pushing to fork..."
        if git push origin "$branch_name"; then
            log_success "Successfully pushed to fork"
        else
            log_warning "Failed to push to fork. You may need to force push or resolve conflicts."
        fi
    else
        log_error "Merge conflicts detected. Please resolve manually."
        log_info "After resolving conflicts, run:"
        log_info "  git add ."
        log_info "  git commit"
        log_info "  git push origin $branch_name"
        exit 1
    fi
}

# Function to check for new upstream branches
check_new_branches() {
    log_info "Checking for new upstream branches..."
    
    # Fetch all upstream branches
    git fetch upstream
    
    # Get list of upstream branches
    local upstream_branches=$(git branch -r | grep 'upstream/' | sed 's/upstream\///' | grep -v 'HEAD' | tr -d ' ')
    local local_branches=$(git branch | sed 's/[* ]//g')
    
    for branch in $upstream_branches; do
        if ! echo "$local_branches" | grep -q "^$branch$"; then
            log_info "New upstream branch found: $branch"
            read -p "Do you want to create and sync this branch? (y/n): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                sync_branch "$branch" true
            fi
        fi
    done
}

# Function to show sync summary
show_summary() {
    echo ""
    echo "📊 Sync Summary"
    echo "==============="
    
    # Show last commit from upstream
    log_info "Latest upstream commit:"
    git log upstream/main --oneline -1 2>/dev/null || git log upstream/master --oneline -1 2>/dev/null || echo "  No upstream commits found"
    
    # Show current branch status
    echo ""
    log_info "Current branch status:"
    local current_branch=$(git branch --show-current)
    local behind_count=$(git rev-list --count HEAD..upstream/$current_branch 2>/dev/null || echo "0")
    local ahead_count=$(git rev-list --count upstream/$current_branch..HEAD 2>/dev/null || echo "0")
    
    if [[ "$behind_count" -eq 0 && "$ahead_count" -eq 0 ]]; then
        log_success "Your fork is up-to-date with upstream"
    elif [[ "$behind_count" -gt 0 ]]; then
        log_warning "Your fork is $behind_count commits behind upstream"
    elif [[ "$ahead_count" -gt 0 ]]; then
        log_info "Your fork is $ahead_count commits ahead of upstream"
    fi
    
    echo ""
    log_info "Repository URLs:"
    log_info "  Upstream: https://github.com/google-agentic-commerce/AP2"
    log_info "  Your Fork: https://github.com/$GITHUB_USERNAME/$PRODUCT_REPO"
    
    echo ""
    log_info "Next steps:"
    log_info "  - Review changes: git log --oneline upstream/main..HEAD"
    log_info "  - Check status: git status"
    log_info "  - View differences: git diff upstream/main"
}

# Main execution
main() {
    echo "🚀 Starting AP2 fork sync process..."
    echo ""
    
    # Verify git remotes are set up correctly
    log_info "Verifying git remotes..."
    if ! git remote get-url upstream &>/dev/null; then
        log_error "Upstream remote not configured. Setting up..."
        git remote add upstream "$UPSTREAM_REPO"
    fi
    
    if ! git remote get-url origin &>/dev/null; then
        log_error "Origin remote not configured. Setting up..."
        git remote add origin "$FORK_REPO"
    fi
    
    # Verify remotes point to correct repositories
    local upstream_url=$(git remote get-url upstream)
    local origin_url=$(git remote get-url origin)
    
    if [[ "$upstream_url" != "$UPSTREAM_REPO" ]]; then
        log_warning "Upstream URL mismatch. Updating..."
        git remote set-url upstream "$UPSTREAM_REPO"
    fi
    
    if [[ "$origin_url" != "$FORK_REPO" ]]; then
        log_warning "Origin URL mismatch. Updating..."
        git remote set-url origin "$FORK_REPO"
    fi
    
    log_success "Git remotes configured correctly"
    
    # Check working directory status
    check_git_status
    
    # Store current branch
    local original_branch=$(git branch --show-current)
    
    # Sync main/master branch
    if git show-ref --verify --quiet "refs/remotes/upstream/main"; then
        sync_branch "main" true
    elif git show-ref --verify --quiet "refs/remotes/upstream/master"; then
        sync_branch "master" true
    else
        log_error "No main or master branch found in upstream"
        exit 1
    fi
    
    # Check for and sync other important branches
    for branch in develop development staging production; do
        if git show-ref --verify --quiet "refs/remotes/upstream/$branch"; then
            log_info "Found upstream branch: $branch"
            read -p "Sync $branch branch? (y/n): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                sync_branch "$branch" true
            fi
        fi
    done
    
    # Check for new branches
    check_new_branches
    
    # Return to original branch if it still exists
    if [[ -n "$original_branch" ]] && git show-ref --verify --quiet "refs/heads/$original_branch"; then
        git checkout "$original_branch"
    fi
    
    # Show summary
    show_summary
    
    log_success "Fork sync completed successfully! 🎉"
}

# Run main function
main "$@"