# Fork Sync Configuration and Setup Guide
# For <your-github-username>/AP2-shopping-concierge

## 🔄 Fork Sync Setup Complete!

Your fork is now properly configured to stay in sync with the upstream AP2 repository. Here's what has been set up:

### Git Remote Configuration
```
origin    → https://github.com/AnkitaParakh/AP2-shopping-concierge.git (your fork)
upstream  → https://github.com/google-agentic-commerce/AP2.git (Google's repo)
```

### Branch Structure
- `main` - Synced with upstream/main (AP2 core protocol)
- `ai-shopping-concierge-dev` - Your AI Shopping Concierge features

## 🚀 How to Sync with Upstream

### Option 1: PowerShell (Windows)
```powershell
# Sync all branches
.\scripts\automation\sync-ankita-fork.ps1

# Sync specific branch only
.\scripts\automation\sync-ankita-fork.ps1 -Branch main

# Force sync (even with uncommitted changes)
.\scripts\automation\sync-ankita-fork.ps1 -Force
```

### Option 2: Bash (Linux/Mac/WSL)
```bash
# Make script executable (first time only)
chmod +x scripts/automation/sync-ankita-fork.sh

# Sync all branches
./scripts/automation/sync-ankita-fork.sh
```

### Option 3: Manual Sync
```bash
# Fetch latest upstream changes
git fetch upstream

# Switch to main branch and sync
git checkout main
git merge upstream/main
git push origin main

# Switch back to your development branch
git checkout ai-shopping-concierge-dev
```

## ⏰ Automated Sync (Recommended)

### Windows Task Scheduler
1. Open Task Scheduler (taskschd.msc)
2. Create Basic Task:
   - Name: "Sync AP2 Fork"
   - Trigger: Daily at 9:00 AM
   - Action: Start a program
   - Program: `powershell.exe`
   - Arguments: `-ExecutionPolicy Bypass -File "C:\AP2\scripts\automation\sync-ankita-fork.ps1"`
   - Start in: `C:\AP2`

### GitHub Actions (Automated)
Create `.github/workflows/sync-upstream.yml` in your fork:

```yaml
name: Sync Fork with Upstream

on:
  schedule:
    - cron: '0 9 * * *'  # Daily at 9 AM UTC
  workflow_dispatch:     # Manual trigger

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          fetch-depth: 0
      
      - name: Sync upstream
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git remote add upstream https://github.com/google-agentic-commerce/AP2.git
          git fetch upstream
          git checkout main
          git merge upstream/main --no-edit
          git push origin main
```

## 🔍 Monitor Sync Status

### Check if your fork is behind upstream:
```bash
# Check how many commits behind
git fetch upstream
git rev-list --count HEAD..upstream/main

# View what changes are available
git log --oneline HEAD..upstream/main
```

### Check sync history:
```bash
# View recent commits
git log --oneline -10

# View merge commits (sync points)
git log --merges --oneline -5
```

## 🛠️ Development Workflow

### Working on AI Shopping Concierge features:
```bash
# 1. Start from your development branch
git checkout ai-shopping-concierge-dev

# 2. Create feature branch
git checkout -b feature/new-payment-method

# 3. Make changes and commit
git add .
git commit -m "feat: Add new payment method support"

# 4. Push to your fork
git push origin feature/new-payment-method

# 5. Create PR in your fork: feature/new-payment-method → ai-shopping-concierge-dev
```

### When contributing back to AP2 protocol:
```bash
# 1. Start from synced main branch
git checkout main
git pull upstream main

# 2. Create protocol improvement branch
git checkout -b protocol/improve-security

# 3. Make changes and commit
git add .
git commit -m "feat: Enhance AP2 security validation"

# 4. Push to your fork
git push origin protocol/improve-security

# 5. Create PR to upstream: your-fork/protocol/improve-security → google-agentic-commerce/AP2:main
```

## 📋 Sync Checklist

### Daily (Automated):
- ✅ Fetch upstream changes
- ✅ Merge to main branch
- ✅ Push to your fork
- ✅ Check for conflicts

### Weekly (Manual Review):
- [ ] Review upstream changelog
- [ ] Test compatibility with your features
- [ ] Update dependencies if needed
- [ ] Merge main into your development branches

### Monthly (Maintenance):
- [ ] Clean up old feature branches
- [ ] Review and update documentation
- [ ] Performance testing
- [ ] Security audit

## 🚨 Troubleshooting

### Merge Conflicts:
```bash
# If sync fails due to conflicts:
git status                    # See conflicted files
# Edit files to resolve conflicts
git add .                     # Stage resolved files
git commit                    # Complete the merge
git push origin main          # Push resolved version
```

### Reset to Upstream (Nuclear Option):
```bash
# WARNING: This will lose your changes on main branch
git fetch upstream
git checkout main
git reset --hard upstream/main
git push --force-with-lease origin main
```

### Fork is Far Behind:
```bash
# If your fork is many commits behind:
git fetch upstream
git rebase upstream/main      # Replay your commits on top of upstream
git push --force-with-lease origin main
```

## 📞 Support

- **Sync Issues**: Check the troubleshooting section above
- **Upstream Changes**: Monitor [AP2 Releases](https://github.com/google-agentic-commerce/AP2/releases)
- **Feature Development**: Use the development workflow above

---

**Your AI Shopping Concierge fork is now fully configured for automatic upstream synchronization! 🎉**

The sync will keep your protocol foundation up-to-date while preserving your product innovations in separate branches.