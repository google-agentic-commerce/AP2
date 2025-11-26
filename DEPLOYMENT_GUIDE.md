# AI Shopping Agent Deployment Guide

## Overview

This guide provides complete setup and deployment instructions for the enhanced AI Shopping Agent built on the AP2 (Agent Payments Protocol) platform. The solution includes multi-channel support (WhatsApp, Web Chat), AI-powered product curation, intelligent negotiation, and comprehensive analytics.

## Features

- **Multi-Channel Support**: WhatsApp Business API, Web Chat Widget, SMS, Telegram
- **AI Product Curation**: Personalized recommendations, smart bundles, dynamic pricing
- **Intelligent Negotiation**: Real-time price negotiation, discount optimization
- **Checkout Optimization**: Cart abandonment recovery, one-click purchasing
- **Comprehensive Analytics**: Conversion tracking, AOV metrics, customer insights
- **AP2 Integration**: Secure payments through Agent Payments Protocol

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   WhatsApp      │    │   Web Chat      │    │   Other         │
│   Business API  │    │   Widget        │    │   Channels      │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────▼─────────────┐
                    │   Unified Chat Manager    │
                    └─────────────┬─────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
┌─────────▼─────────┐   ┌─────────▼─────────┐   ┌─────────▼─────────┐
│   AI Curation     │   │   Negotiation     │   │   Checkout        │
│   Engine          │   │   Engine          │   │   Optimizer       │
└─────────┬─────────┘   └─────────┬─────────┘   └─────────┬─────────┘
          │                       │                       │
          └───────────────────────┼───────────────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │   AP2 Shopping Agent      │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │   Analytics Engine        │
                    └───────────────────────────┘
```

## Prerequisites

### System Requirements

- Python 3.10 or higher
- Node.js 18+ (for web components)
- PostgreSQL 12+ or SQLite (for production use PostgreSQL)
- Redis 6+ (for session management and caching)
- Minimum 4GB RAM, 2 CPU cores
- 20GB disk space

### Required Services

1. **Google AI Studio API Key** or **Vertex AI** access
2. **WhatsApp Business API** account
3. **Facebook Developer** account (for WhatsApp)
4. **Domain** with SSL certificate
5. **Email service** (for notifications)

### Development Tools

```bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Node.js dependencies
npm install -g typescript

# Install Docker (optional but recommended)
# Follow Docker installation guide for your OS
```

## Installation

### 1. Clone and Setup Repository

```bash
# Clone the AP2 repository
git clone https://github.com/google-agentic-commerce/AP2.git
cd AP2

# Create virtual environment
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -r requirements.txt
uv pip install -e .
```

### 2. Environment Configuration

Create a `.env` file in the root directory:

```bash
# Google AI Configuration
GOOGLE_API_KEY=your_google_ai_api_key
# OR for Vertex AI:
# GOOGLE_GENAI_USE_VERTEXAI=true
# GOOGLE_CLOUD_PROJECT=your-project-id
# GOOGLE_CLOUD_LOCATION=global

# WhatsApp Business API
WHATSAPP_BUSINESS_TOKEN=your_whatsapp_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_WEBHOOK_VERIFY_TOKEN=your_webhook_verify_token

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/ai_shopping_agent
# For development, you can use SQLite:
# DATABASE_URL=sqlite:///./ai_shopping_agent.db

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Application Settings
SECRET_KEY=your_secret_key_here
DEBUG=false
ENVIRONMENT=production

# Webhook URLs
BASE_URL=https://your-domain.com
WEBHOOK_SECRET=your_webhook_secret

# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password

# Analytics Configuration
ANALYTICS_ENABLED=true
EXPORT_ANALYTICS_DAILY=true
```

### 3. Database Setup

```bash
# For PostgreSQL
createdb ai_shopping_agent

# Run migrations (if using Django/SQLAlchemy)
python manage.py migrate

# Or initialize tables manually
python scripts/init_database.py
```

### 4. WhatsApp Business API Setup

#### 4.1 Create Facebook App

1. Go to [Facebook Developers](https://developers.facebook.com/)
2. Create new app → Business → Create app
3. Add WhatsApp product to your app

#### 4.2 Configure WhatsApp Business API

1. Get temporary access token from WhatsApp Business API setup
2. Configure webhook URL: `https://your-domain.com/webhook/whatsapp`
3. Set webhook verify token in your `.env` file
4. Subscribe to webhook events: `messages`, `message_status`

#### 4.3 Test WhatsApp Integration

```bash
# Test webhook verification
curl -X GET "https://your-domain.com/webhook/whatsapp?hub.mode=subscribe&hub.challenge=CHALLENGE_ACCEPTED&hub.verify_token=your_verify_token"

# Should return: CHALLENGE_ACCEPTED
```

## Deployment Options

### Option 1: Docker Deployment (Recommended)

#### 1.1 Create Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY . .

# Install the package
RUN pip install -e .

# Expose port
EXPOSE 8000

# Start application
CMD ["uvicorn", "samples.python.src.channels.unified_chat_manager:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 1.2 Create docker-compose.yml

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/ai_shopping_agent
      - REDIS_URL=redis://redis:6379/0
    env_file:
      - .env
    depends_on:
      - db
      - redis
    volumes:
      - ./logs:/app/logs

  db:
    image: postgres:13
    environment:
      POSTGRES_DB: ai_shopping_agent
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:6-alpine
    ports:
      - "6379:6379"

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - app

volumes:
  postgres_data:
```

#### 1.3 Deploy with Docker

```bash
# Build and start services
docker-compose up -d

# Check logs
docker-compose logs -f app

# Scale if needed
docker-compose up -d --scale app=3
```

### Option 2: Cloud Platform Deployment

#### 2.1 Google Cloud Platform

```bash
# Install Google Cloud CLI
curl https://sdk.cloud.google.com | bash

# Initialize and authenticate
gcloud init
gcloud auth login

# Create project
gcloud projects create ai-shopping-agent-prod
gcloud config set project ai-shopping-agent-prod

# Deploy to Cloud Run
gcloud run deploy ai-shopping-agent \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --min-instances 1 \
  --max-instances 10
```

#### 2.2 AWS Deployment

```bash
# Install AWS CLI and EB CLI
pip install awscli awsebcli

# Initialize Elastic Beanstalk
eb init
eb create ai-shopping-agent-prod

# Deploy
eb deploy
```

#### 2.3 Azure Deployment

```bash
# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Create resource group
az group create --name ai-shopping-agent --location eastus

# Create web app
az webapp create --resource-group ai-shopping-agent --plan ai-shopping-agent-plan --name ai-shopping-agent --runtime "PYTHON|3.11"

# Deploy
az webapp deployment source config --name ai-shopping-agent --resource-group ai-shopping-agent --repo-url https://github.com/your-repo/ai-shopping-agent --branch main
```

## Configuration

### Application Settings

Create `config.py`:

```python
import os
from typing import Optional

class Settings:
    # API Configuration
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")
    WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_BUSINESS_TOKEN", "")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Application
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # AI Curation Settings
    MAX_RECOMMENDATIONS: int = 10
    DEFAULT_DISCOUNT_LIMIT: float = 0.25
    NEGOTIATION_ENABLED: bool = True
    
    # Checkout Optimization
    CART_ABANDONMENT_TIMEOUT: int = 1800  # 30 minutes
    RECOVERY_ATTEMPTS_LIMIT: int = 3
    
    # Analytics
    ANALYTICS_ENABLED: bool = True
    ANALYTICS_RETENTION_DAYS: int = 365

settings = Settings()
```

### Nginx Configuration

Create `nginx.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream app {
        server app:8000;
    }

    server {
        listen 80;
        server_name your-domain.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;

        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;

        location / {
            proxy_pass http://app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /ws/ {
            proxy_pass http://app;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
        }
    }
}
```

## Running the Application

### Development Mode

```bash
# Start individual components
cd samples/python

# Start unified chat manager
python -m uvicorn src.channels.unified_chat_manager:app --reload --port 8000

# Start analytics dashboard (optional)
python -m uvicorn src.analytics.dashboard:app --reload --port 8001

# Start background workers
python -m celery worker -A src.tasks --loglevel=info
```

### Production Mode

```bash
# Using gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker samples.python.src.channels.unified_chat_manager:app --bind 0.0.0.0:8000

# Or using uvicorn
uvicorn samples.python.src.channels.unified_chat_manager:app --host 0.0.0.0 --port 8000 --workers 4
```

## Testing

### Unit Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test files
python -m pytest tests/test_curation_engine.py
python -m pytest tests/test_negotiation_engine.py
python -m pytest tests/test_chat_manager.py

# Run with coverage
python -m pytest --cov=src tests/
```

### Integration Tests

```bash
# Test WhatsApp integration
python tests/integration/test_whatsapp.py

# Test end-to-end shopping flow
python tests/integration/test_shopping_flow.py

# Load testing
python tests/load/test_concurrent_users.py
```

### Manual Testing

```bash
# Test web chat locally
curl -X POST http://localhost:8000/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d '{"entry":[{"changes":[{"field":"messages","value":{"messages":[{"from":"1234567890","text":{"body":"Hi"},"timestamp":"1640995200"}]}}]}]}'

# Test WhatsApp webhook
ngrok http 8000
# Update webhook URL in Facebook Developer Console to ngrok URL
```

## Monitoring and Maintenance

### Health Checks

```python
# Add to your application
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "database": await check_database_health(),
            "redis": await check_redis_health(),
            "whatsapp_api": await check_whatsapp_health()
        }
    }
```

### Logging

```python
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
```

### Metrics and Alerts

```bash
# Using Prometheus and Grafana
docker run -d -p 9090:9090 prom/prometheus
docker run -d -p 3000:3000 grafana/grafana

# Add metrics endpoints to your app
from prometheus_client import Counter, Histogram, generate_latest

message_counter = Counter('messages_total', 'Total messages processed')
response_time = Histogram('response_time_seconds', 'Response time')

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

## Security

### SSL/TLS Configuration

```bash
# Get Let's Encrypt certificate
sudo apt install certbot
sudo certbot certonly --standalone -d your-domain.com

# Or use CloudFlare for SSL termination
```

### API Security

```python
from fastapi import HTTPException, Depends, Header

async def verify_webhook_signature(
    x_hub_signature_256: str = Header(None),
    request: Request
):
    if not x_hub_signature_256:
        raise HTTPException(status_code=401, detail="Missing signature")
    
    body = await request.body()
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(f"sha256={expected_signature}", x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")
```

### Environment Security

```bash
# Secure environment variables
chmod 600 .env

# Use secret management
aws secretsmanager create-secret --name ai-shopping-agent-config
gcloud secrets create ai-shopping-agent-config
az keyvault secret set --vault-name ai-shopping-agent --name config
```

## Scaling and Performance

### Horizontal Scaling

```yaml
# Kubernetes deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-shopping-agent
spec:
  replicas: 5
  selector:
    matchLabels:
      app: ai-shopping-agent
  template:
    metadata:
      labels:
        app: ai-shopping-agent
    spec:
      containers:
      - name: app
        image: ai-shopping-agent:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-config
              key: url
```

### Performance Optimization

```python
# Add caching
from functools import lru_cache
import redis

redis_client = redis.Redis.from_url(settings.REDIS_URL)

@lru_cache(maxsize=1000)
def get_cached_recommendations(customer_id: str, query: str):
    cache_key = f"recommendations:{customer_id}:{hash(query)}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Generate recommendations
    recommendations = generate_recommendations(customer_id, query)
    redis_client.setex(cache_key, 3600, json.dumps(recommendations))
    return recommendations
```

### Database Optimization

```sql
-- Add database indexes
CREATE INDEX idx_customer_events ON analytics_events(customer_id, timestamp);
CREATE INDEX idx_session_events ON analytics_events(session_id);
CREATE INDEX idx_event_type ON analytics_events(event_type);

-- Partition large tables
CREATE TABLE analytics_events_2024_01 PARTITION OF analytics_events
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

## Troubleshooting

### Common Issues

1. **WhatsApp webhook not receiving messages**
   ```bash
   # Check webhook verification
   curl -X GET "https://your-domain.com/webhook/whatsapp?hub.mode=subscribe&hub.challenge=test&hub.verify_token=your_token"
   
   # Check webhook logs
   docker-compose logs -f app | grep webhook
   ```

2. **High response times**
   ```python
   # Add performance monitoring
   import time
   
   @app.middleware("http")
   async def add_process_time_header(request: Request, call_next):
       start_time = time.time()
       response = await call_next(request)
       process_time = time.time() - start_time
       response.headers["X-Process-Time"] = str(process_time)
       return response
   ```

3. **Database connection issues**
   ```bash
   # Check database connectivity
   python -c "import psycopg2; conn = psycopg2.connect('your_db_url'); print('Connected successfully')"
   
   # Check connection pool
   docker-compose logs db
   ```

### Debugging Tools

```bash
# Debug mode
export DEBUG=true
python -m uvicorn src.channels.unified_chat_manager:app --reload --log-level debug

# Profile performance
pip install py-spy
py-spy top --pid $(pydoc python)

# Memory profiling
pip install memory-profiler
python -m memory_profiler your_script.py
```

## API Documentation

The application provides comprehensive API documentation at:

- Swagger UI: `https://your-domain.com/docs`
- ReDoc: `https://your-domain.com/redoc`
- OpenAPI JSON: `https://your-domain.com/openapi.json`

## Support and Maintenance

### Regular Maintenance Tasks

```bash
# Weekly tasks
python scripts/cleanup_old_sessions.py
python scripts/archive_old_analytics.py
python scripts/backup_database.py

# Monthly tasks
python scripts/optimize_database.py
python scripts/update_ml_models.py
python scripts/generate_business_report.py
```

### Backup Strategy

```bash
# Database backup
pg_dump ai_shopping_agent > backup_$(date +%Y%m%d).sql

# Application backup
tar -czf app_backup_$(date +%Y%m%d).tar.gz /path/to/app

# Automated backup with cron
0 2 * * * /path/to/backup_script.sh
```

### Update Procedure

```bash
# Update application
git pull origin main
uv pip install -r requirements.txt
python manage.py migrate
docker-compose restart app

# Zero-downtime deployment
docker-compose up -d --scale app=2
# Wait for health checks
docker-compose up -d --scale app=1
```

## Getting Help

- **Documentation**: [AP2 Documentation](https://google-agentic-commerce.github.io/AP2/)
- **Issues**: [GitHub Issues](https://github.com/google-agentic-commerce/AP2/issues)
- **Community**: [Discord/Slack Community](#)
- **Email Support**: support@your-domain.com

## License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.