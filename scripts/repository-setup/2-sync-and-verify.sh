#!/bin/bash

# AI Shopping Concierge - Sync and Verify Script
# Run this after completing the manual GitHub steps

set -e

echo "🔄 AI Shopping Concierge - Sync and Verify"
echo "=========================================="

# Configuration
GITHUB_USERNAME="${1:-ankitap}"
PRODUCT_REPO="ai-shopping-concierge-ap2"

echo "📋 Verifying setup for: $GITHUB_USERNAME"
echo

# Step 1: Fetch from upstream
echo "🔄 Fetching latest changes from upstream..."
git fetch upstream

# Step 2: Create and switch to development branch
echo "🌿 Creating development branch..."
if git show-ref --verify --quiet refs/heads/ai-shopping-concierge; then
    echo "   ⚠️  Branch 'ai-shopping-concierge' already exists, switching..."
    git checkout ai-shopping-concierge
else
    echo "   ➕ Creating new branch 'ai-shopping-concierge'..."
    git checkout -b ai-shopping-concierge upstream/main
fi

# Step 3: Test connection to your fork
echo "🧪 Testing connection to your fork..."
if git ls-remote origin &> /dev/null; then
    echo "✅ Successfully connected to your fork"
else
    echo "❌ Cannot connect to your fork. Please check:"
    echo "   - Your fork exists at: https://github.com/$GITHUB_USERNAME/AP2"
    echo "   - Your authentication is set up (SSH keys or token)"
    echo "   - Your internet connection"
    exit 1
fi

# Step 4: Push development branch to your fork
echo "⬆️  Pushing development branch to your fork..."
git push -u origin ai-shopping-concierge

# Step 5: Clone your product repository
echo "📦 Setting up your product repository..."
PRODUCT_DIR="../$PRODUCT_REPO"

if [[ -d "$PRODUCT_DIR" ]]; then
    echo "   ⚠️  Product repository directory already exists"
    cd "$PRODUCT_DIR"
    git pull origin main
else
    echo "   📥 Cloning your product repository..."
    cd ..
    git clone "https://github.com/$GITHUB_USERNAME/$PRODUCT_REPO.git"
    cd "$PRODUCT_REPO"
fi

# Initialize basic structure
echo "🏗️  Initializing product structure..."
mkdir -p {ai-shopping-agent,deployment,docs,examples,tests}
mkdir -p ai-shopping-agent/{whatsapp-integration,ai-curation,negotiation-engine,checkout-optimizer,analytics}

# Create basic files if they don't exist
if [[ ! -f "README.md" ]]; then
    cat > README.md << 'EOF'
# AI Shopping Concierge (AP2)

An intelligent shopping assistant built on the AP2 (Agentic Protocol 2) platform.

## Features
- 🤖 AI-powered product curation
- 💬 Multi-channel chat (WhatsApp, Web)
- 💰 Smart negotiation and bundling
- 💳 Automated payment processing with currency conversion
- 📊 Advanced analytics and insights

## Quick Start
```bash
# Install dependencies
pip install -r requirements.txt

# Start the shopping agent
python -m ai_shopping_agent
```

## Documentation
- [Getting Started](docs/getting-started.md)
- [API Reference](docs/api-reference.md)
- [Deployment Guide](docs/deployment.md)

## Built With
- [AP2 Protocol](https://github.com/google-agentic-commerce/AP2) - Core payment and commerce infrastructure
- FastAPI - Web framework
- Google AI - Language models
- WhatsApp Business API - Messaging

## License
Apache 2.0 - see LICENSE file
EOF
fi

# Create gitignore if it doesn't exist
if [[ ! -f ".gitignore" ]]; then
    cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Project specific
config/secrets.yaml
logs/
.coverage
htmlcov/

# AP2 Core (will be added as submodule)
ap2-core/
EOF
fi

echo "✅ Product repository initialized"

# Step 6: Add AP2 as submodule
echo "🔗 Adding AP2 core as submodule..."
if [[ ! -d "ap2-core" ]]; then
    git submodule add "https://github.com/$GITHUB_USERNAME/AP2.git" ap2-core
    git submodule update --init --recursive
    echo "✅ AP2 core added as submodule"
else
    echo "   ⚠️  AP2 submodule already exists"
fi

# Commit initial structure
if [[ -n "$(git status --porcelain)" ]]; then
    git add .
    git commit -m "Initial AI Shopping Concierge structure with AP2 submodule"
    git push origin main
    echo "✅ Initial structure committed and pushed"
fi

echo
echo "🎉 SUCCESS! Repository setup completed!"
echo "======================================"
echo
echo "📁 Your repositories:"
echo "   Fork: https://github.com/$GITHUB_USERNAME/AP2"
echo "   Product: https://github.com/$GITHUB_USERNAME/$PRODUCT_REPO"
echo
echo "🚀 Next steps:"
echo "   1. cd ../$PRODUCT_REPO"
echo "   2. Run: ../AP2/scripts/repository-setup/3-migrate-code.sh"
echo "   3. Start developing your AI Shopping Concierge!"
echo

cd "../AP2"  # Return to original directory
echo "📍 Returned to AP2 directory: $(pwd)"