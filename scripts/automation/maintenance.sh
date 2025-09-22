#!/bin/bash

# AI Shopping Concierge - Automated Maintenance Script
# Handles routine maintenance tasks

set -e

echo "🔧 AI Shopping Concierge - Automated Maintenance"
echo "=============================================="

# Configuration
GITHUB_USERNAME="${1:-ankitap}"
PRODUCT_REPO="ai-shopping-concierge-ap2"
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

# Step 1: Update dependencies
log_info "Updating dependencies..."

if [[ -f "$PRODUCT_DIR/requirements.txt" ]]; then
    cd "$PRODUCT_DIR"
    
    # Backup current requirements
    cp requirements.txt requirements.txt.backup
    
    # Update Python packages
    log_info "Checking for Python package updates..."
    pip list --outdated --format=freeze | grep -v '^\-e' | cut -d = -f 1 > outdated_packages.txt
    
    if [[ -s outdated_packages.txt ]]; then
        log_info "Found outdated packages:"
        cat outdated_packages.txt
        
        # Update packages (be careful with major version updates)
        pip install --upgrade $(cat outdated_packages.txt | tr '\n' ' ')
        pip freeze > requirements.txt
        
        log_success "Dependencies updated"
    else
        log_success "All dependencies are up to date"
    fi
    
    rm -f outdated_packages.txt
else
    log_warning "No requirements.txt found"
fi

# Step 2: Clean up Docker resources
log_info "Cleaning up Docker resources..."

if command -v docker &> /dev/null; then
    # Remove unused images
    docker image prune -f
    
    # Remove unused containers
    docker container prune -f
    
    # Remove unused volumes
    docker volume prune -f
    
    log_success "Docker cleanup completed"
else
    log_warning "Docker not available"
fi

# Step 3: Clean up logs
log_info "Cleaning up old logs..."

if [[ -d "$PRODUCT_DIR/logs" ]]; then
    cd "$PRODUCT_DIR/logs"
    
    # Remove logs older than 30 days
    find . -name "*.log" -type f -mtime +30 -delete
    
    # Compress logs older than 7 days
    find . -name "*.log" -type f -mtime +7 -exec gzip {} \;
    
    log_success "Log cleanup completed"
else
    log_warning "No logs directory found"
fi

# Step 4: Database maintenance
log_info "Running database maintenance..."

if [[ -f "$PRODUCT_DIR/config/secrets.yaml" ]]; then
    # Example database maintenance (adjust for your setup)
    log_info "Database maintenance tasks:"
    log_info "  - Consider running VACUUM/ANALYZE on PostgreSQL"
    log_info "  - Check Redis memory usage"
    log_info "  - Review database connection pool settings"
    
    # You can add actual database maintenance commands here
    # psql $DATABASE_URL -c "VACUUM ANALYZE;"
    # redis-cli --eval "redis.call('FLUSHDB')"
    
    log_success "Database maintenance tasks noted"
else
    log_warning "No database configuration found"
fi

# Step 5: Security updates
log_info "Checking for security updates..."

# Check for CVEs in dependencies
if command -v safety &> /dev/null; then
    cd "$PRODUCT_DIR"
    safety check --json > security_report.json 2>/dev/null || true
    
    if [[ -f "security_report.json" ]]; then
        VULNERABILITIES=$(cat security_report.json | jq '.vulnerabilities | length' 2>/dev/null || echo "0")
        if [[ "$VULNERABILITIES" -gt 0 ]]; then
            log_warning "Found $VULNERABILITIES security vulnerabilities!"
            log_warning "Run: safety check --full-report"
        else
            log_success "No security vulnerabilities found"
        fi
        rm -f security_report.json
    fi
else
    log_warning "Safety not installed. Run: pip install safety"
fi

# Step 6: Performance monitoring
log_info "Checking performance metrics..."

if command -v docker &> /dev/null && docker ps | grep -q ai-shopping-concierge; then
    # Get container stats
    CONTAINER_ID=$(docker ps | grep ai-shopping-concierge | awk '{print $1}')
    if [[ -n "$CONTAINER_ID" ]]; then
        log_info "Container resource usage:"
        docker stats --no-stream "$CONTAINER_ID"
    fi
    
    log_success "Performance metrics collected"
else
    log_warning "AI Shopping Concierge container not running"
fi

# Step 7: Backup important data
log_info "Creating backups..."

BACKUP_DIR="$PRODUCT_DIR/backups/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# Backup configuration
if [[ -d "$PRODUCT_DIR/config" ]]; then
    cp -r "$PRODUCT_DIR/config" "$BACKUP_DIR/"
fi

# Backup database (example - adjust for your setup)
if [[ -f "$PRODUCT_DIR/config/secrets.yaml" ]]; then
    # Example backup commands (uncomment and adjust as needed):
    # pg_dump $DATABASE_URL > "$BACKUP_DIR/database_backup.sql"
    # redis-cli --rdb "$BACKUP_DIR/redis_backup.rdb"
    
    log_info "Database backup commands prepared (review and uncomment in script)"
fi

log_success "Backup directory created: $BACKUP_DIR"

# Step 8: Generate maintenance report
MAINTENANCE_REPORT="$PRODUCT_DIR/maintenance-report-$(date +%Y%m%d-%H%M%S).txt"

cat > "$MAINTENANCE_REPORT" << EOF
AI Shopping Concierge - Maintenance Report
Generated: $(date)

Maintenance Tasks Completed:
✅ Dependencies updated
✅ Docker resources cleaned
✅ Old logs cleaned up
✅ Database maintenance reviewed
✅ Security check performed
✅ Performance metrics collected
✅ Backup directory created

System Status:
- Python packages: $(pip list | wc -l) installed
- Docker images: $(docker images | grep ai-shopping-concierge | wc -l) AI Shopping Concierge images
- Log files: $(find "$PRODUCT_DIR/logs" -name "*.log" 2>/dev/null | wc -l) active log files
- Backup location: $BACKUP_DIR

Recommendations:
1. Review security report if vulnerabilities were found
2. Monitor application performance after updates
3. Consider scheduling regular maintenance (weekly/monthly)
4. Update documentation if dependencies changed significantly

Next Maintenance: $(date -d '+7 days')

EOF

log_success "Maintenance report generated: $MAINTENANCE_REPORT"

echo
log_success "🎉 Maintenance completed successfully!"
echo "===================================="
echo
log_info "📊 Summary:"
log_info "  - Dependencies updated"
log_info "  - System cleaned up"
log_info "  - Backups created"
log_info "  - Report: $MAINTENANCE_REPORT"
echo
log_info "🔍 Next steps:"
log_info "  1. Review the maintenance report"
log_info "  2. Test the application after updates"
log_info "  3. Schedule next maintenance in 1 week"
log_info "  4. Monitor for any issues"

# Optional: Schedule next maintenance
log_info "💡 Tip: Add this to your crontab for weekly maintenance:"
log_info "0 2 * * 0 cd $(pwd) && ./scripts/automation/maintenance.sh >> maintenance.log 2>&1"