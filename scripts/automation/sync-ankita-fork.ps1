# Sync AnkitaParakh/AP2-shopping-concierge fork with upstream AP2
# PowerShell version for Windows users

param(
    [switch]$Force,
    [string]$Branch = "",
    [switch]$Help
)

# Configuration
$GITHUB_USERNAME = "AnkitaParakh"
$PRODUCT_REPO = "AP2-shopping-concierge"
$UPSTREAM_REPO = "https://github.com/google-agentic-commerce/AP2.git"
$FORK_REPO = "https://github.com/$GITHUB_USERNAME/$PRODUCT_REPO.git"

# Color output functions
function Write-Info { 
    param($Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue 
}

function Write-Success { 
    param($Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green 
}

function Write-Warning { 
    param($Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow 
}

function Write-Error { 
    param($Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red 
}

# Help function
function Show-Help {
    Write-Host @"
Sync AnkitaParakh/AP2-shopping-concierge fork with upstream AP2

Usage: .\sync-ankita-fork.ps1 [OPTIONS]

Options:
    -Force          Force sync even if working directory is not clean
    -Branch <name>  Sync only specific branch
    -Help           Show this help message

Examples:
    .\sync-ankita-fork.ps1                    # Sync all branches
    .\sync-ankita-fork.ps1 -Branch main       # Sync only main branch
    .\sync-ankita-fork.ps1 -Force             # Force sync with uncommitted changes

"@
}

# Check if we're in the right directory
function Test-GitRepository {
    if (-not (Test-Path "pyproject.toml") -or -not (Test-Path ".git")) {
        Write-Error "Not in AP2 repository root. Please run from AP2 directory."
        exit 1
    }
}

# Check git status
function Test-GitStatus {
    $status = git status --porcelain 2>$null
    if ($status -and -not $Force) {
        Write-Error "Working directory is not clean. Please commit or stash your changes, or use -Force."
        git status --short
        exit 1
    }
}

# Sync a specific branch
function Sync-Branch {
    param(
        [string]$BranchName,
        [bool]$CreateIfMissing = $false
    )
    
    Write-Info "Syncing branch: $BranchName"
    
    # Check if branch exists locally
    $branchExists = git show-ref --verify --quiet "refs/heads/$BranchName" 2>$null
    $LASTEXITCODE = 0  # Reset exit code
    
    if ($branchExists) {
        Write-Info "Switching to existing branch: $BranchName"
        git checkout $BranchName
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to checkout branch $BranchName"
            return $false
        }
    } elseif ($CreateIfMissing) {
        Write-Info "Creating new branch: $BranchName"
        git checkout -b $BranchName
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to create branch $BranchName"
            return $false
        }
    } else {
        Write-Warning "Branch $BranchName doesn't exist locally. Skipping..."
        return $true
    }
    
    # Fetch latest changes from upstream
    Write-Info "Fetching from upstream..."
    git fetch upstream $BranchName
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Failed to fetch from upstream. Continuing anyway..."
    }
    
    # Check if upstream branch exists
    $upstreamExists = git show-ref --verify --quiet "refs/remotes/upstream/$BranchName" 2>$null
    $LASTEXITCODE = 0  # Reset exit code
    
    if (-not $upstreamExists) {
        Write-Warning "Upstream branch $BranchName doesn't exist. Skipping merge..."
        return $true
    }
    
    # Merge upstream changes
    Write-Info "Merging upstream/$BranchName into $BranchName"
    git merge "upstream/$BranchName" --no-edit
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Merge conflicts detected. Please resolve manually."
        Write-Info "After resolving conflicts, run:"
        Write-Info "  git add ."
        Write-Info "  git commit"
        Write-Info "  git push origin $BranchName"
        return $false
    }
    
    Write-Success "Successfully merged upstream changes"
    
    # Push to fork
    Write-Info "Pushing to fork..."
    git push origin $BranchName
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Failed to push to fork. You may need to force push or resolve conflicts."
        return $false
    }
    
    Write-Success "Successfully pushed to fork"
    return $true
}

# Check for new upstream branches
function Test-NewBranches {
    Write-Info "Checking for new upstream branches..."
    
    # Fetch all upstream branches
    git fetch upstream
    
    # Get list of upstream branches
    $upstreamBranches = git branch -r | Where-Object { $_ -match 'upstream/' } | ForEach-Object { $_.Replace('upstream/', '').Trim() } | Where-Object { $_ -ne 'HEAD' }
    $localBranches = git branch | ForEach-Object { $_.Replace('*', '').Trim() }
    
    foreach ($branch in $upstreamBranches) {
        if ($branch -notin $localBranches) {
            Write-Info "New upstream branch found: $branch"
            $response = Read-Host "Do you want to create and sync this branch? (y/n)"
            if ($response -eq 'y' -or $response -eq 'Y') {
                Sync-Branch $branch $true
            }
        }
    }
}

# Show sync summary
function Show-Summary {
    Write-Host ""
    Write-Host "Sync Summary" -ForegroundColor Cyan
    Write-Host "===============" -ForegroundColor Cyan
    
    # Show last commit from upstream
    Write-Info "Latest upstream commit:"
    $upstreamCommit = git log upstream/main --oneline -1 2>$null
    if (-not $upstreamCommit) {
        $upstreamCommit = git log upstream/master --oneline -1 2>$null
    }
    if ($upstreamCommit) {
        Write-Host "  $upstreamCommit"
    } else {
        Write-Host "  No upstream commits found"
    }
    
    # Show current branch status
    Write-Host ""
    Write-Info "Current branch status:"
    $currentBranch = git branch --show-current
    
    $behindCount = 0
    $aheadCount = 0
    
    try {
        $behindCount = git rev-list --count "HEAD..upstream/$currentBranch" 2>$null
        $aheadCount = git rev-list --count "upstream/$currentBranch..HEAD" 2>$null
    } catch {
        # Ignore errors
    }
    
    if ($behindCount -eq 0 -and $aheadCount -eq 0) {
        Write-Success "Your fork is up-to-date with upstream"
    } elseif ($behindCount -gt 0) {
        Write-Warning "Your fork is $behindCount commits behind upstream"
    } elseif ($aheadCount -gt 0) {
        Write-Info "Your fork is $aheadCount commits ahead of upstream"
    }
    
    Write-Host ""
    Write-Info "Repository URLs:"
    Write-Info "  Upstream: https://github.com/google-agentic-commerce/AP2"
    Write-Info "  Your Fork: https://github.com/$GITHUB_USERNAME/$PRODUCT_REPO"
    
    Write-Host ""
    Write-Info "Next steps:"
    Write-Info "  - Review changes: git log --oneline upstream/main..HEAD"
    Write-Info "  - Check status: git status"
    Write-Info "  - View differences: git diff upstream/main"
}

# Main execution
function Main {
    if ($Help) {
        Show-Help
        return
    }
    
    Write-Host "Starting AP2 fork sync process..." -ForegroundColor Cyan
    Write-Host ""
    
    # Display current status
    Write-Host "AP2 Fork Sync Status" -ForegroundColor Cyan
    Write-Host "=======================" -ForegroundColor Cyan
    Write-Host "Upstream: $UPSTREAM_REPO"
    Write-Host "Fork: $FORK_REPO"
    Write-Host "Current directory: $(Get-Location)"
    $currentBranch = git branch --show-current 2>$null
    Write-Host "Current branch: $currentBranch"
    Write-Host ""
    
    # Check if we're in the right directory
    Test-GitRepository
    
    # Verify git remotes are set up correctly
    Write-Info "Verifying git remotes..."
    
    $upstreamUrl = git remote get-url upstream 2>$null
    $originUrl = git remote get-url origin 2>$null
    
    if (-not $upstreamUrl) {
        Write-Info "Upstream remote not configured. Setting up..."
        git remote add upstream $UPSTREAM_REPO
    } elseif ($upstreamUrl -ne $UPSTREAM_REPO) {
        Write-Warning "Upstream URL mismatch. Updating..."
        git remote set-url upstream $UPSTREAM_REPO
    }
    
    if (-not $originUrl) {
        Write-Info "Origin remote not configured. Setting up..."
        git remote add origin $FORK_REPO
    } elseif ($originUrl -ne $FORK_REPO) {
        Write-Warning "Origin URL mismatch. Updating..."
        git remote set-url origin $FORK_REPO
    }
    
    Write-Success "Git remotes configured correctly"
    
    # Check working directory status
    Test-GitStatus
    
    # Store current branch
    $originalBranch = git branch --show-current
    
    # If specific branch requested, sync only that branch
    if ($Branch) {
        $success = Sync-Branch $Branch $true
        if (-not $success) {
            exit 1
        }
    } else {
        # Sync main/master branch
        $mainExists = git show-ref --verify --quiet "refs/remotes/upstream/main" 2>$null
        $masterExists = git show-ref --verify --quiet "refs/remotes/upstream/master" 2>$null
        
        if ($mainExists) {
            $success = Sync-Branch "main" $true
        } elseif ($masterExists) {
            $success = Sync-Branch "master" $true
        } else {
            Write-Error "No main or master branch found in upstream"
            exit 1
        }
        
        if (-not $success) {
            exit 1
        }
        
        # Check for and sync other important branches
        $importantBranches = @("develop", "development", "staging", "production")
        foreach ($branch in $importantBranches) {
            $branchExists = git show-ref --verify --quiet "refs/remotes/upstream/$branch" 2>$null
            $LASTEXITCODE = 0  # Reset exit code
            
            if ($branchExists) {
                Write-Info "Found upstream branch: $branch"
                $response = Read-Host "Sync $branch branch? (y/n)"
                if ($response -eq 'y' -or $response -eq 'Y') {
                    Sync-Branch $branch $true
                }
            }
        }
        
        # Check for new branches
        Test-NewBranches
    }
    
    # Return to original branch if it still exists
    if ($originalBranch) {
        $branchExists = git show-ref --verify --quiet "refs/heads/$originalBranch" 2>$null
        $LASTEXITCODE = 0  # Reset exit code
        
        if ($branchExists) {
            git checkout $originalBranch
        }
    }
    
    # Show summary
    Show-Summary
    
    Write-Success "Fork sync completed successfully!"
}

# Run main function
Main