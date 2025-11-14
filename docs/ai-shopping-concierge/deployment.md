# AI Shopping Concierge - Deployment Guide

Complete guide for deploying the AI Shopping Concierge to production environments.

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │────│      Nginx      │────│  AI Shopping    │
│   (CloudFlare)  │    │   (Reverse      │    │   Concierge     │
│                 │    │    Proxy)       │    │   (FastAPI)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                         │
                       ┌─────────────────┐              │
                       │   WhatsApp      │              │
                       │  Business API   │              │
                       │                 │              │
                       └─────────────────┘              │
                                                         │
        ┌─────────────────┐    ┌─────────────────┐      │
        │   PostgreSQL    │    │      Redis      │      │
        │   (Database)    │    │     (Cache)     │      │
        │                 │    │                 │      │
        └─────────────────┘    └─────────────────┘      │
                                                         │
        ┌─────────────────┐    ┌─────────────────┐      │
        │   Google AI     │    │   Payment       │      │
        │   (Gemini)      │────│  Processors     │──────┘
        │                 │    │  (AP2/Stripe)   │
        └─────────────────┘    └─────────────────┘
```

## 🚀 Deployment Options

### Option 1: Docker Compose (Recommended for Small-Medium Scale)

**Pros:**
- Easy to set up and manage
- Good for single-server deployments
- Built-in service orchestration
- Suitable for up to 10,000 users

**Cons:**
- Single point of failure
- Limited horizontal scaling
- Manual scaling required

### Option 2: Kubernetes (Recommended for Large Scale)

**Pros:**
- Auto-scaling capabilities
- High availability
- Zero-downtime deployments
- Suitable for 100,000+ users

**Cons:**
- Complex setup
- Requires Kubernetes expertise
- Higher operational overhead

### Option 3: Cloud Services (Managed)

**Pros:**
- Fully managed infrastructure
- Auto-scaling
- Built-in monitoring
- No server management

**Cons:**
- Higher costs
- Platform lock-in
- Less control

## 🐳 Docker Deployment

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- 4GB+ RAM
- 20GB+ disk space

### 1. Production Configuration

Create production configuration files:

**docker-compose.production.yml:**
```yaml
version: '3.8'

services:
  ai-shopping-concierge:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=postgresql+asyncpg://postgres:${DB_PASSWORD}@db:5432/ai_shopping_concierge
      - REDIS_URL=redis://redis:6379/0
      - GOOGLE_AI_API_KEY=${GOOGLE_AI_API_KEY}
      - WHATSAPP_ACCESS_TOKEN=${WHATSAPP_ACCESS_TOKEN}
      - AP2_MERCHANT_ID=${AP2_MERCHANT_ID}
    depends_on:
      - db
      - redis
    volumes:
      - ./config:/app/config:ro
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: ai_shopping_concierge
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backup:/backup
    restart: unless-stopped
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes --maxmemory 1gb --maxmemory-policy allkeys-lru

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./deployment/nginx.production.conf:/etc/nginx/nginx.conf:ro
      - ./deployment/ssl:/etc/ssl:ro
    depends_on:
      - ai-shopping-concierge
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

**deployment/nginx.production.conf:**
```nginx
events {
    worker_connections 1024;
}

http {
    upstream ai_shopping_concierge {
        server ai-shopping-concierge:8000;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

    server {
        listen 80;
        server_name your-domain.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;

        ssl_certificate /etc/ssl/your-domain.crt;
        ssl_certificate_key /etc/ssl/your-domain.key;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        # Security headers
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Frame-Options DENY always;
        add_header X-Content-Type-Options nosniff always;

        # API endpoints
        location /api/ {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://ai_shopping_concierge;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Webhook endpoints (no rate limiting)
        location /webhook/ {
            proxy_pass http://ai_shopping_concierge;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Health check
        location /health {
            proxy_pass http://ai_shopping_concierge;
            access_log off;
        }
    }
}
```

### 2. Environment Variables

Create `.env.production`:
```bash
# Database
DB_PASSWORD=your_secure_database_password

# API Keys
GOOGLE_AI_API_KEY=your_google_ai_api_key
WHATSAPP_ACCESS_TOKEN=your_whatsapp_access_token
WHATSAPP_VERIFY_TOKEN=your_whatsapp_verify_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id

# Payment Processors
AP2_MERCHANT_ID=your_ap2_merchant_id
AP2_API_KEY=your_ap2_api_key
STRIPE_API_KEY=your_stripe_api_key
PAYPAL_CLIENT_ID=your_paypal_client_id
PAYPAL_CLIENT_SECRET=your_paypal_client_secret

# Security
SECRET_KEY=your_super_secret_key_change_this_in_production

# Monitoring (optional)
SENTRY_DSN=your_sentry_dsn
DATADOG_API_KEY=your_datadog_api_key
```

### 3. SSL Certificates

Option A: Let's Encrypt (Free)
```bash
# Install certbot
sudo apt install certbot

# Get certificate
sudo certbot certonly --standalone -d your-domain.com

# Copy certificates
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem deployment/ssl/your-domain.crt
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem deployment/ssl/your-domain.key
```

Option B: Commercial Certificate
```bash
# Place your certificates in deployment/ssl/
cp your-domain.crt deployment/ssl/
cp your-domain.key deployment/ssl/
```

### 4. Deploy

```bash
# Build and start services
docker-compose -f docker-compose.production.yml up -d --build

# Check status
docker-compose -f docker-compose.production.yml ps

# View logs
docker-compose -f docker-compose.production.yml logs -f ai-shopping-concierge
```

## ☸️ Kubernetes Deployment

### Prerequisites

- Kubernetes cluster 1.20+
- kubectl configured
- Helm 3.0+ (optional)

### 1. Create Namespace

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ai-shopping-concierge
```

### 2. ConfigMap and Secrets

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: ai-shopping-concierge-config
  namespace: ai-shopping-concierge
data:
  app.yaml: |
    app:
      name: "AI Shopping Concierge"
      debug: false
      host: "0.0.0.0"
      port: 8000
    database:
      echo: false
      pool_size: 20
      max_overflow: 30
---
apiVersion: v1
kind: Secret
metadata:
  name: ai-shopping-concierge-secrets
  namespace: ai-shopping-concierge
type: Opaque
stringData:
  DATABASE_URL: "postgresql+asyncpg://postgres:password@postgres-service:5432/ai_shopping_concierge"
  REDIS_URL: "redis://redis-service:6379/0"
  GOOGLE_AI_API_KEY: "your_google_ai_api_key"
  WHATSAPP_ACCESS_TOKEN: "your_whatsapp_access_token"
  AP2_MERCHANT_ID: "your_ap2_merchant_id"
  SECRET_KEY: "your_super_secret_key"
```

### 3. Database Deployment

```yaml
# postgres.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: ai-shopping-concierge
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15
        env:
        - name: POSTGRES_DB
          value: ai_shopping_concierge
        - name: POSTGRES_USER
          value: postgres
        - name: POSTGRES_PASSWORD
          value: password
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
      volumes:
      - name: postgres-storage
        persistentVolumeClaim:
          claimName: postgres-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: postgres-service
  namespace: ai-shopping-concierge
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-pvc
  namespace: ai-shopping-concierge
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 50Gi
```

### 4. Application Deployment

```yaml
# ai-shopping-concierge.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-shopping-concierge
  namespace: ai-shopping-concierge
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ai-shopping-concierge
  template:
    metadata:
      labels:
        app: ai-shopping-concierge
    spec:
      containers:
      - name: ai-shopping-concierge
        image: your-registry/ai-shopping-concierge:latest
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          value: "production"
        envFrom:
        - secretRef:
            name: ai-shopping-concierge-secrets
        - configMapRef:
            name: ai-shopping-concierge-config
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: ai-shopping-concierge-service
  namespace: ai-shopping-concierge
spec:
  selector:
    app: ai-shopping-concierge
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP
```

### 5. Ingress

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ai-shopping-concierge-ingress
  namespace: ai-shopping-concierge
  annotations:
    kubernetes.io/ingress.class: "nginx"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  tls:
  - hosts:
    - your-domain.com
    secretName: ai-shopping-concierge-tls
  rules:
  - host: your-domain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: ai-shopping-concierge-service
            port:
              number: 8000
```

### 6. Deploy to Kubernetes

```bash
# Apply configurations
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f postgres.yaml
kubectl apply -f redis.yaml
kubectl apply -f ai-shopping-concierge.yaml
kubectl apply -f ingress.yaml

# Check status
kubectl get pods -n ai-shopping-concierge
kubectl get services -n ai-shopping-concierge
kubectl get ingress -n ai-shopping-concierge

# View logs
kubectl logs -f deployment/ai-shopping-concierge -n ai-shopping-concierge
```

## ☁️ Cloud Provider Deployments

### AWS (Amazon Web Services)

**Services Used:**
- **ECS/Fargate**: Container orchestration
- **RDS**: Managed PostgreSQL
- **ElastiCache**: Managed Redis
- **ALB**: Load balancer
- **Route 53**: DNS
- **CloudWatch**: Monitoring

**Deployment Script:**
```bash
# AWS CLI deployment script
aws ecs create-cluster --cluster-name ai-shopping-concierge

# Create task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json

# Create service
aws ecs create-service \
    --cluster ai-shopping-concierge \
    --service-name ai-shopping-concierge-service \
    --task-definition ai-shopping-concierge:1 \
    --desired-count 3 \
    --load-balancers file://load-balancers.json
```

### Google Cloud Platform

**Services Used:**
- **Cloud Run**: Serverless containers
- **Cloud SQL**: Managed PostgreSQL
- **Memorystore**: Managed Redis
- **Cloud Load Balancing**: Load balancer
- **Cloud DNS**: DNS
- **Cloud Monitoring**: Monitoring

**Deployment Script:**
```bash
# Build and push container
gcloud builds submit --tag gcr.io/PROJECT_ID/ai-shopping-concierge

# Deploy to Cloud Run
gcloud run deploy ai-shopping-concierge \
    --image gcr.io/PROJECT_ID/ai-shopping-concierge \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --set-env-vars="DATABASE_URL=...,REDIS_URL=..."
```

### Microsoft Azure

**Services Used:**
- **Container Instances**: Container hosting
- **Database for PostgreSQL**: Managed PostgreSQL
- **Cache for Redis**: Managed Redis
- **Application Gateway**: Load balancer
- **DNS Zone**: DNS
- **Monitor**: Monitoring

## 🔧 Configuration Management

### Environment-Specific Configs

**config/production.yaml:**
```yaml
app:
  debug: false
  workers: 4
  log_level: "INFO"

database:
  pool_size: 20
  max_overflow: 30
  echo: false

redis:
  max_connections: 100

rate_limiting:
  enabled: true
  requests_per_minute: 1000

monitoring:
  enabled: true
  sentry_dsn: "${SENTRY_DSN}"
  datadog_api_key: "${DATADOG_API_KEY}"
```

### Secrets Management

**Option 1: Kubernetes Secrets**
```bash
kubectl create secret generic api-keys \
    --from-literal=google-ai-key=your_key \
    --from-literal=whatsapp-token=your_token
```

**Option 2: HashiCorp Vault**
```bash
vault kv put secret/ai-shopping-concierge \
    google_ai_key=your_key \
    whatsapp_token=your_token
```

**Option 3: Cloud Provider Secret Managers**
```bash
# AWS Secrets Manager
aws secretsmanager create-secret \
    --name ai-shopping-concierge/api-keys \
    --secret-string '{"google_ai_key":"your_key"}'

# Google Secret Manager
gcloud secrets create google-ai-key --data-file=-
```

## 📊 Monitoring & Observability

### Health Checks

The application provides comprehensive health checks:

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-09-22T10:30:00Z",
  "services": {
    "database": "connected",
    "redis": "connected",
    "whatsapp": "active",
    "ai_engine": "ready"
  },
  "version": "1.0.0",
  "uptime": "72h35m12s"
}
```

### Metrics Collection

**Prometheus Configuration:**
```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'ai-shopping-concierge'
    static_configs:
      - targets: ['ai-shopping-concierge:8000']
    metrics_path: /metrics
```

**Key Metrics:**
- `http_requests_total`: Total HTTP requests
- `http_request_duration_seconds`: Request duration
- `active_conversations`: Active chat sessions
- `conversion_rate`: Purchase conversion rate
- `payment_success_rate`: Payment success rate

### Logging

**Structured Logging Configuration:**
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s',
            'datefmt': '%Y-%m-%dT%H:%M:%S'
        }
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/app/logs/app.log',
            'maxBytes': 50 * 1024 * 1024,  # 50MB
            'backupCount': 5,
            'formatter': 'json'
        }
    },
    'loggers': {
        'ai_shopping_agent': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True
        }
    }
}
```

### Alerting

**Sample Alerts:**
```yaml
# alerts.yml
groups:
  - name: ai-shopping-concierge
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"

      - alert: DatabaseConnectionDown
        expr: up{job="postgres"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Database connection is down"

      - alert: LowConversionRate
        expr: conversion_rate < 0.1
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Conversion rate is below 10%"
```

## 🔒 Security

### SSL/TLS Configuration

**Nginx SSL Configuration:**
```nginx
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384;
ssl_prefer_server_ciphers off;
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;
```

### Web Application Firewall

**CloudFlare Rules:**
```
# Block suspicious patterns
(http.request.uri.path contains "/admin" and ip.src ne YOUR_ADMIN_IP)
(http.request.method eq "POST" and rate(1m) > 30)
(http.user_agent contains "bot" and not http.user_agent contains "whatsapp")
```

### API Security

**Rate Limiting:**
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/v1/chat/message")
@limiter.limit("10/minute")
async def send_message(request: Request, ...):
    pass
```

**Input Validation:**
```python
from pydantic import BaseModel, validator

class MessageRequest(BaseModel):
    message: str
    session_id: str
    
    @validator('message')
    def validate_message(cls, v):
        if len(v) > 1000:
            raise ValueError('Message too long')
        return v.strip()
```

## 🚀 Performance Optimization

### Database Optimization

**PostgreSQL Configuration:**
```sql
-- Optimize for production workload
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET work_mem = '4MB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;

-- Create indexes for common queries
CREATE INDEX idx_conversations_customer_id ON conversations(customer_id);
CREATE INDEX idx_messages_session_id ON messages(session_id);
CREATE INDEX idx_orders_created_at ON orders(created_at);
```

### Redis Configuration

```redis
# redis.conf
maxmemory 1gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

### Application Performance

**Connection Pooling:**
```python
from sqlalchemy.pool import QueuePool

engine = create_async_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

**Caching Strategy:**
```python
import redis
from functools import wraps

redis_client = redis.Redis.from_url(REDIS_URL)

def cache_result(expiry=300):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            cached = redis_client.get(cache_key)
            
            if cached:
                return json.loads(cached)
            
            result = await func(*args, **kwargs)
            redis_client.setex(cache_key, expiry, json.dumps(result))
            return result
        return wrapper
    return decorator
```

## 🔄 CI/CD Pipeline

### GitHub Actions

**.github/workflows/deploy.yml:**
```yaml
name: Deploy AI Shopping Concierge

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-asyncio
    
    - name: Run tests
      run: pytest tests/ -v
    
    - name: Run security scan
      run: |
        pip install safety bandit
        safety check
        bandit -r ai_shopping_agent/

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Build Docker image
      run: |
        docker build -t ai-shopping-concierge:${{ github.sha }} .
        docker tag ai-shopping-concierge:${{ github.sha }} ai-shopping-concierge:latest
    
    - name: Push to registry
      run: |
        echo ${{ secrets.DOCKER_PASSWORD }} | docker login -u ${{ secrets.DOCKER_USERNAME }} --password-stdin
        docker push ai-shopping-concierge:${{ github.sha }}
        docker push ai-shopping-concierge:latest

  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    environment: staging
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Deploy to staging
      run: |
        # Deploy to staging environment
        ./scripts/automation/deploy.sh staging

  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment: production
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Deploy to production
      run: |
        # Deploy to production environment
        ./scripts/automation/deploy.sh production
```

## 📋 Post-Deployment Checklist

### Immediate (0-1 hour)

- [ ] Verify all services are running
- [ ] Check health endpoints return 200 OK
- [ ] Test WhatsApp webhook receives messages
- [ ] Verify database connectivity
- [ ] Check Redis cache is working
- [ ] Test payment processing with small amounts
- [ ] Verify SSL certificates are valid
- [ ] Check monitoring dashboards show green status

### Short-term (1-24 hours)

- [ ] Monitor error rates and response times
- [ ] Check log files for any warnings or errors
- [ ] Verify backup procedures are working
- [ ] Test auto-scaling if configured
- [ ] Check all integrations (WhatsApp, Google AI, payment processors)
- [ ] Verify rate limiting is working
- [ ] Test disaster recovery procedures

### Long-term (1-7 days)

- [ ] Monitor conversion rates and user satisfaction
- [ ] Review performance metrics and optimize if needed
- [ ] Check cost optimization opportunities
- [ ] Update documentation based on deployment experience
- [ ] Plan next release and improvements
- [ ] Review security logs and access patterns
- [ ] Optimize resource allocation based on usage patterns

## 🆘 Troubleshooting

### Common Issues

**Application Won't Start:**
```bash
# Check logs
docker-compose logs ai-shopping-concierge

# Check environment variables
docker-compose exec ai-shopping-concierge env | grep -E "(DATABASE|REDIS|GOOGLE)"

# Check dependencies
docker-compose exec ai-shopping-concierge pip list
```

**Database Connection Issues:**
```bash
# Test database connectivity
docker-compose exec ai-shopping-concierge python -c "
import asyncpg
import asyncio
async def test(): 
    conn = await asyncpg.connect('postgresql://...')
    print('Connected successfully')
    await conn.close()
asyncio.run(test())
"
```

**High Memory Usage:**
```bash
# Check memory usage
docker stats

# Optimize Python memory
export PYTHONMALLOC=malloc
export MALLOC_TRIM_THRESHOLD_=100000
```

**SSL Certificate Issues:**
```bash
# Check certificate validity
openssl x509 -in deployment/ssl/your-domain.crt -text -noout

# Test SSL connection
openssl s_client -connect your-domain.com:443
```

For additional support, check the troubleshooting guide or open an issue on GitHub.