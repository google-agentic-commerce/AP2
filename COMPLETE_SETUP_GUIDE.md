# AI Shopping Concierge - Complete Setup and Deployment Guide

## 🚀 Quick Start

The AI Shopping Concierge is built on top of the AP2 protocol, providing intelligent shopping assistance with WhatsApp/web chat, AI curation, negotiation, and seamless checkout.

## 📁 Project Structure

```
AP2/
├── product-layer/              # Your product innovations
│   └── ai-shopping-agent/     # AI Shopping Concierge code
├── scripts/
│   ├── repository-setup/      # Setup and migration scripts
│   └── automation/           # Sync, deploy, maintenance
├── samples/python/           # Extended AP2 Python samples
├── deployment/              # Docker, K8s, cloud configs
├── docs/ai-shopping-concierge/  # Documentation
└── .github/workflows/       # CI/CD pipelines
```

## 🔧 Complete Setup Workflow

### Step 1: Repository Setup

#### Option A: Linux/Mac
```bash
# Fork AP2 repo and set up your product repo
./scripts/repository-setup/1-fork-and-setup.sh

# Sync and verify setup
./scripts/repository-setup/2-sync-and-verify.sh

# Migrate your code to product layer
./scripts/repository-setup/3-migrate-code.sh
```

#### Option B: Windows
```powershell
# Fork AP2 repo and set up your product repo
.\scripts\repository-setup\1-fork-and-setup.bat
```

### Step 2: Development Setup

1. **Install Dependencies**
```bash
cd samples/python
pip install -r requirements.txt
pip install -e .
```

2. **Environment Configuration**
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

3. **Database Setup**
```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up -d

# Run migrations
python -m alembic upgrade head
```

### Step 3: Run the AI Shopping Concierge

#### Development Mode
```bash
# Start the FastAPI server
cd samples/python
python -m src.common.server

# Or use the development docker setup
docker-compose -f docker-compose.dev.yml up
```

#### Production Mode
```bash
# Build and run production containers
docker-compose -f docker-compose.production.yml up -d
```

## ☁️ Cloud Deployment

### AWS ECS
```bash
./scripts/automation/cloud-deploy.sh --provider aws --region us-west-2 deploy
```

### Google Cloud Run
```bash
./scripts/automation/cloud-deploy.sh --provider gcp --region us-central1 deploy
```

### Azure Container Instances
```bash
./scripts/automation/cloud-deploy.sh --provider azure --region eastus deploy
```

### Kubernetes
```bash
# Apply Kubernetes manifests
kubectl apply -f deployment/kubernetes/production.yaml

# Check deployment status
kubectl get pods -n ai-shopping-concierge
```

## 🔄 Maintenance and Updates

### Sync with Upstream AP2
```bash
# Sync latest changes from Google's AP2 repo
./scripts/automation/sync-upstream.sh

# Deploy updated version
./scripts/automation/deploy.sh production
```

### Monitor and Maintain
```bash
# Run maintenance tasks
./scripts/automation/maintenance.sh

# Check application health
curl http://localhost:8000/health
```

## 🧪 Testing

### Unit Tests
```bash
cd samples/python
python -m pytest tests/ -v
```

### Integration Tests
```bash
# Test WhatsApp integration
python -m pytest tests/integration/test_whatsapp.py

# Test AI curation
python -m pytest tests/integration/test_curation.py

# Test checkout flow
python -m pytest tests/integration/test_checkout.py
```

### Load Testing
```bash
# Install k6
brew install k6  # macOS
# or download from https://k6.io/

# Run load tests
k6 run tests/load/basic-load-test.js
```

## 📊 Monitoring and Observability

### Prometheus Metrics
- Application metrics: `http://localhost:9090`
- Custom metrics for shopping sessions, conversions, etc.

### Grafana Dashboards
- Performance dashboard: `http://localhost:3000`
- Business metrics dashboard with shopping analytics

### Log Aggregation
- Centralized logging with Fluentd
- Structured logs for easy analysis

## 🔐 Security

### Environment Variables
```bash
# Required API keys and secrets
GOOGLE_AI_API_KEY=your_google_ai_key
WHATSAPP_ACCESS_TOKEN=your_whatsapp_token
AP2_MERCHANT_ID=your_merchant_id
AP2_API_KEY=your_ap2_key
SECRET_KEY=your_secret_key
```

### SSL/TLS Configuration
- Automatic HTTPS with Let's Encrypt
- Certificate management in cloud deployments

## 🏗️ Architecture Overview

### Core Components
1. **WhatsApp Integration** (`channels/whatsapp_integration.py`)
   - Business API integration
   - Message handling and routing

2. **AI Curation Engine** (`ai_curation/smart_curation_engine.py`)
   - Product recommendation
   - Personalized suggestions

3. **Negotiation Engine** (`ai_curation/negotiation_engine.py`)
   - Dynamic pricing
   - Bundle optimization

4. **Checkout Optimizer** (`optimization/checkout_optimizer.py`)
   - Payment processing
   - Currency conversion
   - Settlement handling

5. **Analytics Engine** (`analytics/performance_analytics.py`)
   - Real-time metrics
   - Business intelligence

### Data Flow
```
Customer Message → WhatsApp → AI Agent → Product Curation → Negotiation → AP2 Checkout → Payment
                                    ↓
                               Analytics & Monitoring
```

## 🔧 Configuration

### Application Settings
```python
# src/common/config.py
class Settings:
    environment: str = "production"
    debug: bool = False
    database_url: str
    redis_url: str
    google_ai_api_key: str
    whatsapp_access_token: str
    ap2_merchant_id: str
    # ... more settings
```

### Feature Flags
```python
# Enable/disable features
ENABLE_AI_NEGOTIATION = True
ENABLE_CURRENCY_CONVERSION = True
ENABLE_ANALYTICS = True
MAX_PRODUCTS_PER_RECOMMENDATION = 10
```

## 📈 Scaling

### Horizontal Scaling
- Auto-scaling based on CPU/memory usage
- Load balancing across multiple instances

### Database Scaling
- Read replicas for analytics queries
- Connection pooling for high concurrency

### Caching Strategy
- Redis for session data and recommendations
- CDN for static assets

## 🐛 Troubleshooting

### Common Issues

1. **WhatsApp Webhook Verification Failed**
   ```bash
   # Check webhook URL and verify token
   curl -X GET "https://your-domain.com/webhooks/whatsapp?hub.verify_token=your_verify_token&hub.challenge=challenge"
   ```

2. **Database Connection Issues**
   ```bash
   # Check database connectivity
   docker-compose logs db
   ```

3. **AI API Rate Limits**
   ```bash
   # Monitor API usage and implement rate limiting
   # Check logs for rate limit errors
   ```

### Debug Mode
```bash
# Enable debug logging
export DEBUG=true
export LOG_LEVEL=DEBUG
```

## 📚 API Reference

### REST Endpoints
- `GET /health` - Health check
- `POST /webhooks/whatsapp` - WhatsApp webhook
- `GET /api/products/recommendations` - Product recommendations
- `POST /api/checkout/initiate` - Start checkout process
- `GET /api/analytics/dashboard` - Analytics data

### WebSocket Endpoints
- `/ws/chat/{session_id}` - Real-time chat
- `/ws/notifications` - Real-time notifications

## 🤝 Contributing

### Development Workflow
1. Fork the repository
2. Create a feature branch
3. Make changes and add tests
4. Run tests and linting
5. Submit a pull request

### Code Style
```bash
# Format code
black samples/python/src/
isort samples/python/src/

# Lint code
flake8 samples/python/src/
mypy samples/python/src/
```

## 📝 License

This project extends the AP2 protocol under the Apache 2.0 License. See [LICENSE](LICENSE) for details.

## 🆘 Support

- **Documentation**: [docs/ai-shopping-concierge/](docs/ai-shopping-concierge/)
- **Issues**: GitHub Issues
- **Discord**: [AP2 Community](https://discord.gg/ap2-community)

## 🎯 Roadmap

### Current Features ✅
- WhatsApp Business API integration
- AI-powered product curation
- Dynamic pricing and negotiation
- AP2 secure checkout
- Real-time analytics
- Multi-cloud deployment

### Upcoming Features 🚧
- Voice integration (Twilio/AWS Connect)
- Multi-language support
- Advanced ML recommendations
- Inventory management integration
- B2B marketplace features

---

**Ready to revolutionize shopping with AI? Start building your intelligent shopping concierge today!** 🛍️✨