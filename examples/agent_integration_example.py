"""
AP2 Agent Integration Example

This example shows how to integrate the proposed audit logging standards
into existing AP2 agent code with minimal changes.

This demonstrates integration with the merchant agent's payment processing
workflow, adding comprehensive audit logging and structured error handling.
"""

import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timezone

# Import our audit logging implementation
from examples.audit_logger_implementation import (
    AP2AuditLogger,
    AP2ErrorHandler,
    EventCategory,
    MandateType,
    ErrorSeverity
)

# Mock imports to represent existing AP2 types
class PaymentMandate:
    def __init__(self, payment_mandate_contents):
        self.payment_mandate_contents = payment_mandate_contents

class PaymentMandateContents:
    def __init__(self, payment_mandate_id: str, payment_details_total: Dict):
        self.payment_mandate_id = payment_mandate_id
        self.payment_details_total = payment_details_total

class TaskUpdater:
    def __init__(self):
        self.messages = []

    async def failed(self, message):
        self.messages.append(("failed", message))

    async def complete(self, message=None):
        self.messages.append(("complete", message))


class EnhancedMerchantAgentTools:
    """
    Enhanced version of merchant agent tools with audit logging integration.

    This shows how the existing merchant agent tools can be enhanced with
    comprehensive audit logging and structured error handling while
    maintaining backward compatibility.
    """

    def __init__(self, merchant_id: str = "merchant_agent_001"):
        """Initialize enhanced merchant agent with audit logging."""
        self.audit_logger = AP2AuditLogger(merchant_id, "merchant_agent")
        self.error_handler = AP2ErrorHandler(self.audit_logger)
        self.merchant_id = merchant_id

    async def initiate_payment_enhanced(
        self,
        data_parts: list[dict[str, Any]],
        updater: TaskUpdater,
        current_task: Optional[dict] = None,
        debug_mode: bool = False,
    ) -> None:
        """
        Enhanced version of initiate_payment with comprehensive audit logging.

        This is based on the existing merchant_agent/tools.py:initiate_payment
        but adds structured audit logging and error handling.
        """
        # Start audit logging for payment initiation
        session_id = str(uuid.uuid4())

        self.audit_logger.log_mandate_event(
            event_category=EventCategory.MANDATE_EXECUTION,
            event_action="payment_initiation_requested",
            mandate_id="pending_validation",  # Will be updated once validated
            mandate_type=MandateType.PAYMENT_MANDATE,
            session_id=session_id,
            event_details={
                "debug_mode": debug_mode,
                "data_parts_count": len(data_parts),
                "has_current_task": current_task is not None
            }
        )

        # Extract payment mandate (original logic)
        payment_mandate_data = None
        for part in data_parts:
            if "ap2.mandates.PaymentMandate" in part:
                payment_mandate_data = part["ap2.mandates.PaymentMandate"]
                break

        if not payment_mandate_data:
            # Enhanced error handling with audit logging
            error_response = self.error_handler.create_error_response(
                error_code="AP2-MND-EX-001",
                error_category="mandate_execution",
                error_type="missing_payment_mandate",
                severity=ErrorSeverity.HIGH,
                message="Missing payment_mandate in request data",
                details={
                    "data_parts_received": len(data_parts),
                    "expected_key": "ap2.mandates.PaymentMandate"
                }
            )

            await self._fail_task_enhanced(
                updater,
                error_response,
                session_id=session_id
            )
            return

        # Validate and parse payment mandate
        try:
            # Require payment_mandate_id - no fallback to random UUID for security/audit reasons
            payment_mandate = PaymentMandate(
                PaymentMandateContents(
                    payment_mandate_id=payment_mandate_data["payment_mandate_id"],  # Direct access - let KeyError be raised
                    payment_details_total=payment_mandate_data.get("payment_details_total", {})
                )
            )
            mandate_id = payment_mandate.payment_mandate_contents.payment_mandate_id

            # Log successful mandate validation
            self.audit_logger.log_mandate_event(
                event_category=EventCategory.MANDATE_EXECUTION,
                event_action="payment_mandate_validated",
                mandate_id=mandate_id,
                mandate_type=MandateType.PAYMENT_MANDATE,
                session_id=session_id,
                event_details={
                    "validation_result": "success",
                    "mandate_structure": "valid"
                }
            )

        except KeyError as e:
            # Specific handling for missing payment_mandate_id (security critical)
            error_response = self.error_handler.create_error_response(
                error_code="AP2-MND-CR-002",
                error_category="mandate_creation", 
                error_type="missing_mandate_id",
                severity=ErrorSeverity.CRITICAL,
                message=f"Missing required field in payment mandate: {str(e)}",
                details={
                    "missing_field": str(e),
                    "received_data_keys": list(payment_mandate_data.keys()) if payment_mandate_data else [],
                    "security_note": "mandate_id is required for audit trail integrity"
                }
            )

            await self._fail_task_enhanced(
                updater,
                error_response,
                session_id=session_id
            )
            return

        except Exception as e:
            # Log validation failure with structured error
            error_response = self.error_handler.create_error_response(
                error_code="AP2-MND-CR-001",
                error_category="mandate_creation",
                error_type="invalid_mandate_format",
                severity=ErrorSeverity.HIGH,
                message=f"Invalid payment mandate format: {str(e)}",
                details={
                    "validation_error": str(e),
                    "received_data_keys": list(payment_mandate_data.keys()) if payment_mandate_data else []
                }
            )

            await self._fail_task_enhanced(
                updater,
                error_response,
                session_id=session_id
            )
            return

        # Extract risk data (original logic)
        risk_data = None
        for part in data_parts:
            if "risk_data" in part:
                risk_data = part["risk_data"]
                break

        if not risk_data:
            # Enhanced error handling for missing risk data
            error_response = self.error_handler.create_error_response(
                error_code="AP2-MND-EX-003",
                error_category="mandate_execution",
                error_type="missing_risk_data",
                severity=ErrorSeverity.MEDIUM,
                message="Missing required risk_data for payment processing",
                details={
                    "mandate_id": mandate_id,
                    "risk_assessment": "blocked_due_to_missing_data"
                },
                mandate_id=mandate_id,
                mandate_type=MandateType.PAYMENT_MANDATE
            )

            await self._fail_task_enhanced(
                updater,
                error_response,
                mandate_id=mandate_id,
                session_id=session_id
            )
            return

        # Validate payment amount against mandate constraints
        payment_amount = payment_mandate.payment_mandate_contents.payment_details_total.get("value", 0)
        validation_error = self._validate_payment_constraints(mandate_id, payment_amount, session_id)
        if validation_error:
            # Constraint validation failed - fail the task with structured error
            await self._fail_task_enhanced(
                updater,
                validation_error,
                mandate_id=mandate_id,
                session_id=session_id
            )
            return

        # Log successful constraint validation
        self.audit_logger.log_mandate_event(
            event_category=EventCategory.MANDATE_ENFORCEMENT,
            event_action="constraints_validated",
            mandate_id=mandate_id,
            mandate_type=MandateType.PAYMENT_MANDATE,
            session_id=session_id,
            event_details={
                "amount": payment_amount,
                "risk_score": risk_data.get("risk_score", 0),
                "validation_result": "passed"
            }
        )

        # Proceed with payment processing (original logic would continue here)
        transaction_id = str(uuid.uuid4())

        # Log payment initiation
        self.audit_logger.log_payment_execution(
            mandate_id=mandate_id,
            action="payment_processing_started",
            result="in_progress",
            amount=payment_amount,
            currency="USD",  # Would be extracted from mandate
            processor="example_processor",
            transaction_id=transaction_id
        )

        # Simulate successful payment completion
        await self._complete_payment_enhanced(
            mandate_id=mandate_id,
            transaction_id=transaction_id,
            amount=payment_amount,
            updater=updater,
            session_id=session_id
        )

    def _validate_payment_constraints(
        self,
        mandate_id: str,
        payment_amount: float,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Validate payment against mandate constraints with audit logging.
        
        This demonstrates how constraint validation can be enhanced with
        structured violation logging.

        Returns:
            An error response dictionary if validation fails, otherwise None.
        """
        # Example constraint: maximum payment amount of $500
        max_amount = 500.00

        if payment_amount > max_amount:
            # Create structured error response. The error handler will log the violation.
            return self.error_handler.create_mandate_violation_error(
                violation_type="price_exceeded",
                mandate_id=mandate_id,
                mandate_type=MandateType.PAYMENT_MANDATE,
                expected_value=max_amount,
                actual_value=payment_amount,
                severity=ErrorSeverity.HIGH
            )

        return None

    async def _complete_payment_enhanced(
        self,
        mandate_id: str,
        transaction_id: str,
        amount: float,
        updater: TaskUpdater,
        session_id: str
    ) -> None:
        """Complete payment processing with comprehensive audit logging."""

        # Simulate payment processing time
        processing_start = datetime.now(timezone.utc)

        # Log payment completion
        processing_time_ms = 1250  # Simulated processing time
        authorization_code = f"AUTH_{uuid.uuid4().hex[:8].upper()}"

        self.audit_logger.log_payment_execution(
            mandate_id=mandate_id,
            action="payment_completed",
            result="success",
            amount=amount,
            currency="USD",
            processor="example_processor",
            authorization_code=authorization_code,
            processing_time_ms=processing_time_ms,
            transaction_id=transaction_id
        )

        # Log final resolution
        self.audit_logger.log_mandate_event(
            event_category=EventCategory.MANDATE_RESOLUTION,
            event_action="payment_confirmed",
            mandate_id=mandate_id,
            mandate_type=MandateType.PAYMENT_MANDATE,
            session_id=session_id,
            transaction_id=transaction_id,
            event_details={
                "final_amount": amount,
                "authorization_code": authorization_code,
                "settlement_status": "pending",
                "confirmation_timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

        # Complete the task (original logic)
        success_message = {
            "status": "success",
            "transaction_id": transaction_id,
            "authorization_code": authorization_code,
            "amount": amount
        }

        await updater.complete(message=success_message)

    async def _fail_task_enhanced(
        self,
        updater: TaskUpdater,
        error_response: Dict[str, Any],
        mandate_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> None:
        """
        Enhanced version of _fail_task with structured error responses.

        This replaces the simple error text with a comprehensive structured
        error response that includes audit logging.
        """
        # Log the task failure event
        if mandate_id:
            self.audit_logger.log_mandate_event(
                event_category=EventCategory.MANDATE_EXECUTION,
                event_action="task_failed",
                mandate_id=mandate_id,
                mandate_type=MandateType.PAYMENT_MANDATE,
                session_id=session_id,
                event_result="failure",
                event_details={
                    "error_code": error_response["error_code"],
                    "error_category": error_response["error_category"],
                    "failure_reason": error_response["message"]
                }
            )

        # Fail the task with structured error
        await updater.failed(message=error_response)


# Example of how to modify existing agent code with minimal changes
class BackwardCompatibleMerchantAgent:
    """
    Example showing backward-compatible integration.

    This shows how existing agent code can be gradually enhanced with
    audit logging without breaking existing functionality.
    """

    def __init__(self, merchant_id: str = "merchant_agent_001"):
        # Add audit logging to existing initialization
        self.audit_logger = AP2AuditLogger(merchant_id, "merchant_agent")
        self.error_handler = AP2ErrorHandler(self.audit_logger)

        # Existing initialization code would remain unchanged
        self.merchant_id = merchant_id

    async def initiate_payment(
        self,
        data_parts: list[dict[str, Any]],
        updater: TaskUpdater,
        current_task: Optional[dict] = None,
        debug_mode: bool = False,
    ) -> None:
        """
        Existing initiate_payment method with minimal audit logging integration.

        This shows how to add basic audit logging to existing methods
        without major refactoring.
        """
        # Add minimal audit logging at the start
        session_id = str(uuid.uuid4())

        try:
            # Log payment initiation attempt
            self.audit_logger.log_mandate_event(
                event_category="mandate_execution",
                event_action="payment_initiation_requested",
                mandate_id="pending_extraction",
                mandate_type="payment_mandate",
                session_id=session_id
            )

            # EXISTING CODE STARTS HERE (unchanged)
            payment_mandate_data = None
            for part in data_parts:
                if "ap2.mandates.PaymentMandate" in part:
                    payment_mandate_data = part["ap2.mandates.PaymentMandate"]
                    break

            if not payment_mandate_data:
                await self._fail_task(updater, "Missing payment_mandate.")
                return

            # More existing code would follow...
            # EXISTING CODE ENDS HERE

            # Add minimal audit logging at the end
            mandate_id = payment_mandate_data.get("payment_mandate_id", "unknown")
            self.audit_logger.log_mandate_event(
                event_category="mandate_execution",
                event_action="payment_completed",
                mandate_id=mandate_id,
                mandate_type="payment_mandate",
                session_id=session_id,
                event_result="success"
            )

        except Exception as e:
            # Enhanced error handling with audit logging
            error_response = self.error_handler.create_error_response(
                error_code="AP2-MND-EX-999",
                error_category="mandate_execution",
                error_type="unexpected_error",
                severity="high",
                message=f"Unexpected error during payment processing: {str(e)}"
            )

            await updater.failed(message=error_response)

    async def _fail_task(self, updater: TaskUpdater, error_text: str) -> None:
        """
        Minimally enhanced version of existing _fail_task method.

        This shows how to gradually enhance error handling while maintaining
        backward compatibility.
        """
        # Create basic structured error from simple text
        error_response = self.error_handler.create_error_response(
            error_code="AP2-MND-EX-999",
            error_category="mandate_execution",
            error_type="general_error",
            severity="medium",
            message=error_text
        )

        # Maintain backward compatibility by also logging simple text
        await updater.failed(message=error_response)


# Demo function showing integration examples
async def demo_agent_integration():
    """Demonstrate how audit logging integrates with AP2 agents."""

    print("=== AP2 Agent Integration Demo ===\n")

    # 1. Enhanced agent with full audit logging
    print("1. Testing enhanced merchant agent...")
    enhanced_agent = EnhancedMerchantAgentTools("enhanced_merchant_001")

    # Simulate payment request data
    payment_data = [
        {
            "ap2.mandates.PaymentMandate": {
                "payment_mandate_id": "mandate_test_123",
                "payment_details_total": {"value": 99.99, "currency": "USD"}
            }
        },
        {
            "risk_data": {"risk_score": 0.1, "device_id": "device_123"}
        }
    ]

    updater = TaskUpdater()
    await enhanced_agent.initiate_payment_enhanced(payment_data, updater, debug_mode=True)
    print(f"Enhanced agent completed with {len(updater.messages)} messages")

    # 2. Test constraint violation
    print("\n2. Testing constraint violation...")
    violation_data = [
        {
            "ap2.mandates.PaymentMandate": {
                "payment_mandate_id": "mandate_violation_456",
                "payment_details_total": {"value": 999.99, "currency": "USD"}  # Exceeds $500 limit
            }
        },
        {
            "risk_data": {"risk_score": 0.3, "device_id": "device_456"}
        }
    ]

    violation_updater = TaskUpdater()
    await enhanced_agent.initiate_payment_enhanced(violation_data, violation_updater)
    print(f"Violation test completed with {len(violation_updater.messages)} messages")

    # 3. Backward compatible agent
    print("\n3. Testing backward-compatible agent...")
    compat_agent = BackwardCompatibleMerchantAgent("compat_merchant_001")
    compat_updater = TaskUpdater()
    await compat_agent.initiate_payment(payment_data, compat_updater)
    print(f"Compatible agent completed with {len(compat_updater.messages)} messages")

    print("\n=== Integration Demo Complete ===")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo_agent_integration())
