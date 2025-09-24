# Autonomous Agent Flows (Human-Not-Present)

Agent Payments Protocol (AP2) supports autonomous agent transactions where AI agents can execute purchases without requiring user confirmation for each transaction. This capability is essential for the emerging agent economy, where agents need to operate independently while maintaining security and user control.

## Overview

Human-not-present flows enable:

- **Autonomous Transactions**: Agents can complete purchases based on pre-authorized intents
- **Programmable Constraints**: Users define spending rules that agents must respect
- **Session-Based Security**: Time-bounded, cryptographically secured agent authority
- **Real-Time Revocation**: Users can instantly revoke agent permissions
- **Transparent Accountability**: Full audit trail of all agent decisions and actions

## Core Components

### Enhanced IntentMandate

The `IntentMandate` has been extended with new fields specifically for autonomous operations:

```python
class IntentMandate(BaseModel):
    # Existing fields for human-present flows
    user_cart_confirmation_required: bool = True
    natural_language_description: str
    merchants: Optional[list[str]] = None
    skus: Optional[list[str]] = None
    requires_refundability: Optional[bool] = False
    intent_expiry: str

    # New fields for human-not-present flows
    session_authorization: Optional[SessionAuthorization] = None
    spending_rules: SpendingRuleSet = Field(default_factory=SpendingRuleSet)
    agent_did: Optional[str] = None
    revocation_registry_uri: Optional[str] = None
    delegation_depth: int = 1
    requires_consensus: bool = False
```

### Session Authorization

Session authorization provides cryptographic proof that a user has delegated specific authority to an agent:

```python
class SessionAuthorization(BaseModel):
    session_id: str
    agent_did: str
    user_wallet_address: str
    auth_type: SessionAuthType
    credential: SessionCredential
    intents: list[SessionIntent]
    session_expiry: str
    status: SessionStatus
    # ... additional fields
```

Key features:

- **Ephemeral Keys**: Session keys are randomly generated and expire automatically
- **Scope Limitation**: Each session defines specific authorized actions and limits
- **Replay Protection**: Nonce-based protection against transaction replay attacks
- **Revocation Support**: Sessions can be instantly invalidated

### Programmable Spending Rules

Spending rules provide fine-grained control over agent behavior:

#### Amount Constraints

```python
AmountConstraint(
    limit_amount=PaymentCurrencyAmount(currency="USD", value=500.0),
    operator=ConstraintOperator.LESS_THAN_OR_EQUAL,
    time_window_hours=24,  # Daily limit
)
```

#### Time Constraints

```python
TimeConstraint(
    allowed_hours=[9, 10, 11, 12, 13, 14, 15, 16, 17],  # Business hours
    allowed_days_of_week=[0, 1, 2, 3, 4],  # Monday-Friday
)
```

#### Merchant Constraints

```python
MerchantConstraint(
    merchant_ids=["amazon", "bestbuy", "target"],
    constraint_type="allow",  # Whitelist
    match_type="exact",
)
```

#### Category Constraints

```python
CategoryConstraint(
    categories=["electronics", "books", "office_supplies"],
    constraint_type="allow",
    category_system="standard_classification",
)
```

#### Frequency Constraints

```python
FrequencyConstraint(
    max_transactions=5,
    time_window_hours=24,
    merchant_specific=True,  # Per-merchant limit
)
```

## Implementation Flow

### 1. User Authorization

The user creates an autonomous mandate by:

1. **Defining Intent**: Natural language description of what the agent should accomplish
2. **Setting Spending Rules**: Configurable constraints that define acceptable behavior
3. **Creating Session**: Generating ephemeral credentials for the agent
4. **Signing Mandate**: Cryptographically authorizing the agent's authority

```python
# Example: Create autonomous shopping mandate
mandate = IntentMandate(
    user_cart_confirmation_required=False,  # Enable autonomy
    natural_language_description="Buy office supplies under $200 monthly",
    session_authorization=session_auth,
    spending_rules=spending_rules,
    agent_did="did:kite:1:office_manager_agent",
    intent_expiry=(datetime.now() + timedelta(days=30)).isoformat(),
)
```

### 2. Agent Operation

When the agent identifies a purchase opportunity:

1. **Mandate Validation**: Verify the mandate is still valid and active
2. **Rule Evaluation**: Check all spending rules against the proposed transaction
3. **Session Verification**: Validate session credentials and expiry
4. **Transaction Execution**: If approved, execute the purchase autonomously
5. **Audit Logging**: Record all decisions and actions for transparency

```python
# Example: Agent evaluates purchase opportunity
validator = IntentMandateValidator()
result = validator.validate_transaction_against_mandate(
    mandate=mandate,
    transaction_amount=PaymentCurrencyAmount(currency="USD", value=89.99),
    merchant_id="office_depot",
    categories=["office_supplies"],
)

if result.is_valid:
    # Execute autonomous purchase
    purchase_result = agent.execute_purchase(...)
```

### 3. Real-Time Oversight

Users maintain control through:

- **Live Monitoring**: Real-time visibility into agent decisions
- **Instant Revocation**: Ability to immediately stop agent activity
- **Rule Updates**: Dynamic modification of spending constraints
- **Session Management**: Control over session renewal and expiration

## Security Model

### Cryptographic Chain of Trust

1. **User → Agent Binding**: DID-based verification of agent authorization
2. **Agent → Session Binding**: Cryptographic link between agent identity and session
3. **Session → Transaction Binding**: Each transaction signed with session credentials
4. **Non-Repudiation**: All actions are cryptographically attributable

### Defense in Depth

- **Session Expiry**: Automatic termination of agent authority
- **Spending Limits**: Multiple layers of amount constraints
- **Time Boundaries**: Restrictions on when agents can operate
- **Merchant Controls**: Allowlists and blocklists for transaction destinations
- **Frequency Limits**: Prevention of transaction spam or abuse

### Revocation Mechanisms

- **Immediate Revocation**: Users can instantly invalidate sessions
- **Revocation Registry**: Centralized or distributed revocation status
- **Grace Periods**: Configurable delays for transaction completion
- **Emergency Procedures**: Rapid response for compromised sessions

## Best Practices

### For Users

1. **Start Conservative**: Begin with low spending limits and short durations
2. **Regular Review**: Monitor agent activity and adjust rules as needed
3. **Merchant Vetting**: Use allowlists for trusted merchants initially
4. **Time Restrictions**: Limit agent activity to appropriate time windows
5. **Emergency Planning**: Know how to quickly revoke agent access

### For Agent Developers

1. **Transparent Decisions**: Log all decision factors and reasoning
2. **Rule Compliance**: Always validate against spending rules before acting
3. **Error Handling**: Gracefully handle rule violations and session expiry
4. **User Communication**: Provide clear feedback on agent actions
5. **Security Updates**: Keep session credentials secure and rotate regularly

### For Merchants

1. **Agent Detection**: Recognize and appropriately handle agent transactions
2. **Verification**: Validate session credentials and mandate authorization
3. **Rate Limiting**: Implement appropriate limits for agent interactions
4. **Dispute Handling**: Provide clear processes for agent-related issues
5. **Integration Testing**: Test thoroughly with various agent implementations

## Integration Examples

### E-commerce Platform

```python
class EcommercePlatform:
    def process_agent_order(self, order_request):
        # Validate agent mandate
        mandate_valid = self.validate_mandate(order_request.mandate)
        if not mandate_valid:
            return {"error": "Invalid mandate"}

        # Check spending rules
        rules_passed = self.evaluate_spending_rules(
            order_request.mandate.spending_rules,
            order_request.transaction_context
        )
        if not rules_passed:
            return {"error": "Spending rules violation"}

        # Process order autonomously
        return self.execute_order(order_request)
```

### Subscription Service

```python
class SubscriptionService:
    def auto_renewal_check(self, user_id):
        # Find active renewal mandate
        mandate = self.get_renewal_mandate(user_id)
        if not mandate or mandate.user_cart_confirmation_required:
            return  # Manual renewal required

        # Validate session authorization
        if not mandate.session_authorization.is_valid():
            self.notify_user_renewal_failed(user_id, "Session expired")
            return

        # Execute autonomous renewal
        self.process_renewal(user_id, mandate)
```

### Investment Platform

```python
class InvestmentPlatform:
    def evaluate_investment_opportunity(self, portfolio_agent_mandate):
        # Check investment rules
        rules_result = portfolio_agent_mandate.spending_rules.evaluate_transaction({
            "amount": self.opportunity.amount,
            "merchant_id": self.opportunity.broker_id,
            "categories": ["investments", self.opportunity.asset_class],
        })

        if rules_result["allowed"]:
            # Execute autonomous investment
            return self.place_order(self.opportunity)
```

## Compliance and Regulatory Considerations

### Financial Regulations

- **Know Your Customer (KYC)**: Agent transactions must maintain user identity verification
- **Anti-Money Laundering (AML)**: Autonomous transactions require appropriate monitoring
- **Consumer Protection**: Users must understand and consent to agent authority
- **Liability Framework**: Clear attribution of responsibility for agent actions

### Data Protection

- **Privacy by Design**: Minimize personal data exposure in agent transactions
- **Consent Management**: Explicit consent for agent access to payment methods
- **Data Retention**: Appropriate retention periods for transaction logs
- **Cross-Border**: Compliance with international data protection regulations

### Audit Requirements

- **Transaction Logging**: Complete audit trail of all agent decisions
- **Decision Explainability**: Clear reasoning for each autonomous action
- **Performance Monitoring**: Tracking of agent success rates and error patterns
- **Compliance Reporting**: Regular reports on agent behavior and compliance

## Future Enhancements

### Advanced Capabilities

- **Multi-Agent Coordination**: Agents collaborating on complex transactions
- **Dynamic Rule Learning**: AI-powered optimization of spending rules
- **Context Awareness**: Agents adapting behavior based on external factors
- **Cross-Platform Integration**: Seamless operation across multiple merchants

### Enhanced Security

- **Hardware Attestation**: Secure element integration for key protection
- **Biometric Confirmation**: Additional user verification for high-value transactions
- **Behavioral Analysis**: ML-based detection of anomalous agent behavior
- **Zero-Knowledge Proofs**: Privacy-preserving verification of agent authority

### Scalability Improvements

- **Batch Processing**: Efficient handling of multiple simultaneous transactions
- **Caching Strategies**: Optimized rule evaluation and session management
- **Distributed Systems**: Horizontal scaling for high-volume agent platforms
- **Performance Optimization**: Sub-second response times for real-time commerce

This autonomous agent framework positions AP2 as the foundational protocol for the next generation of AI-driven commerce, enabling sophisticated agent behavior while maintaining the security, transparency, and user control that make digital payments trustworthy.
