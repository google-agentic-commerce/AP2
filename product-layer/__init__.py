"""
AI Shopping Concierge - Product Layer
====================================

This directory contains the AI Shopping Concierge product layer built on top of the AP2 protocol.

Directory Structure:
-------------------
ai-shopping-agent/          # Core shopping agent modules
├── whatsapp-integration/   # WhatsApp Business API integration
├── ai-curation/           # AI-powered product curation
├── negotiation-engine/    # Smart negotiation and bundling
├── checkout-optimizer/    # Enhanced checkout with payment processing
├── analytics/             # Performance analytics and insights
├── common/               # Shared utilities and base classes
└── __main__.py          # Application entry point

Key Features:
------------
🤖 AI-Powered Curation: Smart product recommendations using Google AI
💬 Multi-Channel Chat: WhatsApp and web chat integration  
💰 Dynamic Negotiation: AI-driven pricing and bundle optimization
💳 Payment Processing: Automated payment with currency conversion
📊 Advanced Analytics: Real-time insights and performance tracking

Integration with AP2:
-------------------
The product layer uses AP2 as a submodule for:
- Core payment infrastructure
- Mandate management
- Transaction security
- Protocol compliance

This ensures we stay synced with upstream AP2 improvements while building
innovative product features on top.

Usage:
------
1. Set up your product repository (see scripts/repository-setup/)
2. Configure API keys in config/secrets.yaml  
3. Run: python -m ai_shopping_agent
4. Your AI Shopping Concierge will be ready!

For detailed setup instructions, see the repository setup scripts in:
scripts/repository-setup/
"""

# Version information
__version__ = "1.0.0"
__product__ = "AI Shopping Concierge"
__protocol__ = "AP2"