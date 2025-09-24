# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Enhanced validation logic for IntentMandate with human-not-present support."""

from datetime import datetime
from datetime import timezone
from enum import Enum
from typing import Any, Optional

from ap2.types.mandate import IntentMandate
from ap2.types.payment_request import PaymentCurrencyAmount
from ap2.types.session_auth import SessionStatus
from pydantic import BaseModel
from pydantic import Field


class ValidationResult(BaseModel):
    """Result of mandate validation."""

    is_valid: bool = Field(..., description="Whether the mandate is valid.")
    errors: list[str] = Field(
        default_factory=list, description="List of validation errors."
    )
    warnings: list[str] = Field(
        default_factory=list, description="List of validation warnings."
    )
    validation_context: dict[str, Any] = Field(
        default_factory=dict, description="Additional validation context."
    )


class ValidationSeverity(str, Enum):
    """Severity levels for validation issues."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class IntentMandateValidator:
    """Validator for enhanced IntentMandate with human-not-present support."""

    def __init__(self):
        """Initialize the mandate validator."""
        self.current_time = datetime.now(timezone.utc)

    def validate_mandate(
        self,
        mandate: IntentMandate,
        transaction_context: Optional[dict[str, Any]] = None,
    ) -> ValidationResult:
        """Validate an IntentMandate for both human-present and human-not-present flows.

        Args:
            mandate: The IntentMandate to validate
            transaction_context: Optional context about the proposed transaction

        Returns:
            ValidationResult with validation status and any issues found
        """
        result = ValidationResult(is_valid=True)
        transaction_context = transaction_context or {}

        # Basic mandate validation
        self._validate_basic_fields(mandate, result)

        # Flow-specific validation
        if mandate.user_cart_confirmation_required:
            self._validate_human_present_flow(mandate, result)
        else:
            self._validate_human_not_present_flow(mandate, result, transaction_context)

        # Spending rules validation
        if mandate.spending_rules and mandate.spending_rules.rules:
            self._validate_spending_rules(mandate, result, transaction_context)

        # Agent DID validation
        if mandate.agent_did:
            self._validate_agent_did(mandate, result)

        # Set overall validity
        result.is_valid = len(result.errors) == 0

        return result

    def _validate_basic_fields(self, mandate: IntentMandate, result: ValidationResult) -> None:
        """Validate basic mandate fields."""
        # Check intent expiry
        try:
            expiry_time = datetime.fromisoformat(mandate.intent_expiry.replace("Z", "+00:00"))
            if expiry_time <= self.current_time:
                result.errors.append("Intent mandate has expired")
        except ValueError:
            result.errors.append("Invalid intent_expiry format (must be ISO 8601)")

        # Validate natural language description
        if not mandate.natural_language_description.strip():
            result.errors.append("Natural language description cannot be empty")

        if len(mandate.natural_language_description) > 1000:
            result.warnings.append("Natural language description is very long (>1000 chars)")

        # Validate delegation depth
        if mandate.delegation_depth < 1 or mandate.delegation_depth > 5:
            result.errors.append("Delegation depth must be between 1 and 5")

    def _validate_human_present_flow(self, mandate: IntentMandate, result: ValidationResult) -> None:
        """Validate mandate for human-present flow."""
        # Human-present flows should not have session authorization
        if mandate.session_authorization:
            result.warnings.append(
                "Session authorization provided for human-present flow (will be ignored)"
            )

        # Agent DID is optional for human-present flows
        if mandate.agent_did:
            result.validation_context["flow_type"] = "human_present_with_agent_did"
        else:
            result.validation_context["flow_type"] = "human_present_traditional"

    def _validate_human_not_present_flow(
        self,
        mandate: IntentMandate,
        result: ValidationResult,
        transaction_context: dict[str, Any],
    ) -> None:
        """Validate mandate for human-not-present flow."""
        result.validation_context["flow_type"] = "human_not_present"

        # Session authorization is required for human-not-present flows
        if not mandate.session_authorization:
            result.errors.append(
                "Session authorization required for human-not-present flows"
            )
        else:
            self._validate_session_authorization(mandate, result)

        # Agent DID is required for human-not-present flows
        if not mandate.agent_did:
            result.errors.append("Agent DID required for human-not-present flows")

        # Spending rules should be defined for autonomous flows
        if not mandate.spending_rules.rules:
            result.warnings.append(
                "No spending rules defined for autonomous flow - consider adding constraints"
            )

    def _validate_session_authorization(self, mandate: IntentMandate, result: ValidationResult) -> None:
        """Validate session authorization."""
        session_auth = mandate.session_authorization
        if not session_auth:
            return

        # Check session validity
        if not session_auth.is_valid(self.current_time):
            if session_auth.status != SessionStatus.ACTIVE:
                result.errors.append(f"Session authorization status is {session_auth.status}")
            else:
                result.errors.append("Session authorization has expired")

        # Verify agent DID matches
        if mandate.agent_did and session_auth.agent_did != mandate.agent_did:
            result.errors.append(
                "Session authorization agent DID does not match mandate agent DID"
            )

        # Check session expiry vs intent expiry
        try:
            session_expiry = datetime.fromisoformat(session_auth.session_expiry.replace("Z", "+00:00"))
            intent_expiry = datetime.fromisoformat(mandate.intent_expiry.replace("Z", "+00:00"))

            if session_expiry > intent_expiry:
                result.warnings.append(
                    "Session authorization expires after intent mandate"
                )
        except ValueError:
            result.errors.append("Invalid date format in session authorization")

        # Validate session intents
        if not session_auth.intents:
            result.warnings.append("Session authorization has no specific intents defined")

    def _validate_spending_rules(
        self,
        mandate: IntentMandate,
        result: ValidationResult,
        transaction_context: dict[str, Any],
    ) -> None:
        """Validate spending rules against transaction context."""
        spending_rules = mandate.spending_rules

        # Check for rule conflicts
        conflicts = self._detect_rule_conflicts(spending_rules)
        if conflicts:
            result.warnings.extend([f"Spending rule conflict: {conflict}" for conflict in conflicts])

        # If we have transaction context, evaluate rules
        if transaction_context:
            evaluation_result = spending_rules.evaluate_transaction(transaction_context)
            result.validation_context["spending_rules_evaluation"] = evaluation_result

            if not evaluation_result["allowed"]:
                result.errors.append(
                    f"Transaction violates spending rules: {evaluation_result['message']}"
                )

    def _validate_agent_did(self, mandate: IntentMandate, result: ValidationResult) -> None:
        """Validate agent DID format and structure."""
        agent_did = mandate.agent_did
        if not agent_did:
            return

        # Basic DID format validation
        if not agent_did.startswith("did:"):
            result.errors.append("Agent DID must start with 'did:'")
            return

        # Split DID into components
        did_parts = agent_did.split(":")
        if len(did_parts) < 3:
            result.errors.append("Agent DID must have at least method and identifier")
            return

        method = did_parts[1]
        identifier = did_parts[2]

        # Validate supported DID methods
        supported_methods = ["kite", "web", "ethr", "key"]
        if method not in supported_methods:
            result.warnings.append(
                f"Agent DID method '{method}' may not be supported (supported: {supported_methods})"
            )

        # Basic identifier validation
        if not identifier:
            result.errors.append("Agent DID identifier cannot be empty")

        result.validation_context["agent_did_method"] = method
        result.validation_context["agent_did_identifier"] = identifier

    def _detect_rule_conflicts(self, spending_rules) -> list[str]:
        """Detect conflicts between spending rules."""
        conflicts = []

        # Group rules by type
        rules_by_type = {}
        for rule in spending_rules.rules:
            rule_type = rule.rule_type
            if rule_type not in rules_by_type:
                rules_by_type[rule_type] = []
            rules_by_type[rule_type].append(rule)

        # Check for amount constraint conflicts
        amount_rules = rules_by_type.get("amount_constraint", [])
        if len(amount_rules) > 1:
            # Check for overlapping time windows with different limits
            for i, rule1 in enumerate(amount_rules):
                for rule2 in amount_rules[i + 1:]:
                    if (rule1.time_window_hours == rule2.time_window_hours and
                        rule1.limit_amount.currency == rule2.limit_amount.currency):
                        conflicts.append(
                            f"Multiple amount constraints for same currency and time window: "
                            f"{rule1.rule_id} and {rule2.rule_id}"
                        )

        # Check for merchant constraint conflicts
        merchant_rules = rules_by_type.get("merchant_constraint", [])
        allow_rules = [r for r in merchant_rules if r.constraint_type == "allow"]
        deny_rules = [r for r in merchant_rules if r.constraint_type == "deny"]

        if allow_rules and deny_rules:
            # Check for overlapping merchant lists
            allowed_merchants = set()
            for rule in allow_rules:
                allowed_merchants.update(rule.merchant_ids)

            denied_merchants = set()
            for rule in deny_rules:
                denied_merchants.update(rule.merchant_ids)

            overlap = allowed_merchants.intersection(denied_merchants)
            if overlap:
                conflicts.append(
                    f"Merchant(s) both allowed and denied: {', '.join(overlap)}"
                )

        return conflicts

    def validate_transaction_against_mandate(
        self,
        mandate: IntentMandate,
        transaction_amount: PaymentCurrencyAmount,
        merchant_id: str,
        categories: Optional[list[str]] = None,
    ) -> ValidationResult:
        """Validate a specific transaction against the mandate.

        Args:
            mandate: The IntentMandate to validate against
            transaction_amount: Amount of the proposed transaction
            merchant_id: Identifier of the merchant
            categories: Optional list of product categories

        Returns:
            ValidationResult indicating if transaction is allowed
        """
        transaction_context = {
            "amount": transaction_amount,
            "merchant_id": merchant_id,
            "categories": categories or [],
            "timestamp": self.current_time,
        }

        return self.validate_mandate(mandate, transaction_context)