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

"""Programmable spending rules for autonomous agent transactions."""

from abc import ABC, abstractmethod
from datetime import datetime
from datetime import timezone
from enum import Enum
from typing import Any, Optional

from ap2.types.payment_request import PaymentCurrencyAmount
from pydantic import BaseModel
from pydantic import Field


class SpendingRuleType(str, Enum):
    """Types of spending rules that can be applied to agent transactions."""

    AMOUNT_CONSTRAINT = "amount_constraint"
    TIME_CONSTRAINT = "time_constraint"
    MERCHANT_CONSTRAINT = "merchant_constraint"
    CATEGORY_CONSTRAINT = "category_constraint"
    FREQUENCY_CONSTRAINT = "frequency_constraint"


class ConstraintOperator(str, Enum):
    """Operators for constraint evaluation."""

    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "lte"
    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "gte"
    EQUAL = "eq"
    NOT_EQUAL = "ne"
    IN = "in"
    NOT_IN = "not_in"
    MATCHES = "matches"  # For regex patterns


class SpendingRule(BaseModel, ABC):
    """Base class for all spending rules.

    Spending rules define programmable constraints that autonomous agents
    must respect when making purchases on behalf of users.
    """

    rule_id: str = Field(..., description="Unique identifier for this rule.")
    rule_type: SpendingRuleType = Field(..., description="Type of spending rule.")
    description: str = Field(
        ..., description="Human-readable description of the rule."
    )
    priority: int = Field(
        default=100,
        description="Rule priority (lower numbers = higher priority).",
        ge=1,
        le=1000,
    )
    enabled: bool = Field(default=True, description="Whether the rule is active.")
    created_at: str = Field(
        description="When the rule was created, in ISO 8601 format.",
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )

    @abstractmethod
    def evaluate(self, transaction_context: dict[str, Any]) -> bool:
        """Evaluate whether the transaction satisfies this rule.

        Args:
            transaction_context: Context about the proposed transaction

        Returns:
            True if the transaction satisfies the rule, False otherwise
        """
        pass


class AmountConstraint(SpendingRule):
    """Constraint on transaction amounts."""

    rule_type: SpendingRuleType = Field(
        default=SpendingRuleType.AMOUNT_CONSTRAINT, frozen=True
    )
    limit_amount: PaymentCurrencyAmount = Field(
        ..., description="The amount limit for this constraint."
    )
    operator: ConstraintOperator = Field(
        default=ConstraintOperator.LESS_THAN_OR_EQUAL,
        description="How to compare transaction amount with limit.",
    )
    time_window_hours: Optional[int] = Field(
        None,
        description="Time window in hours for aggregate amount checks. "
        "If None, applies per-transaction.",
        ge=1,
    )
    include_pending: bool = Field(
        default=True,
        description="Whether to include pending transactions in aggregate calculations.",
    )

    def evaluate(self, transaction_context: dict[str, Any]) -> bool:
        """Evaluate amount constraint."""
        transaction_amount = transaction_context.get("amount")
        if not transaction_amount:
            return False

        # Convert to same currency if needed
        if transaction_amount.currency != self.limit_amount.currency:
            # In a real implementation, this would use a currency conversion service
            # For now, we'll assume same currency or fail
            return False

        if self.time_window_hours is None:
            # Per-transaction limit
            return self._compare_amounts(
                transaction_amount.value, self.limit_amount.value
            )
        else:
            # Aggregate limit over time window
            historical_amount = transaction_context.get("historical_amount_in_window", 0)
            total_amount = historical_amount + transaction_amount.value
            return self._compare_amounts(total_amount, self.limit_amount.value)

    def _compare_amounts(self, transaction_value: float, limit_value: float) -> bool:
        """Compare transaction value with limit using specified operator."""
        if self.operator == ConstraintOperator.LESS_THAN:
            return transaction_value < limit_value
        elif self.operator == ConstraintOperator.LESS_THAN_OR_EQUAL:
            return transaction_value <= limit_value
        elif self.operator == ConstraintOperator.GREATER_THAN:
            return transaction_value > limit_value
        elif self.operator == ConstraintOperator.GREATER_THAN_OR_EQUAL:
            return transaction_value >= limit_value
        elif self.operator == ConstraintOperator.EQUAL:
            return abs(transaction_value - limit_value) < 0.001  # Float comparison
        elif self.operator == ConstraintOperator.NOT_EQUAL:
            return abs(transaction_value - limit_value) >= 0.001
        else:
            return False


class TimeConstraint(SpendingRule):
    """Constraint on when transactions can occur."""

    rule_type: SpendingRuleType = Field(
        default=SpendingRuleType.TIME_CONSTRAINT, frozen=True
    )
    valid_from: Optional[str] = Field(
        None, description="Earliest valid time in ISO 8601 format."
    )
    valid_until: Optional[str] = Field(
        None, description="Latest valid time in ISO 8601 format."
    )
    allowed_hours: Optional[list[int]] = Field(
        None,
        description="Allowed hours of day (0-23). If None, all hours allowed.",
        min_length=1,
        max_length=24,
    )
    allowed_days_of_week: Optional[list[int]] = Field(
        None,
        description="Allowed days of week (0=Monday, 6=Sunday). If None, all days allowed.",
        min_length=1,
        max_length=7,
    )
    timezone: str = Field(
        default="UTC", description="Timezone for time-based evaluations."
    )

    def evaluate(self, transaction_context: dict[str, Any]) -> bool:
        """Evaluate time constraint."""
        current_time = datetime.now(timezone.utc)
        transaction_time = transaction_context.get("timestamp", current_time)

        if isinstance(transaction_time, str):
            transaction_time = datetime.fromisoformat(transaction_time.replace("Z", "+00:00"))

        # Check absolute time bounds
        if self.valid_from:
            valid_from_dt = datetime.fromisoformat(self.valid_from.replace("Z", "+00:00"))
            if transaction_time < valid_from_dt:
                return False

        if self.valid_until:
            valid_until_dt = datetime.fromisoformat(self.valid_until.replace("Z", "+00:00"))
            if transaction_time > valid_until_dt:
                return False

        # Check hour constraints
        if self.allowed_hours is not None:
            if transaction_time.hour not in self.allowed_hours:
                return False

        # Check day of week constraints
        if self.allowed_days_of_week is not None:
            if transaction_time.weekday() not in self.allowed_days_of_week:
                return False

        return True


class MerchantConstraint(SpendingRule):
    """Constraint on which merchants are allowed/forbidden."""

    rule_type: SpendingRuleType = Field(
        default=SpendingRuleType.MERCHANT_CONSTRAINT, frozen=True
    )
    merchant_ids: list[str] = Field(
        ...,
        description="List of merchant identifiers.",
        min_length=1,
    )
    constraint_type: str = Field(
        ...,
        description="'allow' for whitelist, 'deny' for blacklist.",
        pattern="^(allow|deny)$",
    )
    match_type: str = Field(
        default="exact",
        description="How to match merchant IDs: 'exact', 'prefix', 'regex'.",
        pattern="^(exact|prefix|regex)$",
    )

    def evaluate(self, transaction_context: dict[str, Any]) -> bool:
        """Evaluate merchant constraint."""
        merchant_id = transaction_context.get("merchant_id")
        if not merchant_id:
            return False

        is_match = self._is_merchant_match(merchant_id)

        if self.constraint_type == "allow":
            return is_match
        else:  # deny
            return not is_match

    def _is_merchant_match(self, merchant_id: str) -> bool:
        """Check if merchant ID matches any in the constraint list."""
        for allowed_id in self.merchant_ids:
            if self.match_type == "exact":
                if merchant_id == allowed_id:
                    return True
            elif self.match_type == "prefix":
                if merchant_id.startswith(allowed_id):
                    return True
            elif self.match_type == "regex":
                import re
                if re.match(allowed_id, merchant_id):
                    return True
        return False


class CategoryConstraint(SpendingRule):
    """Constraint on product categories."""

    rule_type: SpendingRuleType = Field(
        default=SpendingRuleType.CATEGORY_CONSTRAINT, frozen=True
    )
    categories: list[str] = Field(
        ...,
        description="List of product categories.",
        min_length=1,
    )
    constraint_type: str = Field(
        ...,
        description="'allow' for whitelist, 'deny' for blacklist.",
        pattern="^(allow|deny)$",
    )
    category_system: str = Field(
        default="custom",
        description="Category classification system used.",
    )

    def evaluate(self, transaction_context: dict[str, Any]) -> bool:
        """Evaluate category constraint."""
        item_categories = transaction_context.get("categories", [])
        if not item_categories:
            return self.constraint_type == "deny"  # If no categories, only pass if denying categories

        has_matching_category = any(
            category in self.categories for category in item_categories
        )

        if self.constraint_type == "allow":
            return has_matching_category
        else:  # deny
            return not has_matching_category


class FrequencyConstraint(SpendingRule):
    """Constraint on transaction frequency."""

    rule_type: SpendingRuleType = Field(
        default=SpendingRuleType.FREQUENCY_CONSTRAINT, frozen=True
    )
    max_transactions: int = Field(
        ..., description="Maximum number of transactions allowed.", ge=1
    )
    time_window_hours: int = Field(
        ..., description="Time window in hours for frequency check.", ge=1
    )
    merchant_specific: bool = Field(
        default=False,
        description="Whether frequency is per-merchant or global.",
    )

    def evaluate(self, transaction_context: dict[str, Any]) -> bool:
        """Evaluate frequency constraint."""
        if self.merchant_specific:
            transaction_count = transaction_context.get(
                "merchant_transaction_count_in_window", 0
            )
        else:
            transaction_count = transaction_context.get(
                "total_transaction_count_in_window", 0
            )

        return transaction_count < self.max_transactions


class SpendingRuleSet(BaseModel):
    """A collection of spending rules with evaluation logic."""

    rules: list[SpendingRule] = Field(
        default_factory=list, description="List of spending rules."
    )
    evaluation_mode: str = Field(
        default="all",
        description="'all' requires all rules to pass, 'any' requires at least one to pass.",
        pattern="^(all|any)$",
    )
    created_at: str = Field(
        description="When the rule set was created, in ISO 8601 format.",
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )

    def evaluate_transaction(self, transaction_context: dict[str, Any]) -> dict[str, Any]:
        """Evaluate all rules against a transaction context.

        Args:
            transaction_context: Context about the proposed transaction

        Returns:
            Dictionary with evaluation results including overall pass/fail
        """
        if not self.rules:
            return {"allowed": True, "rule_results": [], "message": "No rules defined"}

        # Sort rules by priority (lower number = higher priority)
        sorted_rules = sorted(self.rules, key=lambda r: r.priority)

        rule_results = []
        for rule in sorted_rules:
            if rule.enabled:
                try:
                    result = rule.evaluate(transaction_context)
                    rule_results.append({
                        "rule_id": rule.rule_id,
                        "rule_type": rule.rule_type,
                        "passed": result,
                        "description": rule.description,
                    })
                except Exception as e:
                    rule_results.append({
                        "rule_id": rule.rule_id,
                        "rule_type": rule.rule_type,
                        "passed": False,
                        "description": rule.description,
                        "error": str(e),
                    })

        # Determine overall result based on evaluation mode
        if self.evaluation_mode == "all":
            allowed = all(result["passed"] for result in rule_results)
            message = "All rules passed" if allowed else "One or more rules failed"
        else:  # any
            allowed = any(result["passed"] for result in rule_results)
            message = "At least one rule passed" if allowed else "No rules passed"

        return {
            "allowed": allowed,
            "rule_results": rule_results,
            "message": message,
            "evaluation_mode": self.evaluation_mode,
        }

    def add_rule(self, rule: SpendingRule) -> None:
        """Add a spending rule to the set."""
        self.rules.append(rule)

    def remove_rule(self, rule_id: str) -> bool:
        """Remove a spending rule by ID.

        Returns:
            True if rule was found and removed, False otherwise
        """
        initial_count = len(self.rules)
        self.rules = [rule for rule in self.rules if rule.rule_id != rule_id]
        return len(self.rules) < initial_count

    def get_rule(self, rule_id: str) -> Optional[SpendingRule]:
        """Get a spending rule by ID."""
        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule
        return None