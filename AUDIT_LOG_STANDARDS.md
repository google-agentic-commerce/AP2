# Community-Proposed Audit Log Standards for AP2 Mandates

> **Note**: This document presents community-driven research and proposed standards for mandate audit logging in the Agent Payments Protocol (AP2). These proposals are based on industry best practices and analysis of the AP2 codebase. This work addresses [Issue #46](https://github.com/google/ap2/issues/46) and is subject to review and approval by the AP2 protocol maintainers.

## Executive Summary

The Agent Payments Protocol requires robust audit logging to ensure accountability, compliance, and trust in agentic payment systems. This document proposes standardized audit log formats and error schemas for mandate enforcement, based on analysis of industry standards including PCI DSS, SOX compliance requirements, and ISO 20022 messaging.

## Overview

Currently, AP2 demonstrates mandate types and payment flows but lacks standardized audit logging and error reporting for mandate-related actions. Without consistent logging standards, developers implement varying approaches, potentially weakening trust guarantees and compliance capabilities.

This document proposes:
- **Standardized audit log schema** for mandate lifecycle events
- **Comprehensive error taxonomy** for mandate enforcement scenarios  
- **Privacy-preserving patterns** for cross-participant audit verification
- **Implementation guidance** with practical examples

## Industry Standards Analysis

### Payment Industry Requirements

#### PCI DSS (Payment Card Industry Data Security Standard)
- **Requirement 10**: Track and monitor all access to network resources and cardholder data
- **Log Elements**: User identification, type of event, date/time, success/failure, origination of event, identity of affected data/system/resource
- **Retention**: Minimum 1 year, with 3 months immediately available for analysis

#### SOX (Sarbanes-Oxley Act) Compliance  
- **Section 404**: Internal controls over financial reporting
- **Requirements**: Detailed transaction logs, segregation of duties tracking, change management audit trails
- **Focus**: Non-repudiation, tamper-evidence, chronological integrity

#### ISO 20022 Financial Messaging
- **Message Structure**: Standardized business components for payment messages
- **Audit Requirements**: Transaction traceability, error reporting, status tracking
- **Components**: Message identification, timestamps, participant identification, transaction details

### Existing Payment Protocol Patterns

#### Swift MT Messages
- **Format**: Structured message blocks with mandatory fields
- **Audit Trail**: Each message transformation logged with timestamps and participant details
- **Error Codes**: Standardized reject codes (e.g., MT195, MT196)

#### ACH (Automated Clearing House)
- **Audit Logs**: Batch-level and transaction-level tracking
- **Error Taxonomy**: Return codes (R01-R85) with specific violation categories
- **Settlement**: End-to-end transaction lifecycle logging

#### Real-Time Payment Systems (FedNow, RTP)
- **Immutable Logs**: Cryptographically secured audit trails
- **Real-time Monitoring**: Immediate fraud detection and compliance checking
- **Participant Accountability**: Clear attribution and responsibility tracking

## AP2 Mandate Analysis

### Current Mandate Types

Based on codebase analysis, AP2 defines three core mandate types:

#### 1. Intent Mandate
```python
class IntentMandate(BaseModel):
    user_cart_confirmation_required: bool
    natural_language_description: str
    merchants: Optional[list[str]]
    skus: Optional[list[str]]
    requires_refundability: Optional[bool]
    intent_expiry: str
```

**Audit Touchpoints:**
- Creation with user consent
- Merchant acceptance/rejection
- Expiration handling
- Constraint violation detection

#### 2. Cart Mandate  
```python
class CartMandate(BaseModel):
    contents: CartContents
    merchant_authorization: Optional[str]  # JWT signature
```

**Audit Touchpoints:**
- Cart content finalization
- Merchant signing/authorization
- Price/inventory changes
- User confirmation required events

#### 3. Payment Mandate
```python
class PaymentMandate(BaseModel):
    payment_mandate_contents: PaymentMandateContents
    user_authorization: Optional[str]  # Verifiable credential
```

**Audit Touchpoints:**
- Payment authorization
- Network/issuer submission
- Challenge/response flows
- Transaction completion/failure

### Current Error Handling Patterns

Analysis of the codebase reveals ad-hoc error handling:

```python
# From merchant_agent/tools.py
async def _fail_task(updater: TaskUpdater, error_text: str) -> None:
    """A helper function to fail a task with a given error message."""
    error_message = updater.new_agent_message(
        parts=[Part(root=TextPart(text=error_text))]
    )
    await updater.failed(message=error_message)

# Example error messages found:
- "Missing payment_mandate."
- "Missing risk_data."
- "Failed to validate shopping agent."
- "Challenge response incorrect."
```

**Gaps Identified:**
- No structured error codes
- Inconsistent error messaging
- Limited categorization
- No severity levels
- Missing compliance context

## Proposed Audit Log Schema

### Core Audit Event Structure

```json
{
  "audit_log_version": "1.0",
  "event_id": "uuid-v4",
  "timestamp": "2025-10-09T14:30:00.000Z",
  "event_type": "mandate_lifecycle_event",
  "mandate_type": "payment_mandate",
  "mandate_id": "mandate_12345",
  "participant_id": "merchant_agent_001",
  "participant_type": "merchant_agent",
  "session_id": "session_abc123",
  "transaction_id": "txn_def456",
  "event_category": "mandate_creation",
  "event_action": "user_authorization_completed",
  "event_result": "success",
  "event_details": {
    "mandate_hash": "sha256_hash_of_mandate_contents",
    "user_signature_verification": "valid",
    "compliance_flags": ["pci_dss", "sox_compliant"],
    "risk_score": 0.15,
    "geographic_location": "US-CA",
    "device_fingerprint": "device_hash_xyz"
  },
  "security_context": {
    "encryption_algorithm": "AES-256-GCM",
    "digital_signature": "jwt_signature_of_log_entry",
    "integrity_hash": "sha256_of_entire_log_entry"
  },
  "privacy_metadata": {
    "pii_redacted": true,
    "data_classification": "financial_transaction",
    "retention_period_days": 2555,
    "shared_with": ["issuer", "network"]
  }
}
```

### Mandate Lifecycle Events

#### Event Categories

1. **mandate_creation**
   - `intent_submitted` - User submits purchase intent
   - `intent_validated` - Shopping agent validates intent constraints
   - `cart_finalized` - Merchant finalizes cart contents
   - `cart_signed` - Merchant cryptographically signs cart
   - `payment_authorized` - User authorizes payment details

2. **mandate_enforcement**
   - `constraint_checked` - Validation of mandate constraints
   - `price_verification` - Price compliance checking
   - `merchant_verification` - Allowed merchant validation
   - `expiry_checked` - Mandate expiration validation
   - `refund_policy_verified` - Refundability requirement check

3. **mandate_execution**
   - `payment_initiated` - Payment process started
   - `credentials_requested` - Payment credentials retrieved
   - `network_submitted` - Transaction sent to payment network
   - `challenge_issued` - Additional authentication required
   - `challenge_responded` - User responds to challenge
   - `payment_completed` - Transaction successfully processed

4. **mandate_violation**
   - `price_exceeded` - Amount exceeds mandate limits
   - `merchant_unauthorized` - Non-allowed merchant attempted
   - `mandate_expired` - Attempt to use expired mandate
   - `insufficient_funds` - Payment method declined
   - `user_revoked` - User cancels/revokes mandate
   - `fraud_detected` - Suspicious activity identified

5. **mandate_resolution**
   - `payment_confirmed` - Final settlement confirmation
   - `refund_initiated` - Refund process started
   - `dispute_opened` - Chargeback or dispute filed
   - `audit_requested` - External audit or investigation

### Event Details Schema by Category

#### Mandate Creation Events
```json
{
  "event_details": {
    "mandate_version": "1.0",
    "user_consent_method": "digital_signature|biometric|pin",
    "consent_timestamp": "2025-10-09T14:25:00.000Z",
    "merchant_details": {
      "merchant_id": "merch_12345",
      "merchant_name": "Example Store",
      "mcc_code": "5411"
    },
    "payment_method": {
      "method_type": "card|bank_transfer|digital_wallet",
      "last_four": "1234",
      "network": "visa|mastercard|ach"
    },
    "amount_details": {
      "currency": "USD",
      "amount": 129.99,
      "tax_amount": 10.40,
      "shipping_amount": 5.99
    },
    "geographic_context": {
      "billing_country": "US",
      "shipping_country": "US",
      "transaction_country": "US"
    }
  }
}
```

#### Mandate Violation Events
```json
{
  "event_details": {
    "violation_type": "price_exceeded|merchant_unauthorized|mandate_expired|fraud_detected",
    "violation_severity": "low|medium|high|critical",
    "expected_value": "original_constraint_value",
    "actual_value": "attempted_value",
    "violation_delta": "difference_amount_or_description",
    "enforcement_action": "blocked|flagged|challenged|allowed_with_warning",
    "risk_factors": [
      "unusual_merchant",
      "high_amount",
      "geographic_anomaly",
      "velocity_concern"
    ],
    "compliance_impact": {
      "pci_dss_violation": false,
      "sox_reporting_required": true,
      "regulatory_notification": false
    }
  }
}
```

#### Payment Execution Events
```json
{
  "event_details": {
    "payment_processor": "processor_name",
    "network_reference": "network_txn_id",
    "authorization_code": "auth_123456",
    "processing_time_ms": 1250,
    "3ds_challenge": {
      "challenge_required": true,
      "challenge_type": "otp|biometric|password",
      "challenge_result": "success|failure|timeout"
    },
    "issuer_response": {
      "response_code": "00",
      "response_description": "Approved",
      "avs_result": "Y",
      "cvv_result": "M"
    },
    "settlement_details": {
      "settlement_date": "2025-10-10",
      "batch_id": "batch_789",
      "clearing_network": "visa_net"
    }
  }
}
```

## Proposed Error Schema

### Error Code Structure

Format: `AP2-{Category}{SubCategory}{ErrorNumber}`

#### Categories:
- **MND**: Mandate-related errors
- **PAY**: Payment processing errors  
- **AUT**: Authentication/authorization errors
- **VAL**: Validation errors
- **NET**: Network/communication errors
- **SYS**: System/technical errors

### Mandate Error Codes (MND)

#### Creation Errors (MND-CR-xxx)
- `AP2-MND-CR-001`: Invalid mandate format
- `AP2-MND-CR-002`: Missing required user consent
- `AP2-MND-CR-003`: Merchant signature validation failed
- `AP2-MND-CR-004`: Mandate expiry date invalid
- `AP2-MND-CR-005`: Amount limits exceeded during creation

#### Enforcement Errors (MND-EN-xxx)  
- `AP2-MND-EN-001`: Price constraint violation
- `AP2-MND-EN-002`: Unauthorized merchant attempted
- `AP2-MND-EN-003`: Mandate has expired
- `AP2-MND-EN-004`: SKU not permitted by mandate
- `AP2-MND-EN-005`: Refundability requirement not met
- `AP2-MND-EN-006`: Geographic restriction violation
- `AP2-MND-EN-007`: Velocity limit exceeded
- `AP2-MND-EN-008`: User consent revoked

#### Execution Errors (MND-EX-xxx)
- `AP2-MND-EX-001`: Payment method unavailable
- `AP2-MND-EX-002`: Insufficient funds
- `AP2-MND-EX-003`: Network timeout during processing
- `AP2-MND-EX-004`: Challenge response failed
- `AP2-MND-EX-005`: Issuer declined transaction
- `AP2-MND-EX-006`: Fraud detection triggered
- `AP2-MND-EX-007`: Settlement failed

### Error Response Format

```json
{
  "error_code": "AP2-MND-EN-001",
  "error_category": "mandate_enforcement",
  "error_type": "price_constraint_violation",
  "severity": "high",
  "timestamp": "2025-10-09T14:30:00.000Z",
  "message": "Transaction amount exceeds mandate maximum",
  "details": {
    "mandate_id": "mandate_12345",
    "constraint_type": "maximum_amount",
    "mandate_limit": 100.00,
    "attempted_amount": 129.99,
    "violation_amount": 29.99,
    "currency": "USD"
  },
  "suggested_actions": [
    "Reduce transaction amount to within mandate limits",
    "Request new mandate with higher limits",
    "Split transaction into multiple smaller amounts"
  ],
  "compliance_context": {
    "requires_reporting": true,
    "retention_required": true,
    "audit_trail_needed": true
  },
  "technical_context": {
    "validation_rule": "amount <= mandate.maximum_amount",
    "code_location": "mandate_validator.py:line_45",
    "correlation_id": "corr_abc123"
  }
}
```

### Error Severity Levels

#### Critical (System/Security)
- Authentication failures
- Cryptographic signature failures  
- Data integrity violations
- Security policy violations

#### High (Business/Compliance)
- Mandate constraint violations
- Regulatory compliance failures
- Fraud detection triggers
- Payment processing failures

#### Medium (Operational)
- Network timeouts
- Temporary service unavailability
- Configuration issues
- Performance degradation

#### Low (Informational)
- Validation warnings
- Best practice violations
- Performance metrics
- Usage statistics

## Privacy-Preserving Log Sharing

### Cross-Participant Verification Model

#### Selective Disclosure Pattern
```json
{
  "shared_log_entry": {
    "event_id": "public_event_identifier",
    "timestamp": "2025-10-09T14:30:00.000Z",
    "event_hash": "sha256_hash_of_full_event",
    "participant_signature": "digital_signature_of_participant",
    "disclosed_fields": {
      "mandate_id": "mandate_12345",
      "event_category": "mandate_execution",
      "event_result": "success",
      "amount": "REDACTED",
      "payment_method": "REDACTED",
      "user_identity": "REDACTED"
    },
    "verification_proofs": {
      "amount_range_proof": "zero_knowledge_proof_amount_within_limits",
      "merchant_authorization": "proof_merchant_is_authorized",
      "user_consent": "proof_user_provided_valid_consent"
    }
  }
}
```

#### Zero-Knowledge Audit Proofs

**Range Proofs**: Prove amount is within mandate limits without revealing exact amount
**Membership Proofs**: Prove merchant is in allowed list without revealing list
**Timestamp Proofs**: Prove transaction occurred within mandate validity without revealing exact time

### Multi-Party Log Verification

#### Distributed Audit Trail
```json
{
  "distributed_log_entry": {
    "event_chain_id": "chain_abc123",
    "previous_event_hash": "sha256_of_previous_event",
    "participant_contributions": {
      "shopping_agent": {
        "event_fragment": "shopping_agent_perspective",
        "signature": "shopping_agent_signature"
      },
      "merchant_agent": {
        "event_fragment": "merchant_agent_perspective", 
        "signature": "merchant_agent_signature"
      },
      "credentials_provider": {
        "event_fragment": "credentials_provider_perspective",
        "signature": "credentials_provider_signature"
      }
    },
    "consensus_proof": "multi_party_agreement_signature"
  }
}
```

## Implementation Guidance

### Agent Implementation Patterns

#### Shopping Agent Logging
```python
from datetime import datetime
from typing import Dict, Any
import uuid
import hashlib
import json

class AP2AuditLogger:
    def __init__(self, participant_id: str, participant_type: str):
        self.participant_id = participant_id
        self.participant_type = participant_type
    
    def log_mandate_event(
        self,
        event_category: str,
        event_action: str,
        mandate_id: str,
        mandate_type: str,
        event_result: str = "success",
        event_details: Dict[str, Any] = None,
        session_id: str = None,
        transaction_id: str = None
    ) -> Dict[str, Any]:
        """
        Creates a standardized audit log entry for mandate events.
        """
        event_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        audit_entry = {
            "audit_log_version": "1.0",
            "event_id": event_id,
            "timestamp": timestamp,
            "event_type": "mandate_lifecycle_event",
            "mandate_type": mandate_type,
            "mandate_id": mandate_id,
            "participant_id": self.participant_id,
            "participant_type": self.participant_type,
            "session_id": session_id,
            "transaction_id": transaction_id,
            "event_category": event_category,
            "event_action": event_action,
            "event_result": event_result,
            "event_details": event_details or {},
            "security_context": self._create_security_context(event_id, timestamp),
            "privacy_metadata": self._create_privacy_metadata()
        }
        
        # Add integrity hash
        audit_entry["security_context"]["integrity_hash"] = self._compute_integrity_hash(audit_entry)
        
        # Store and/or transmit the audit entry
        self._store_audit_entry(audit_entry)
        
        return audit_entry
    
    def log_mandate_violation(
        self,
        violation_type: str,
        mandate_id: str,
        expected_value: Any,
        actual_value: Any,
        severity: str = "medium",
        enforcement_action: str = "blocked"
    ) -> Dict[str, Any]:
        """
        Logs mandate constraint violations with detailed context.
        """
        event_details = {
            "violation_type": violation_type,
            "violation_severity": severity,
            "expected_value": str(expected_value),
            "actual_value": str(actual_value),
            "enforcement_action": enforcement_action,
            "compliance_impact": self._assess_compliance_impact(violation_type, severity)
        }
        
        return self.log_mandate_event(
            event_category="mandate_violation",
            event_action=violation_type,
            mandate_id=mandate_id,
            mandate_type="intent_mandate",  # or derived from context
            event_result="violation_detected",
            event_details=event_details
        )
    
    def _create_security_context(self, event_id: str, timestamp: str) -> Dict[str, Any]:
        return {
            "encryption_algorithm": "AES-256-GCM",
            "digital_signature": self._sign_event(event_id, timestamp),
            # integrity_hash added after audit entry completion
        }
    
    def _create_privacy_metadata(self) -> Dict[str, Any]:
        return {
            "pii_redacted": True,
            "data_classification": "financial_transaction",
            "retention_period_days": 2555,  # 7 years for financial records
            "shared_with": ["issuer", "network"]
        }
    
    def _compute_integrity_hash(self, audit_entry: Dict[str, Any]) -> str:
        # Create a copy without the integrity_hash field
        entry_copy = audit_entry.copy()
        if "security_context" in entry_copy and "integrity_hash" in entry_copy["security_context"]:
            del entry_copy["security_context"]["integrity_hash"]
        
        # Compute hash of canonical JSON representation
        canonical_json = json.dumps(entry_copy, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical_json.encode()).hexdigest()
    
    def _sign_event(self, event_id: str, timestamp: str) -> str:
        # Placeholder for digital signature implementation
        # In production, would use agent's private key
        return f"signature_of_{event_id}_{timestamp}"
    
    def _assess_compliance_impact(self, violation_type: str, severity: str) -> Dict[str, bool]:
        # Determine compliance reporting requirements
        return {
            "pci_dss_violation": violation_type in ["payment_data_exposure", "unauthorized_access"],
            "sox_reporting_required": severity in ["high", "critical"],
            "regulatory_notification": severity == "critical"
        }
    
    def _store_audit_entry(self, audit_entry: Dict[str, Any]) -> None:
        # Implementation would store to secure audit log storage
        # Options: secure database, immutable ledger, encrypted file system
        pass

# Usage examples in existing AP2 agents:

class ShoppingAgentWithAudit:
    def __init__(self):
        self.audit_logger = AP2AuditLogger("shopping_agent_001", "shopping_agent")
    
    async def create_intent_mandate(self, user_intent: str, constraints: Dict[str, Any]) -> IntentMandate:
        # Create intent mandate
        intent_mandate = IntentMandate(
            natural_language_description=user_intent,
            intent_expiry=constraints.get("expiry"),
            # ... other fields
        )
        
        # Log mandate creation
        self.audit_logger.log_mandate_event(
            event_category="mandate_creation",
            event_action="intent_submitted",
            mandate_id=str(uuid.uuid4()),  # Generated mandate ID
            mandate_type="intent_mandate",
            event_details={
                "user_intent": user_intent,
                "constraints": constraints,
                "user_consent_method": "digital_signature"
            }
        )
        
        return intent_mandate
    
    async def validate_merchant(self, merchant_id: str, allowed_merchants: List[str]) -> bool:
        is_valid = merchant_id in allowed_merchants
        
        if not is_valid:
            self.audit_logger.log_mandate_violation(
                violation_type="merchant_unauthorized",
                mandate_id="current_mandate_id",
                expected_value=allowed_merchants,
                actual_value=merchant_id,
                severity="high",
                enforcement_action="blocked"
            )
        
        return is_valid
```

#### Error Handling Integration
```python
class AP2ErrorHandler:
    def __init__(self, audit_logger: AP2AuditLogger):
        self.audit_logger = audit_logger
    
    def create_error_response(
        self,
        error_code: str,
        error_category: str,
        error_type: str,
        severity: str,
        message: str,
        details: Dict[str, Any] = None,
        mandate_id: str = None
    ) -> Dict[str, Any]:
        """
        Creates standardized error response with audit logging.
        """
        error_response = {
            "error_code": error_code,
            "error_category": error_category,
            "error_type": error_type,
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "message": message,
            "details": details or {},
            "suggested_actions": self._get_suggested_actions(error_code),
            "compliance_context": self._get_compliance_context(severity),
            "technical_context": {
                "correlation_id": str(uuid.uuid4())
            }
        }
        
        # Log the error event
        if mandate_id:
            self.audit_logger.log_mandate_event(
                event_category="mandate_violation",
                event_action=error_type,
                mandate_id=mandate_id,
                mandate_type="derived_from_context",
                event_result="error",
                event_details={
                    "error_code": error_code,
                    "error_message": message,
                    "error_severity": severity
                }
            )
        
        return error_response
    
    def _get_suggested_actions(self, error_code: str) -> List[str]:
        suggestions_map = {
            "AP2-MND-EN-001": [
                "Reduce transaction amount to within mandate limits",
                "Request new mandate with higher limits",
                "Split transaction into multiple smaller amounts"
            ],
            "AP2-MND-EN-002": [
                "Use an authorized merchant from the mandate",
                "Request new mandate that includes this merchant",
                "Contact user for mandate modification"
            ],
            "AP2-MND-EN-003": [
                "Request new mandate with updated expiry",
                "Use existing valid mandate if available",
                "Contact user for mandate renewal"
            ]
        }
        return suggestions_map.get(error_code, ["Contact support for assistance"])
    
    def _get_compliance_context(self, severity: str) -> Dict[str, bool]:
        return {
            "requires_reporting": severity in ["high", "critical"],
            "retention_required": True,
            "audit_trail_needed": True
        }

# Integration with existing agent code:
async def _fail_task_with_audit(
    updater: TaskUpdater, 
    error_code: str,
    error_message: str,
    mandate_id: str = None,
    error_details: Dict[str, Any] = None
) -> None:
    """Enhanced version of existing _fail_task with audit logging."""
    
    error_handler = AP2ErrorHandler(audit_logger)
    
    # Create structured error response
    error_response = error_handler.create_error_response(
        error_code=error_code,
        error_category="mandate_processing",
        error_type="validation_failure",
        severity="medium",
        message=error_message,
        details=error_details,
        mandate_id=mandate_id
    )
    
    # Create task failure with structured error
    error_message = updater.new_agent_message(
        parts=[
            Part(root=TextPart(text=error_response["message"])),
            Part(root=DataPart(data=error_response))
        ]
    )
    await updater.failed(message=error_message)
```

### Database Schema for Audit Storage

```sql
-- Audit events table
CREATE TABLE ap2_audit_events (
    event_id UUID PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    mandate_type VARCHAR(50) NOT NULL,
    mandate_id VARCHAR(255) NOT NULL,
    participant_id VARCHAR(255) NOT NULL,
    participant_type VARCHAR(50) NOT NULL,
    session_id VARCHAR(255),
    transaction_id VARCHAR(255),
    event_category VARCHAR(50) NOT NULL,
    event_action VARCHAR(100) NOT NULL,
    event_result VARCHAR(50) NOT NULL,
    event_details JSONB,
    security_context JSONB,
    privacy_metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Indexes for common queries
    INDEX idx_mandate_id (mandate_id),
    INDEX idx_participant (participant_id, participant_type),
    INDEX idx_timestamp (timestamp),
    INDEX idx_event_category (event_category),
    INDEX idx_transaction (transaction_id)
);

-- Mandate violations table for specialized queries
CREATE TABLE ap2_mandate_violations (
    violation_id UUID PRIMARY KEY,
    event_id UUID REFERENCES ap2_audit_events(event_id),
    mandate_id VARCHAR(255) NOT NULL,
    violation_type VARCHAR(100) NOT NULL,
    violation_severity VARCHAR(20) NOT NULL,
    expected_value TEXT,
    actual_value TEXT,
    enforcement_action VARCHAR(50) NOT NULL,
    compliance_impact JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    INDEX idx_mandate_violations_mandate_id (mandate_id),
    INDEX idx_mandate_violations_type (violation_type),
    INDEX idx_mandate_violations_severity (violation_severity)
);

-- Error tracking table
CREATE TABLE ap2_errors (
    error_id UUID PRIMARY KEY,
    event_id UUID REFERENCES ap2_audit_events(event_id),
    error_code VARCHAR(50) NOT NULL,
    error_category VARCHAR(50) NOT NULL,
    error_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    error_message TEXT NOT NULL,
    error_details JSONB,
    suggested_actions JSONB,
    compliance_context JSONB,
    technical_context JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    INDEX idx_error_code (error_code),
    INDEX idx_error_severity (severity),
    INDEX idx_error_category (error_category)
);
```

### Configuration Management

```yaml
# audit_config.yaml
audit_logging:
  enabled: true
  version: "1.0"
  
  # Storage configuration
  storage:
    backend: "postgresql"  # postgresql|mongodb|elasticsearch
    connection_string: "${AUDIT_DB_CONNECTION_STRING}"
    encryption_at_rest: true
    backup_retention_days: 2555  # 7 years
  
  # Event filtering
  events:
    log_all_mandate_events: true
    log_successful_payments: true
    log_failed_payments: true
    log_violations: true
    log_performance_metrics: false
  
  # Privacy controls
  privacy:
    redact_pii: true
    redact_payment_details: true
    allow_cross_participant_sharing: true
    zero_knowledge_proofs: false  # Future enhancement
  
  # Compliance settings
  compliance:
    pci_dss_mode: true
    sox_compliance: true
    gdpr_compliance: true
    data_retention_days: 2555
    automatic_reporting: true
  
  # Performance settings
  performance:
    async_logging: true
    batch_size: 100
    flush_interval_seconds: 30
    max_queue_size: 10000

# Error code configuration
error_codes:
  mandate_errors:
    creation:
      AP2-MND-CR-001: "Invalid mandate format"
      AP2-MND-CR-002: "Missing required user consent"
      AP2-MND-CR-003: "Merchant signature validation failed"
    enforcement:
      AP2-MND-EN-001: "Price constraint violation"
      AP2-MND-EN-002: "Unauthorized merchant attempted"
      AP2-MND-EN-003: "Mandate has expired"
    execution:
      AP2-MND-EX-001: "Payment method unavailable"
      AP2-MND-EX-002: "Insufficient funds"
      AP2-MND-EX-003: "Network timeout during processing"
```

## Sample Scenarios

### Scenario 1: Successful Payment with Audit Trail

```python
# Complete audit trail for successful payment flow
async def complete_payment_scenario():
    audit_logger = AP2AuditLogger("shopping_agent_001", "shopping_agent")
    
    # 1. Intent Creation
    intent_mandate_id = "intent_abc123"
    audit_logger.log_mandate_event(
        event_category="mandate_creation",
        event_action="intent_submitted",
        mandate_id=intent_mandate_id,
        mandate_type="intent_mandate",
        event_details={
            "natural_language_description": "High top red basketball shoes",
            "max_amount": 150.00,
            "allowed_merchants": ["nike", "adidas"],
            "user_consent_method": "biometric"
        }
    )
    
    # 2. Cart Finalization
    cart_mandate_id = "cart_def456"
    audit_logger.log_mandate_event(
        event_category="mandate_creation", 
        event_action="cart_finalized",
        mandate_id=cart_mandate_id,
        mandate_type="cart_mandate",
        event_details={
            "merchant_id": "nike_store_001",
            "total_amount": 129.99,
            "items": [{"sku": "AIR_JORDAN_1", "price": 119.99}, {"sku": "SHIPPING", "price": 10.00}],
            "merchant_signature": "jwt_signature_xyz"
        }
    )
    
    # 3. Payment Authorization
    payment_mandate_id = "payment_ghi789"
    audit_logger.log_mandate_event(
        event_category="mandate_creation",
        event_action="user_authorization_completed",
        mandate_id=payment_mandate_id,
        mandate_type="payment_mandate",
        transaction_id="txn_jkl012",
        event_details={
            "payment_method": "visa_ending_1234",
            "authorization_method": "digital_signature",
            "user_verification": "completed"
        }
    )
    
    # 4. Payment Processing
    audit_logger.log_mandate_event(
        event_category="mandate_execution",
        event_action="payment_initiated",
        mandate_id=payment_mandate_id,
        mandate_type="payment_mandate",
        transaction_id="txn_jkl012",
        event_details={
            "processor": "visa_net",
            "authorization_code": "AUTH_123456",
            "processing_time_ms": 1250
        }
    )
    
    # 5. Completion
    audit_logger.log_mandate_event(
        event_category="mandate_resolution",
        event_action="payment_confirmed",
        mandate_id=payment_mandate_id,
        mandate_type="payment_mandate", 
        transaction_id="txn_jkl012",
        event_result="success",
        event_details={
            "settlement_date": "2025-10-10",
            "final_amount": 129.99,
            "confirmation_code": "CONF_789012"
        }
    )
```

### Scenario 2: Mandate Violation with Error Handling

```python
async def price_violation_scenario():
    audit_logger = AP2AuditLogger("merchant_agent_001", "merchant_agent")
    error_handler = AP2ErrorHandler(audit_logger)
    
    # Attempt to process payment exceeding mandate limits
    mandate_id = "mandate_abc123"
    mandate_limit = 100.00
    attempted_amount = 150.00
    
    # Log the violation
    violation_log = audit_logger.log_mandate_violation(
        violation_type="price_exceeded",
        mandate_id=mandate_id,
        expected_value=mandate_limit,
        actual_value=attempted_amount,
        severity="high",
        enforcement_action="blocked"
    )
    
    # Create structured error response
    error_response = error_handler.create_error_response(
        error_code="AP2-MND-EN-001",
        error_category="mandate_enforcement",
        error_type="price_constraint_violation",
        severity="high",
        message="Transaction amount exceeds mandate maximum",
        details={
            "mandate_limit": mandate_limit,
            "attempted_amount": attempted_amount,
            "violation_amount": attempted_amount - mandate_limit,
            "currency": "USD"
        },
        mandate_id=mandate_id
    )
    
    # This would be returned to the user/calling agent
    return error_response
```

### Scenario 3: Cross-Participant Audit Verification

```python
async def cross_participant_verification():
    # Multiple participants contribute to audit trail
    
    # Shopping agent perspective
    shopping_logger = AP2AuditLogger("shopping_agent_001", "shopping_agent")
    shopping_log = shopping_logger.log_mandate_event(
        event_category="mandate_execution",
        event_action="payment_initiated",
        mandate_id="mandate_xyz789",
        mandate_type="payment_mandate",
        event_details={"shopping_agent_perspective": "user_authorized_payment"}
    )
    
    # Merchant agent perspective  
    merchant_logger = AP2AuditLogger("merchant_agent_001", "merchant_agent")
    merchant_log = merchant_logger.log_mandate_event(
        event_category="mandate_execution",
        event_action="payment_initiated", 
        mandate_id="mandate_xyz789",
        mandate_type="payment_mandate",
        event_details={"merchant_agent_perspective": "received_valid_payment_mandate"}
    )
    
    # Credentials provider perspective
    creds_logger = AP2AuditLogger("creds_provider_001", "credentials_provider")
    creds_log = creds_logger.log_mandate_event(
        event_category="mandate_execution",
        event_action="credentials_provided",
        mandate_id="mandate_xyz789",
        mandate_type="payment_mandate",
        event_details={"credentials_provider_perspective": "provided_payment_credentials"}
    )
    
    # Verification: All participants agree on key facts
    assert shopping_log["mandate_id"] == merchant_log["mandate_id"] == creds_log["mandate_id"]
    assert shopping_log["event_category"] == merchant_log["event_category"] == "mandate_execution"
    # Hash chain verification would occur here in production
```

## Migration Strategy

### Phase 1: Foundation (Weeks 1-2)
- Implement core audit logging schema
- Add basic event logging to existing agents
- Create configuration management system
- Develop simple error code integration

### Phase 2: Enhancement (Weeks 3-4)
- Add comprehensive error taxonomy
- Implement privacy-preserving features
- Create cross-participant verification
- Develop monitoring and alerting

### Phase 3: Integration (Weeks 5-6)
- Full integration with all AP2 agents
- Performance optimization
- Compliance validation
- Documentation and training

### Phase 4: Advanced Features (Future)
- Zero-knowledge audit proofs
- Real-time fraud detection
- Advanced analytics and reporting
- Regulatory automation

## Compliance Considerations

### PCI DSS Requirements
- **Requirement 10.1**: Implement audit trails to link all access to system components
- **Requirement 10.2**: Implement automated audit trails for all system components
- **Requirement 10.3**: Record specific audit log entries for all systems
- **Requirement 10.4**: Synchronize all critical system clocks and times
- **Requirement 10.5**: Secure audit trails to prevent unauthorized access

### SOX Compliance
- **Section 302**: Corporate responsibility for financial reports
- **Section 404**: Management assessment of internal controls
- **Section 409**: Real-time financial disclosure requirements

### GDPR Considerations
- **Article 25**: Data protection by design and by default
- **Article 32**: Security of processing
- **Article 35**: Data protection impact assessment

## Future Enhancements

### Zero-Knowledge Audit Proofs
- Range proofs for amount validation without disclosure
- Membership proofs for merchant authorization
- Timestamp proofs for mandate validity

### Machine Learning Integration
- Anomaly detection for fraud prevention
- Pattern recognition for compliance violations
- Predictive analytics for risk assessment

### Blockchain Integration
- Immutable audit trails
- Multi-party consensus mechanisms
- Smart contract automation

### Regulatory Automation
- Automated compliance reporting
- Real-time regulatory notifications
- Cross-jurisdiction requirement handling

## Conclusion

This document presents a comprehensive framework for standardized audit logging in the Agent Payments Protocol. The proposed schemas, error taxonomies, and implementation patterns are designed to:

1. **Ensure Compliance**: Meet PCI DSS, SOX, and other regulatory requirements
2. **Enable Trust**: Provide transparent, verifiable audit trails
3. **Support Scale**: Handle high-volume transaction processing
4. **Preserve Privacy**: Protect sensitive data while maintaining accountability
5. **Foster Interoperability**: Enable cross-participant verification and collaboration

The community-proposed standards build upon industry best practices while addressing the unique requirements of agentic payment systems. Implementation would require careful consideration of performance, privacy, and integration requirements, but would significantly enhance the trustworthiness and compliance capabilities of the AP2 ecosystem.

---

*This document represents community research and proposed standards for Issue #46. All proposals are subject to review, modification, and approval by the AP2 protocol maintainers. For questions or feedback, please comment on the GitHub issue or submit pull requests with improvements.*