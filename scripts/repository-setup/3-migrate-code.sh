#!/bin/bash

# AI Shopping Concierge - Code Migration Script
# Migrates AI shopping agent code to the product repository

set -e

echo "📦 AI Shopping Concierge - Code Migration"
echo "========================================"

# Configuration
GITHUB_USERNAME="${1:-ankitap}"
PRODUCT_REPO="ai-shopping-concierge-ap2"
PRODUCT_DIR="../$PRODUCT_REPO"
AP2_DIR="$(pwd)"

# Verify we're in the right place
if [[ ! -f "pyproject.toml" ]] || [[ ! -d ".git" ]]; then
    echo "❌ Please run this script from the AP2 repository root directory"
    exit 1
fi

if [[ ! -d "$PRODUCT_DIR" ]]; then
    echo "❌ Product repository not found at: $PRODUCT_DIR"
    echo "   Please run: ./scripts/repository-setup/2-sync-and-verify.sh first"
    exit 1
fi

echo "✅ Directories verified"

# Step 1: Copy AI Shopping Agent code
echo "📋 Migrating AI Shopping Agent code..."

# Create target directories
cd "$PRODUCT_DIR"
mkdir -p ai-shopping-agent/{whatsapp-integration,ai-curation,negotiation-engine,checkout-optimizer,analytics,common}

# Copy the enhanced modules we created
echo "   📄 Copying enhanced modules..."

# WhatsApp Integration
if [[ -f "$AP2_DIR/samples/python/src/channels/whatsapp_integration.py" ]]; then
    cp "$AP2_DIR/samples/python/src/channels/whatsapp_integration.py" "ai-shopping-agent/whatsapp-integration/"
    echo "   ✅ WhatsApp integration copied"
fi

# AI Curation
if [[ -f "$AP2_DIR/samples/python/src/ai_curation/smart_curation_engine.py" ]]; then
    cp "$AP2_DIR/samples/python/src/ai_curation/smart_curation_engine.py" "ai-shopping-agent/ai-curation/"
fi

if [[ -f "$AP2_DIR/samples/python/src/ai_curation/negotiation_engine.py" ]]; then
    cp "$AP2_DIR/samples/python/src/ai_curation/negotiation_engine.py" "ai-shopping-agent/negotiation-engine/"
fi

# Unified Chat Manager
if [[ -f "$AP2_DIR/samples/python/src/channels/unified_chat_manager.py" ]]; then
    cp "$AP2_DIR/samples/python/src/channels/unified_chat_manager.py" "ai-shopping-agent/whatsapp-integration/"
fi

# Checkout Optimizer
if [[ -f "$AP2_DIR/samples/python/src/optimization/checkout_optimizer.py" ]]; then
    cp "$AP2_DIR/samples/python/src/optimization/checkout_optimizer.py" "ai-shopping-agent/checkout-optimizer/"
    echo "   ✅ Enhanced checkout optimizer with payment processing copied"
fi

# Analytics
if [[ -f "$AP2_DIR/samples/python/src/analytics/performance_analytics.py" ]]; then
    cp "$AP2_DIR/samples/python/src/analytics/performance_analytics.py" "ai-shopping-agent/analytics/"
fi

# Common utilities
if [[ -d "$AP2_DIR/samples/python/src/common" ]]; then
    cp -r "$AP2_DIR/samples/python/src/common/"* "ai-shopping-agent/common/" 2>/dev/null || true
fi

echo "   ✅ AI Shopping Agent modules migrated"

# Step 2: Create main application entry point
echo "🚀 Creating application entry point..."

cat > ai-shopping-agent/__init__.py << 'EOF'
"""
AI Shopping Concierge
Built on AP2 Protocol

An intelligent shopping assistant that provides:
- Multi-channel chat support (WhatsApp, Web)
- AI-powered product curation and recommendations
- Smart negotiation and dynamic pricing
- Automated payment processing with currency conversion
- Advanced analytics and insights
"""

__version__ = "1.0.0"
__author__ = "AI Shopping Concierge Team"

from .whatsapp_integration import WhatsAppShoppingAgent
from .smart_curation_engine import SmartCurationEngine
from .negotiation_engine import NegotiationEngine
from .checkout_optimizer import ConversionOptimizer
from .performance_analytics import AnalyticsEngine

__all__ = [
    "WhatsAppShoppingAgent",
    "SmartCurationEngine", 
    "NegotiationEngine",
    "ConversionOptimizer",
    "AnalyticsEngine"
]
EOF

cat > ai-shopping-agent/__main__.py << 'EOF'
"""
AI Shopping Concierge - Main Application Entry Point
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the AP2 core to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "ap2-core" / "samples" / "python" / "src"))

from ai_shopping_agent.whatsapp_integration.whatsapp_integration import WhatsAppShoppingAgent
from ai_shopping_agent.ai_curation.smart_curation_engine import SmartCurationEngine
from ai_shopping_agent.negotiation_engine.negotiation_engine import NegotiationEngine
from ai_shopping_agent.checkout_optimizer.checkout_optimizer import ConversionOptimizer
from ai_shopping_agent.analytics.performance_analytics import AnalyticsEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class AIShoppingConcierge:
    """Main AI Shopping Concierge application."""
    
    def __init__(self):
        self.whatsapp_agent = WhatsAppShoppingAgent()
        self.curation_engine = SmartCurationEngine()
        self.negotiation_engine = NegotiationEngine()
        self.checkout_optimizer = ConversionOptimizer()
        self.analytics_engine = AnalyticsEngine()
        
    async def start(self):
        """Start the AI Shopping Concierge."""
        logger.info("🚀 Starting AI Shopping Concierge...")
        
        # Initialize all components
        await self.whatsapp_agent.initialize()
        await self.curation_engine.initialize()
        await self.negotiation_engine.initialize()
        await self.analytics_engine.initialize()
        
        logger.info("✅ AI Shopping Concierge started successfully!")
        logger.info("💬 WhatsApp integration ready")
        logger.info("🤖 AI curation engine ready") 
        logger.info("💰 Negotiation engine ready")
        logger.info("💳 Checkout optimizer ready")
        logger.info("📊 Analytics engine ready")
        
        # Keep the application running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("🛑 Shutting down AI Shopping Concierge...")
        
    async def shutdown(self):
        """Gracefully shutdown the application."""
        logger.info("🔄 Shutting down components...")
        # Add cleanup logic here
        logger.info("✅ Shutdown complete")

async def main():
    """Main application entry point."""
    app = AIShoppingConcierge()
    try:
        await app.start()
    finally:
        await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
EOF

echo "   ✅ Application entry point created"

# Step 3: Create requirements.txt
echo "📦 Creating requirements.txt..."

cat > requirements.txt << 'EOF'
# AI Shopping Concierge Dependencies

# Core framework
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.5.0

# HTTP client
aiohttp>=3.9.0
httpx>=0.25.0

# Google AI
google-generativeai>=0.3.0

# WhatsApp Business API
twilio>=8.10.0

# Data processing
pandas>=2.1.0
numpy>=1.25.0

# Database
sqlalchemy>=2.0.0
asyncpg>=0.29.0  # PostgreSQL
redis>=5.0.0

# Currency conversion
forex-python>=1.8

# Background tasks
celery>=5.3.0

# Monitoring and logging
prometheus-client>=0.19.0
structlog>=23.2.0

# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0
httpx>=0.25.0  # For testing

# Development
black>=23.11.0
isort>=5.12.0
mypy>=1.7.0

# Security
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4

# Configuration
python-dotenv>=1.0.0
pyyaml>=6.0.1

# AP2 Core (as git submodule)
# See ap2-core/ directory
EOF

echo "   ✅ Requirements file created"

# Step 4: Create configuration files
echo "⚙️  Creating configuration files..."

mkdir -p config

cat > config/app.yaml << 'EOF'
# AI Shopping Concierge Configuration

app:
  name: "AI Shopping Concierge"
  version: "1.0.0"
  debug: false
  host: "0.0.0.0"
  port: 8000

# WhatsApp Configuration
whatsapp:
  verify_token: "${WHATSAPP_VERIFY_TOKEN}"
  access_token: "${WHATSAPP_ACCESS_TOKEN}"
  phone_number_id: "${WHATSAPP_PHONE_NUMBER_ID}"
  webhook_url: "${WHATSAPP_WEBHOOK_URL}"

# Google AI Configuration
google_ai:
  api_key: "${GOOGLE_AI_API_KEY}"
  model: "gemini-pro"
  max_tokens: 1000

# Database Configuration
database:
  url: "${DATABASE_URL}"
  echo: false
  pool_size: 10
  max_overflow: 20

# Redis Configuration  
redis:
  url: "${REDIS_URL}"
  max_connections: 20

# Payment Processing
payment:
  default_currency: "USD"
  supported_currencies: ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "CNY", "INR", "BRL"]
  
  processors:
    ap2:
      merchant_id: "${AP2_MERCHANT_ID}"
      api_endpoint: "https://ap2.googleapis.com/v1"
      api_key: "${AP2_API_KEY}"
    
    stripe:
      api_key: "${STRIPE_API_KEY}"
      webhook_secret: "${STRIPE_WEBHOOK_SECRET}"
    
    paypal:
      client_id: "${PAYPAL_CLIENT_ID}"
      client_secret: "${PAYPAL_CLIENT_SECRET}"

# Analytics
analytics:
  enabled: true
  retention_days: 90
  export_format: "json"

# Security
security:
  secret_key: "${SECRET_KEY}"
  algorithm: "HS256"
  access_token_expire_minutes: 30

# Logging
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "logs/app.log"
EOF

cat > config/secrets.yaml.example << 'EOF'
# AI Shopping Concierge - Secrets Configuration
# Copy this file to secrets.yaml and fill in your actual values

# WhatsApp Business API
WHATSAPP_VERIFY_TOKEN: "your_verify_token_here"
WHATSAPP_ACCESS_TOKEN: "your_access_token_here"
WHATSAPP_PHONE_NUMBER_ID: "your_phone_number_id_here"
WHATSAPP_WEBHOOK_URL: "https://your-domain.com/webhook/whatsapp"

# Google AI
GOOGLE_AI_API_KEY: "your_google_ai_api_key_here"

# Database
DATABASE_URL: "postgresql+asyncpg://user:password@localhost/ai_shopping_concierge"

# Redis
REDIS_URL: "redis://localhost:6379/0"

# Payment Processors
AP2_MERCHANT_ID: "your_ap2_merchant_id"
AP2_API_KEY: "your_ap2_api_key"
STRIPE_API_KEY: "sk_test_your_stripe_key"
STRIPE_WEBHOOK_SECRET: "whsec_your_webhook_secret"
PAYPAL_CLIENT_ID: "your_paypal_client_id"
PAYPAL_CLIENT_SECRET: "your_paypal_client_secret"

# Security
SECRET_KEY: "your_super_secret_key_change_this_in_production"

# Environment
ENVIRONMENT: "development"  # development, staging, production
EOF

echo "   ✅ Configuration files created"

# Step 5: Create Docker configuration
echo "🐳 Creating Docker configuration..."

cat > Dockerfile << 'EOF'
# AI Shopping Concierge Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Initialize AP2 submodule
RUN git submodule update --init --recursive

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["python", "-m", "ai_shopping_agent"]
EOF

cat > docker-compose.yml << 'EOF'
# AI Shopping Concierge - Docker Compose

version: '3.8'

services:
  ai-shopping-concierge:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:password@db:5432/ai_shopping_concierge
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
    restart: unless-stopped

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: ai_shopping_concierge
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./deployment/nginx.conf:/etc/nginx/nginx.conf
      - ./deployment/ssl:/etc/ssl
    depends_on:
      - ai-shopping-concierge

volumes:
  postgres_data:
  redis_data:
EOF

echo "   ✅ Docker configuration created"

# Step 6: Commit changes
echo "💾 Committing migrated code..."

# Add all files
git add .

# Check if there are changes to commit
if [[ -n "$(git status --porcelain)" ]]; then
    git commit -m "Migrate AI Shopping Concierge code from AP2 samples

- Added enhanced WhatsApp integration
- Added AI curation and negotiation engines  
- Added checkout optimizer with payment processing
- Added analytics engine
- Added application entry point and configuration
- Added Docker and deployment configuration"

    git push origin main
    echo "✅ Changes committed and pushed"
else
    echo "   ℹ️  No changes to commit"
fi

echo
echo "🎉 SUCCESS! Code migration completed!"
echo "===================================="
echo
echo "📁 Your AI Shopping Concierge is ready at:"
echo "   $(pwd)"
echo
echo "🚀 Quick start:"
echo "   1. cp config/secrets.yaml.example config/secrets.yaml"
echo "   2. Edit config/secrets.yaml with your API keys"
echo "   3. pip install -r requirements.txt"
echo "   4. python -m ai_shopping_agent"
echo
echo "🐳 Or using Docker:"
echo "   docker-compose up --build"
echo
echo "📖 Next: Create documentation with:"
echo "   ../AP2/scripts/repository-setup/4-create-docs.sh"
echo

# Return to AP2 directory
cd "$AP2_DIR"