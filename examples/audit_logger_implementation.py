#!/usr/bin/env python3
"""
AP2 Audit Logger Implementation Example

This module provides a practical implementation of the proposed audit logging
standards for the Agent Payments Protocol. It demonstrates how the standardized
audit log schema and error handling can be integrated into existing AP2 agents.

Usage:
    from audit_logger import AP2AuditLogger, AP2ErrorHandler
    
    # Initialize logger for a specific agent
    logger = AP2AuditLogger("shopping_agent_001", "shopping_agent")
    
    # Log mandate events
    logger.log_mandate_event(
        event_category="mandate_creation",
        event_action="intent_submitted",
        mandate_id="mandate_123",
        mandate_type="intent_mandate"
    )
    
    # Handle errors with structured responses
    error_handler = AP2ErrorHandler(logger)
    error_response = error_handler.create_error_response(
        error_code="AP2-MND-EN-001",
        error_category="mandate_enforcement", 
        error_type="price_constraint_violation",
        severity="high",
        message="Transaction amount exceeds mandate maximum"
    )
"""

import json
import uuid
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EventCategory(Enum):
    """Standardized event categories for mandate lifecycle."""
    MANDATE_CREATION = "mandate_creation"
    MANDATE_ENFORCEMENT = "mandate_enforcement"
    MANDATE_EXECUTION = "mandate_execution"
    MANDATE_VIOLATION = "mandate_violation"
    MANDATE_RESOLUTION = "mandate_resolution"


class MandateType(Enum):
    """Types of mandates in AP2."""
    INTENT_MANDATE = "intent_mandate"
    CART_MANDATE = "cart_mandate"
    PAYMENT_MANDATE = "payment_mandate"


class ParticipantType(Enum):
    """Types of AP2 participants."""
    SHOPPING_AGENT = "shopping_agent"
    MERCHANT_AGENT = "merchant_agent"
    CREDENTIALS_PROVIDER = "credentials_provider"
    PAYMENT_PROCESSOR = "payment_processor"


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityContext:
    """Security context for audit events."""
    encryption_algorithm: str = "AES-256-GCM"
    digital_signature: str = ""
    integrity_hash: str = ""


@dataclass
class PrivacyMetadata:
    """Privacy metadata for audit events."""
    pii_redacted: bool = True
    data_classification: str = "financial_transaction"
    retention_period_days: int = 2555  # 7 years
    shared_with: List[str] = None

    def __post_init__(self):
        if self.shared_with is None:
            self.shared_with = ["issuer", "network"]


@dataclass
class AuditEvent:
    """Complete audit event structure."""
    audit_log_version: str
    event_id: str
    timestamp: str
    event_type: str
    mandate_type: str
    mandate_id: str
    participant_id: str
    participant_type: str
    event_category: str
    event_action: str
    event_result: str
    event_details: Dict[str, Any]
    security_context: SecurityContext
    privacy_metadata: PrivacyMetadata
    session_id: Optional[str] = None
    transaction_id: Optional[str] = None


class AP2AuditLogger:
    """
    Implementation of standardized audit logging for AP2 agents.
    
    This class provides methods to create consistent audit log entries
    that comply with the proposed AP2 audit standards.
    """
    
    def __init__(self, participant_id: str, participant_type: str):
        """
        Initialize the audit logger for a specific AP2 participant.
        
        Args:
            participant_id: Unique identifier for this participant
            participant_type: Type of participant (shopping_agent, merchant_agent, etc.)
        """
        self.participant_id = participant_id
        self.participant_type = participant_type
        self.version = "1.0"
        
        # In production, this would be configured from external sources
        self.config = {
            "storage_backend": "postgresql",
            "encryption_enabled": True,
            "async_logging": True,
            "pii_redaction": True
        }
    
    def log_mandate_event(
        self,
        event_category: Union[str, EventCategory],
        event_action: str,
        mandate_id: str,
        mandate_type: Union[str, MandateType],
        event_result: str = "success",
        event_details: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        transaction_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a standardized audit log entry for mandate events.
        
        Args:
            event_category: High-level category of the event
            event_action: Specific action that occurred
            mandate_id: Unique identifier for the mandate
            mandate_type: Type of mandate (intent, cart, payment)
            event_result: Result of the event (success, failure, etc.)
            event_details: Additional event-specific details
            session_id: Session identifier for grouping related events
            transaction_id: Transaction identifier for payment events
            
        Returns:
            Dictionary containing the complete audit log entry
        """
        # Convert enums to strings if needed
        if isinstance(event_category, EventCategory):
            event_category = event_category.value
        if isinstance(mandate_type, MandateType):
            mandate_type = mandate_type.value
            
        # Generate unique event ID and timestamp
        event_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Create audit event
        audit_event = AuditEvent(
            audit_log_version=self.version,
            event_id=event_id,
            timestamp=timestamp,
            event_type="mandate_lifecycle_event",
            mandate_type=mandate_type,
            mandate_id=mandate_id,
            participant_id=self.participant_id,
            participant_type=self.participant_type,
            session_id=session_id,
            transaction_id=transaction_id,
            event_category=event_category,
            event_action=event_action,
            event_result=event_result,
            event_details=event_details or {},
            security_context=SecurityContext(),
            privacy_metadata=PrivacyMetadata()
        )
        
        # Convert to dictionary for processing
        audit_dict = asdict(audit_event)
        
        # Add security context
        audit_dict["security_context"]["digital_signature"] = self._sign_event(
            event_id, timestamp
        )
        
        # Compute integrity hash
        audit_dict["security_context"]["integrity_hash"] = self._compute_integrity_hash(
            audit_dict
        )
        
        # Store the audit entry
        self._store_audit_entry(audit_dict)
        
        logger.info(f"Audit event logged: {event_category}.{event_action} for {mandate_id}")
        
        return audit_dict
    
    def log_mandate_violation(
        self,
        violation_type: str,
        mandate_id: str,
        expected_value: Any,
        actual_value: Any,
        severity: Union[str, ErrorSeverity] = ErrorSeverity.MEDIUM,
        enforcement_action: str = "blocked",
        mandate_type: Union[str, MandateType] = MandateType.INTENT_MANDATE
    ) -> Dict[str, Any]:
        """
        Log mandate constraint violations with detailed context.
        
        Args:
            violation_type: Type of violation (price_exceeded, merchant_unauthorized, etc.)
            mandate_id: ID of the mandate that was violated
            expected_value: The expected value per mandate constraints
            actual_value: The actual value that was attempted
            severity: Severity level of the violation
            enforcement_action: Action taken (blocked, flagged, etc.)
            mandate_type: Type of mandate that was violated
            
        Returns:
            Dictionary containing the complete violation log entry
        """
        if isinstance(severity, ErrorSeverity):
            severity = severity.value
        if isinstance(mandate_type, MandateType):
            mandate_type = mandate_type.value
            
        # Calculate violation delta if possible
        violation_delta = None
        if isinstance(expected_value, (int, float)) and isinstance(actual_value, (int, float)):
            violation_delta = actual_value - expected_value
        
        event_details = {
            "violation_type": violation_type,
            "violation_severity": severity,
            "expected_value": str(expected_value),
            "actual_value": str(actual_value),
            "violation_delta": violation_delta,
            "enforcement_action": enforcement_action,
            "risk_factors": self._assess_risk_factors(violation_type, severity),
            "compliance_impact": self._assess_compliance_impact(violation_type, severity)
        }
        
        return self.log_mandate_event(
            event_category=EventCategory.MANDATE_VIOLATION,
            event_action=violation_type,
            mandate_id=mandate_id,
            mandate_type=mandate_type,
            event_result="violation_detected",
            event_details=event_details
        )
    
    def log_payment_execution(
        self,
        mandate_id: str,
        action: str,
        result: str,
        amount: Optional[float] = None,
        currency: str = "USD",
        processor: Optional[str] = None,
        authorization_code: Optional[str] = None,
        processing_time_ms: Optional[int] = None,
        transaction_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Log payment execution events with payment-specific details.
        
        Args:
            mandate_id: ID of the payment mandate
            action: Payment action (initiated, authorized, completed, etc.)
            result: Result of the payment action
            amount: Transaction amount
            currency: Currency code
            processor: Payment processor name
            authorization_code: Authorization code from processor
            processing_time_ms: Processing time in milliseconds
            transaction_id: Transaction identifier
            
        Returns:
            Dictionary containing the complete payment execution log entry
        """
        event_details = {
            "payment_processor": processor,
            "authorization_code": authorization_code,
            "processing_time_ms": processing_time_ms
        }
        
        if amount is not None:
            event_details["amount_details"] = {
                "currency": currency,
                "amount": amount
            }
        
        # Remove None values
        event_details = {k: v for k, v in event_details.items() if v is not None}
        
        return self.log_mandate_event(
            event_category=EventCategory.MANDATE_EXECUTION,
            event_action=action,
            mandate_id=mandate_id,
            mandate_type=MandateType.PAYMENT_MANDATE,
            event_result=result,
            event_details=event_details,
            transaction_id=transaction_id
        )
    
    def _sign_event(self, event_id: str, timestamp: str) -> str:
        """
        Create digital signature for the audit event.
        
        In production, this would use the agent's private key to create
        a proper digital signature. For this example, we create a
        placeholder signature.
        """
        signature_data = f"{self.participant_id}:{event_id}:{timestamp}"
        return f"signature_{hashlib.sha256(signature_data.encode()).hexdigest()[:16]}"
    
    def _compute_integrity_hash(self, audit_dict: Dict[str, Any]) -> str:
        """
        Compute integrity hash of the audit event.
        
        This creates a tamper-evident hash of the entire audit entry
        (excluding the integrity_hash field itself).
        """
        # Create a copy without the integrity_hash field
        entry_copy = audit_dict.copy()
        if "security_context" in entry_copy and "integrity_hash" in entry_copy["security_context"]:
            del entry_copy["security_context"]["integrity_hash"]
        
        # Compute hash of canonical JSON representation
        canonical_json = json.dumps(entry_copy, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical_json.encode()).hexdigest()
    
    def _assess_risk_factors(self, violation_type: str, severity: str) -> List[str]:
        """Assess risk factors associated with a violation."""
        risk_factors = []
        
        if violation_type == "price_exceeded":
            risk_factors.extend(["amount_anomaly", "potential_fraud"])
        elif violation_type == "merchant_unauthorized":
            risk_factors.extend(["unauthorized_merchant", "policy_violation"])
        elif violation_type == "mandate_expired":
            risk_factors.extend(["expired_authorization", "stale_mandate"])
        
        if severity in ["high", "critical"]:
            risk_factors.append("high_severity_violation")
        
        return risk_factors
    
    def _assess_compliance_impact(self, violation_type: str, severity: str) -> Dict[str, bool]:
        """Assess compliance impact of a violation."""
        return {
            "pci_dss_violation": violation_type in ["payment_data_exposure", "unauthorized_access"],
            "sox_reporting_required": severity in ["high", "critical"],
            "regulatory_notification": severity == "critical"
        }
    
    def _store_audit_entry(self, audit_entry: Dict[str, Any]) -> None:
        """
        Store audit entry to configured storage backend.
        
        In production, this would write to a secure audit log storage system
        such as a database, immutable ledger, or encrypted file system.
        """
        # For this example, we log to the standard logger
        # In production, this would be replaced with proper storage
        logger.info(f"AUDIT: {json.dumps(audit_entry, indent=2)}")


class AP2ErrorHandler:
    """
    Handler for creating standardized error responses in AP2.
    
    This class works with the audit logger to create consistent error
    responses that comply with the proposed error schema.
    """
    
    def __init__(self, audit_logger: AP2AuditLogger):
        """
        Initialize error handler with audit logging capability.
        
        Args:
            audit_logger: AP2AuditLogger instance for logging errors
        """
        self.audit_logger = audit_logger
        
        # Error code to suggestions mapping
        self.error_suggestions = {
            "AP2-MND-CR-001": [
                "Validate mandate format against schema",
                "Check required fields are present",
                "Ensure data types are correct"
            ],
            "AP2-MND-CR-002": [
                "Obtain proper user consent",
                "Verify consent method is supported",
                "Check consent timestamp validity"
            ],
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
            ],
            "AP2-MND-EX-001": [
                "Verify payment method is available",
                "Try alternative payment method",
                "Contact credentials provider"
            ],
            "AP2-MND-EX-002": [
                "Check account balance",
                "Try alternative payment method",
                "Request user to add funds"
            ]
        }
    
    def create_error_response(
        self,
        error_code: str,
        error_category: str,
        error_type: str,
        severity: Union[str, ErrorSeverity],
        message: str,
        details: Optional[Dict[str, Any]] = None,
        mandate_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a standardized error response with audit logging.
        
        Args:
            error_code: Structured error code (e.g., AP2-MND-EN-001)
            error_category: High-level error category
            error_type: Specific type of error
            severity: Error severity level
            message: Human-readable error message
            details: Error-specific details
            mandate_id: ID of mandate associated with error
            correlation_id: Correlation ID for tracing
            
        Returns:
            Dictionary containing the complete structured error response
        """
        if isinstance(severity, ErrorSeverity):
            severity = severity.value
            
        timestamp = datetime.now(timezone.utc).isoformat()
        correlation_id = correlation_id or str(uuid.uuid4())
        
        error_response = {
            "error_code": error_code,
            "error_category": error_category,
            "error_type": error_type,
            "severity": severity,
            "timestamp": timestamp,
            "message": message,
            "details": details or {},
            "suggested_actions": self.error_suggestions.get(error_code, [
                "Contact support for assistance"
            ]),
            "compliance_context": self._get_compliance_context(severity),
            "technical_context": {
                "correlation_id": correlation_id,
                "agent_id": self.audit_logger.participant_id,
                "agent_type": self.audit_logger.participant_type
            }
        }
        
        # Log the error event if mandate_id is provided
        if mandate_id:
            self.audit_logger.log_mandate_event(
                event_category=EventCategory.MANDATE_VIOLATION,
                event_action=error_type,
                mandate_id=mandate_id,
                mandate_type=MandateType.INTENT_MANDATE,  # Could be derived from context
                event_result="error",
                event_details={
                    "error_code": error_code,
                    "error_message": message,
                    "error_severity": severity,
                    "correlation_id": correlation_id
                }
            )
        
        logger.error(f"Error created: {error_code} - {message}")
        
        return error_response
    
    def create_mandate_violation_error(
        self,
        violation_type: str,
        mandate_id: str,
        expected_value: Any,
        actual_value: Any,
        severity: Union[str, ErrorSeverity] = ErrorSeverity.HIGH
    ) -> Dict[str, Any]:
        """
        Create error response specifically for mandate violations.
        
        Args:
            violation_type: Type of violation
            mandate_id: ID of violated mandate
            expected_value: Expected value per mandate
            actual_value: Actual attempted value
            severity: Severity of the violation
            
        Returns:
            Dictionary containing structured error response
        """
        # Map violation types to error codes
        violation_error_map = {
            "price_exceeded": "AP2-MND-EN-001",
            "merchant_unauthorized": "AP2-MND-EN-002",
            "mandate_expired": "AP2-MND-EN-003",
            "sku_not_permitted": "AP2-MND-EN-004",
            "refund_policy_violation": "AP2-MND-EN-005"
        }
        
        error_code = violation_error_map.get(violation_type, "AP2-MND-EN-999")
        
        details = {
            "mandate_id": mandate_id,
            "violation_type": violation_type,
            "expected_value": expected_value,
            "actual_value": actual_value
        }
        
        # Add specific details based on violation type
        if violation_type == "price_exceeded" and isinstance(expected_value, (int, float)):
            details.update({
                "mandate_limit": expected_value,
                "attempted_amount": actual_value,
                "violation_amount": actual_value - expected_value,
                "currency": "USD"  # Should be provided from context
            })
        
        message_map = {
            "price_exceeded": "Transaction amount exceeds mandate maximum",
            "merchant_unauthorized": "Merchant not authorized by mandate",
            "mandate_expired": "Mandate has expired",
            "sku_not_permitted": "Product SKU not permitted by mandate",
            "refund_policy_violation": "Refund policy requirements not met"
        }
        
        message = message_map.get(violation_type, f"Mandate violation: {violation_type}")
        
        return self.create_error_response(
            error_code=error_code,
            error_category="mandate_enforcement",
            error_type=violation_type,
            severity=severity,
            message=message,
            details=details,
            mandate_id=mandate_id
        )
    
    def _get_compliance_context(self, severity: str) -> Dict[str, bool]:
        """Get compliance context based on error severity."""
        return {
            "requires_reporting": severity in ["high", "critical"],
            "retention_required": True,
            "audit_trail_needed": True,
            "pci_dss_relevant": severity == "critical",
            "sox_reportable": severity in ["high", "critical"]
        }


# Example usage and integration patterns
def demo_audit_logging():
    """Demonstrate audit logging integration with AP2 agents."""
    
    print("=== AP2 Audit Logging Demo ===\n")
    
    # Initialize audit logger for shopping agent
    audit_logger = AP2AuditLogger("shopping_agent_001", "shopping_agent")
    error_handler = AP2ErrorHandler(audit_logger)
    
    # 1. Log intent mandate creation
    print("1. Logging intent mandate creation...")
    intent_log = audit_logger.log_mandate_event(
        event_category=EventCategory.MANDATE_CREATION,
        event_action="intent_submitted",
        mandate_id="intent_abc123",
        mandate_type=MandateType.INTENT_MANDATE,
        event_details={
            "natural_language_description": "High top red basketball shoes",
            "max_amount": 150.00,
            "allowed_merchants": ["nike", "adidas"],
            "user_consent_method": "biometric"
        },
        session_id="session_def456"
    )
    
    # 2. Log mandate violation
    print("\n2. Logging mandate violation...")
    violation_log = audit_logger.log_mandate_violation(
        violation_type="price_exceeded",
        mandate_id="intent_abc123",
        expected_value=150.00,
        actual_value=199.99,
        severity=ErrorSeverity.HIGH,
        enforcement_action="blocked"
    )
    
    # 3. Create structured error response
    print("\n3. Creating structured error response...")
    error_response = error_handler.create_mandate_violation_error(
        violation_type="price_exceeded",
        mandate_id="intent_abc123",
        expected_value=150.00,
        actual_value=199.99,
        severity=ErrorSeverity.HIGH
    )
    
    # 4. Log payment execution
    print("\n4. Logging payment execution...")
    payment_log = audit_logger.log_payment_execution(
        mandate_id="payment_ghi789",
        action="payment_initiated",
        result="success",
        amount=129.99,
        currency="USD",
        processor="visa_net",
        authorization_code="AUTH_123456",
        processing_time_ms=1250,
        transaction_id="txn_jkl012"
    )
    
    print("\n=== Demo Complete ===")
    return {
        "intent_log": intent_log,
        "violation_log": violation_log,
        "error_response": error_response,
        "payment_log": payment_log
    }


if __name__ == "__main__":
    # Run the demo
    demo_results = demo_audit_logging()
    
    # Print summary
    print(f"\nGenerated {len(demo_results)} audit/error entries:")
    for entry_type, entry in demo_results.items():
        print(f"- {entry_type}: {entry.get('event_id', entry.get('technical_context', {}).get('correlation_id', 'N/A'))}")