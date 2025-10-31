# AI Shopping Concierge - Getting Started Guide

Welcome to the AI Shopping Concierge! This guide will help you get up and running with your intelligent shopping assistant built on the AP2 protocol.

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher
- Git
- Docker (optional, for containerized deployment)
- WhatsApp Business API account
- Google AI API key

### 1. Repository Setup

First, set up your repositories using our automated scripts:

```bash
# Clone the AP2 repository
git clone https://github.com/google-agentic-commerce/AP2.git
cd AP2

# Run the repository setup script
./scripts/repository-setup/1-fork-and-setup.sh your-github-username
```

Follow the manual steps to:
1. Fork the AP2 repository on GitHub
2. Create your AI Shopping Concierge repository
3. Set up authentication (SSH keys or tokens)

Then continue with:

```bash
# Complete the setup
./scripts/repository-setup/2-sync-and-verify.sh your-github-username
./scripts/repository-setup/3-migrate-code.sh
```

### 2. Configuration

Configure your API keys and settings:

```bash
cd ../ai-shopping-concierge-ap2
cp config/secrets.yaml.example config/secrets.yaml
```

Edit `config/secrets.yaml` with your actual API keys:

```yaml
# WhatsApp Business API
WHATSAPP_VERIFY_TOKEN: "your_verify_token_here"
WHATSAPP_ACCESS_TOKEN: "your_access_token_here"
WHATSAPP_PHONE_NUMBER_ID: "your_phone_number_id_here"

# Google AI
GOOGLE_AI_API_KEY: "your_google_ai_api_key_here"

# Database (for production)
DATABASE_URL: "postgresql+asyncpg://user:password@localhost/ai_shopping_concierge"

# Payment processors
AP2_MERCHANT_ID: "your_ap2_merchant_id"
STRIPE_API_KEY: "sk_test_your_stripe_key"
```

### 3. Installation

Install dependencies:

```bash
pip install -r requirements.txt
```

### 4. Run the Application

Start your AI Shopping Concierge:

```bash
python -m ai_shopping_agent
```

You should see:

```
🚀 Starting AI Shopping Concierge...
✅ AI Shopping Concierge started successfully!
💬 WhatsApp integration ready
🤖 AI curation engine ready
💰 Negotiation engine ready
💳 Checkout optimizer ready
📊 Analytics engine ready
```

## 🔧 Development Setup

### Using Docker (Recommended)

For a complete development environment:

```bash
# Start all services
docker-compose up --build

# Or for background running
docker-compose up -d --build
```

This starts:
- AI Shopping Concierge application (port 8000)
- PostgreSQL database (port 5432)
- Redis cache (port 6379)
- Nginx proxy (ports 80/443)

### Manual Setup

If you prefer manual setup:

1. **Database Setup**:
   ```bash
   # Install PostgreSQL
   # Create database
   createdb ai_shopping_concierge
   ```

2. **Redis Setup**:
   ```bash
   # Install Redis
   redis-server
   ```

3. **Environment Variables**:
   ```bash
   export DATABASE_URL="postgresql+asyncpg://user:password@localhost/ai_shopping_concierge"
   export REDIS_URL="redis://localhost:6379/0"
   ```

## 📱 WhatsApp Integration

### 1. Set up WhatsApp Business API

1. Go to [Meta for Developers](https://developers.facebook.com/)
2. Create a new app and add WhatsApp product
3. Get your access token and phone number ID
4. Configure webhook URL: `https://your-domain.com/webhook/whatsapp`

### 2. Configure Webhook

Your AI Shopping Concierge automatically handles WhatsApp webhooks at:
- **GET** `/webhook/whatsapp` - Webhook verification
- **POST** `/webhook/whatsapp` - Message processing

### 3. Test Integration

Send a message to your WhatsApp Business number:
```
Hi! I'm looking for a laptop
```

The AI should respond with product recommendations and start a conversation.

## 🤖 AI Features

### Product Curation

The AI automatically:
- Analyzes customer messages for intent and preferences
- Searches product catalogs for relevant items
- Provides personalized recommendations
- Learns from customer interactions

### Smart Negotiation

- Detects price sensitivity signals
- Offers dynamic discounts and bundles
- Creates urgency with limited-time offers
- Suggests alternatives and upgrades

### Payment Processing

- Auto-detects customer currency from location
- Converts prices in real-time
- Supports multiple payment methods (AP2, Stripe, PayPal)
- Handles international transactions with low fees

## 🔒 Security

### API Key Management

- Store sensitive keys in `config/secrets.yaml` (never commit this file)
- Use environment variables in production
- Rotate keys regularly

### Webhook Security

WhatsApp webhooks are automatically verified using your verify token.

### Payment Security

All payment processing uses:
- TLS encryption for data in transit
- Tokenized payment methods
- PCI DSS compliant processors
- Real-time fraud detection

## 📊 Monitoring

### Health Checks

Check application health:
```bash
curl http://localhost:8000/health
```

### Analytics Dashboard

View analytics at: `http://localhost:8000/analytics`

- Conversion rates
- Popular products
- Customer satisfaction
- Revenue metrics

### Logs

Application logs are available in:
- Console output (development)
- `logs/app.log` (production)
- Docker logs: `docker-compose logs ai-shopping-concierge`

## 🚀 Deployment

### Staging Deployment

```bash
./scripts/automation/deploy.sh staging
```

### Production Deployment

```bash
./scripts/automation/deploy.sh production
```

## 🔄 Maintenance

### Keep AP2 Core Updated

```bash
./scripts/automation/sync-upstream.sh
```

### Regular Maintenance

```bash
./scripts/automation/maintenance.sh
```

## 🆘 Troubleshooting

### Common Issues

**WhatsApp messages not received:**
- Check webhook URL configuration
- Verify verify token matches
- Check firewall/port settings

**AI not responding:**
- Verify Google AI API key
- Check API quotas and limits
- Review error logs

**Payment failures:**
- Check payment processor API keys
- Verify merchant account status
- Review transaction logs

**Database connection issues:**
- Check DATABASE_URL format
- Verify database server is running
- Check network connectivity

### Getting Help

1. Check the [API Reference](api-reference.md)
2. Review [troubleshooting guide](troubleshooting.md)
3. Check logs for error messages
4. Open an issue on GitHub

## 🎯 Next Steps

1. **Customize Product Catalog**: Add your products to the AI curation engine
2. **Configure Payment Methods**: Set up your preferred payment processors
3. **Brand the Experience**: Customize messages and UI to match your brand
4. **Scale Infrastructure**: Set up monitoring and auto-scaling for production
5. **Train the AI**: Improve recommendations with your specific product data

## 📚 Additional Resources

- [API Reference](api-reference.md)
- [Deployment Guide](deployment.md)
- [Troubleshooting](troubleshooting.md)
- [AP2 Protocol Documentation](https://github.com/google-agentic-commerce/AP2)
- [WhatsApp Business API Docs](https://developers.facebook.com/docs/whatsapp/)

Welcome to the future of AI-powered commerce! 🛍️🤖