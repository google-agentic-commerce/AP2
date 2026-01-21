#!/bin/bash

# AI Shopping Concierge - Upstream Sync Script
# Automatically syncs changes from Google's AP2 repository

set -e

echo "🔄 AI Shopping Concierge - Upstream Sync"
echo "======================================="

# Configuration
GITHUB_USERNAME="${1:-ankitap}"
PRODUCT_REPO="ai-shopping-concierge-ap2"
CURRENT_DIR="$(pwd)"
PRODUCT_DIR="../$PRODUCT_REPO"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Verify we're in the AP2 directory
if [[ ! -f "pyproject.toml" ]] || [[ ! -d ".git" ]]; then
    log_error "Please run this script from the AP2 repository root directory"
    exit 1
fi

log_success "Running from AP2 repository"

# Step 1: Fetch latest changes from upstream
log_info "Fetching latest changes from upstream Google AP2 repository..."
git fetch upstream

# Check if there are new changes
UPSTREAM_COMMITS=$(git rev-list HEAD..upstream/main --count)
if [[ "$UPSTREAM_COMMITS" -eq 0 ]]; then
    log_success "Already up to date with upstream"
else
    log_info "Found $UPSTREAM_COMMITS new commits from upstream"
fi

# Step 2: Show what changed
if [[ "$UPSTREAM_COMMITS" -gt 0 ]]; then
    echo
    log_info "Recent changes from Google AP2:"
    echo "================================"
    git log --oneline --graph HEAD..upstream/main | head -10
    echo
    
    # Ask for confirmation
    read -p "🤔 Do you want to merge these changes? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_warning "Sync cancelled by user"
        exit 0
    fi
fi

# Step 3: Merge upstream changes
if [[ "$UPSTREAM_COMMITS" -gt 0 ]]; then
    log_info "Merging upstream changes..."
    
    # Switch to main branch
    git checkout main
    
    # Merge upstream changes
    if git merge upstream/main --no-edit; then
        log_success "Successfully merged upstream changes"
    else
        log_error "Merge conflicts detected! Please resolve manually and run:"
        log_error "  git add ."
        log_error "  git commit"
        log_error "  ./scripts/automation/sync-upstream.sh"
        exit 1
    fi
    
    # Push to your fork
    log_info "Pushing changes to your fork..."
    git push origin main
    log_success "Fork updated successfully"
fi

# Step 4: Update product repository submodule
if [[ -d "$PRODUCT_DIR" ]]; then
    log_info "Updating product repository submodule..."
    cd "$PRODUCT_DIR"
    
    # Update the AP2 submodule
    if [[ -d "ap2-core" ]]; then
        git submodule update --remote ap2-core
        
        # Check if submodule has changes
        if [[ -n "$(git status --porcelain)" ]]; then
            log_info "AP2 submodule has updates, committing..."
            git add ap2-core
            git commit -m "Update AP2 core to latest version

$(git -C ap2-core log --oneline HEAD~$UPSTREAM_COMMITS..HEAD)"
            
            git push origin main
            log_success "Product repository updated with latest AP2 core"
        else
            log_success "Product repository submodule already up to date"
        fi
    else
        log_warning "AP2 submodule not found in product repository"
    fi
    
    cd "$CURRENT_DIR"
else
    log_warning "Product repository not found at: $PRODUCT_DIR"
fi

# Step 5: Check for compatibility issues
log_info "Checking for compatibility issues..."

# List of critical files to monitor for breaking changes
CRITICAL_FILES=(
    "src/ap2/types/__init__.py"
    "src/ap2/types/payment_request.py"
    "src/ap2/types/mandate.py"
    "src/ap2/types/contact_picker.py"
)

BREAKING_CHANGES=false
for file in "${CRITICAL_FILES[@]}"; do
    if git diff HEAD~$UPSTREAM_COMMITS..HEAD --quiet -- "$file" 2>/dev/null; then
        continue
    else
        if [[ -f "$file" ]]; then
            log_warning "Breaking change detected in: $file"
            BREAKING_CHANGES=true
        fi
    fi
done

if [[ "$BREAKING_CHANGES" == "true" ]]; then
    echo
    log_warning "⚠️  BREAKING CHANGES DETECTED!"
    log_warning "The following actions are recommended:"
    log_warning "1. Review changes in critical AP2 files"
    log_warning "2. Update your AI Shopping Concierge code accordingly"
    log_warning "3. Run tests to ensure compatibility"
    log_warning "4. Update documentation if needed"
    echo
    
    if [[ -d "$PRODUCT_DIR" ]]; then
        log_info "💡 Quick compatibility check:"
        log_info "cd $PRODUCT_DIR && python -m pytest tests/"
    fi
else
    log_success "No breaking changes detected"
fi

# Step 6: Generate sync report
SYNC_REPORT="sync-report-$(date +%Y%m%d-%H%M%S).txt"
cat > "$SYNC_REPORT" << EOF
AI Shopping Concierge - Upstream Sync Report
Generated: $(date)

Upstream Commits Merged: $UPSTREAM_COMMITS
Breaking Changes: $BREAKING_CHANGES

Recent Changes:
$(git log --oneline HEAD~$UPSTREAM_COMMITS..HEAD)

Critical Files Checked:
$(printf '%s\n' "${CRITICAL_FILES[@]}")

Recommendations:
- Review merged changes for compatibility
- Run full test suite: python -m pytest tests/
- Update documentation if AP2 APIs changed
- Deploy to staging for testing before production

EOF

log_success "Sync report generated: $SYNC_REPORT"

echo
log_success "🎉 Upstream sync completed successfully!"
echo "=================================="
echo
if [[ "$UPSTREAM_COMMITS" -gt 0 ]]; then
    log_info "📊 Summary:"
    log_info "  - Merged $UPSTREAM_COMMITS commits from Google AP2"
    log_info "  - Updated your fork: https://github.com/$GITHUB_USERNAME/AP2"
    if [[ -d "$PRODUCT_DIR" ]]; then
        log_info "  - Updated product repository submodule"
    fi
    log_info "  - Generated sync report: $SYNC_REPORT"
    echo
    log_info "🔍 Next steps:"
    log_info "  1. Review the sync report"
    log_info "  2. Test your AI Shopping Concierge"
    log_info "  3. Deploy updates if everything looks good"
else
    log_info "🚀 Everything is up to date!"
fi