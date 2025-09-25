# Autonomous Shopping Agent Sample

This sample demonstrates the enhanced IntentMandate capabilities for human-not-present flows in AP2. It shows how an AI agent can make purchases autonomously using session-based authorization and programmable spending rules.

## Overview

The autonomous shopping agent showcases:

- **Human-Not-Present Flow**: Agent operates without requiring user confirmation for each transaction
- **Session Authorization**: Cryptographic session credentials that enable time-bounded agent authority
- **Programmable Spending Rules**: Configurable constraints that automatically govern agent behavior
- **Agent DID Integration**: Decentralized identity for cryptographic agent verification
- **Real-time Validation**: Transaction evaluation against mandate criteria

## Key Features

### Session-Based Authorization

- Ephemeral session keys with limited lifespan
- Cryptographic binding between user, agent, and session
- Automatic expiration and revocation capabilities

### Spending Rules Framework

- Amount constraints (per-transaction and aggregate limits)
- Time constraints (business hours, specific time windows)
- Merchant allowlists/blocklists
- Product category restrictions
- Frequency limits to prevent abuse

### Autonomous Decision Making

- Real-time evaluation of purchase opportunities
- Automatic compliance with spending rules
- Transparent reasoning for approve/reject decisions

## Usage

### Basic Usage

```bash
python agent.py --intent "Buy running shoes under $200" --budget 200 --duration 24
```

### Advanced Usage with Constraints

```bash
python agent.py \
  --intent "Buy athletic gear for marathon training" \
  --budget 500 \
  --duration 48 \
  --merchants nike_official adidas_store \
  --categories footwear apparel accessories
```

### Command Line Options

- `--intent`: Natural language description of shopping intent (required)
- `--budget`: Maximum budget in specified currency (required)
- `--currency`: Currency code (default: USD)
- `--duration`: Mandate validity duration in hours (default: 24)
- `--merchants`: Space-separated list of allowed merchant IDs
- `--categories`: Space-separated list of allowed product categories

## Example Output

```text
🤖 Autonomous Shopping Agent Demo
==================================================
Agent DID: did:kite:1:autonomous_shopper_a1b2c3d4
User Wallet: 0x742d35Cc6634C0532925a3b844Bc9e7595f0fA7B

Created autonomous mandate a1b2c3d4-e5f6-7890-abcd-ef1234567890
Description: Buy running shoes under $200
Budget: 200.0 USD
Valid until: 2025-01-16T18:30:00+00:00

📋 Active Mandates:
  ID: a1b2c3d4...
  Description: Buy running shoes under $200
  Valid: True
  Rules: 3

🛍️ Evaluating Purchase Opportunities:
----------------------------------------

Evaluating: Nike Air Max Running Shoes
  Price: 150.0 USD
  Allowed: ✅
  Reason: Transaction approved
  ✅ Purchase completed: p1a2b3c4...

Evaluating: Expensive Designer Shoes
  Price: 500.0 USD
  Allowed: ❌
  Reason: Transaction rejected: Amount exceeds limit

Evaluating: Budget Running Shoes
  Price: 80.0 USD
  Allowed: ✅
  Reason: Transaction approved
  ✅ Purchase completed: p5e6f7g8...
```

## Architecture

### IntentMandate Configuration

The sample creates an IntentMandate with the following key features:

```python
IntentMandate(
    user_cart_confirmation_required=False,  # Enable autonomous mode
    natural_language_description=description,
    session_authorization=session_auth,     # Session-based auth
    spending_rules=spending_rules,          # Programmable constraints
    agent_did=self.agent_did,              # Agent identity
    delegation_depth=1,                     # No sub-delegation
    requires_consensus=False,               # Single agent decision
)
```

### Session Authorization

Session authorization includes:

- Ephemeral key pair for transaction signing
- Time-bounded validity (24 hours default)
- Specific intents with amount limits
- Replay protection with nonce tracking

### Spending Rules

The sample implements several rule types:

- **Amount Constraint**: Maximum budget enforcement
- **Time Constraint**: Business hours restriction
- **Merchant Constraint**: Allowlist of approved merchants
- **Category Constraint**: Product category restrictions

## Security Features

### Cryptographic Verification

- All transactions are cryptographically signed by session keys
- Agent identity is verifiable through DID resolution
- Session credentials cannot be forged or replayed

### Spending Limits

- Multiple layers of spending constraints
- Real-time rule evaluation before any transaction
- Automatic rejection of non-compliant purchases

### Time Boundaries

- Session expiration prevents indefinite agent authority
- Intent expiry limits the mandate lifecycle
- Time-based purchasing restrictions (e.g., business hours only)

### Revocation

- Sessions can be instantly revoked by users
- Mandate status checking before each transaction
- Emergency shutdown capabilities

## Integration with Existing AP2

This sample extends the existing AP2 framework while maintaining full backward compatibility:

- **Human-Present Flows**: Still supported with `user_cart_confirmation_required=True`
- **Existing Mandates**: Continue to work without modification
- **A2A Extension**: Compatible with existing A2A agent roles
- **Payment Methods**: Works with all existing payment method integrations

## Real-World Applications

This autonomous shopping capability enables use cases such as:

- **Subscription Management**: Automatic renewal and optimization
- **Price Monitoring**: Purchase when target prices are reached
- **Supply Chain**: Automated procurement within budget constraints
- **Event-Driven Purchases**: Buy tickets when they become available
- **Recurring Purchases**: Household essentials, business supplies

## Development Notes

### Mock Implementation

This sample uses mock implementations for:

- Cryptographic operations (session key generation, signing)
- DID resolution and verification
- Merchant interaction and payment processing

### Production Considerations

In a production environment, this would integrate with:

- Real cryptographic libraries for key management
- DID resolution networks
- Merchant APIs and payment processors
- Blockchain or trusted registries for session tracking
- Hardware security modules for key protection

### Testing

The sample includes built-in validation and can be extended with:

- Unit tests for spending rule evaluation
- Integration tests with mock merchants
- End-to-end scenarios with multiple agents
- Security testing for session management
