#!/usr/bin/env python3

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

"""Autonomous shopping agent demonstrating human-not-present flows with AP2.

This sample demonstrates how an AI agent can make purchases autonomously
using enhanced IntentMandate with session-based authorization and spending rules.

Example usage:
    python agent.py --intent "Buy running shoes under $200" --budget 200 --duration 24
"""

import argparse
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from ap2.types.mandate import IntentMandate
from ap2.types.payment_request import PaymentCurrencyAmount
from ap2.types.session_auth import (
    SessionAuthorization, SessionAuthType, SessionCredential,
    SessionIntent, SessionStatus
)
from ap2.types.spending_rules import (
    AmountConstraint, CategoryConstraint, SpendingRuleSet,
    TimeConstraint, ConstraintOperator
)
from ap2.validation.mandate_validator import IntentMandateValidator


class AutonomousShoppingAgent:
    """Autonomous shopping agent with human-not-present capabilities."""

    def __init__(self, agent_did: str, user_wallet: str):
        """Initialize the autonomous shopping agent.

        Args:
            agent_did: Decentralized identifier for this agent
            user_wallet: User's wallet address
        """
        self.agent_did = agent_did
        self.user_wallet = user_wallet
        self.validator = IntentMandateValidator()
        self.active_mandates: Dict[str, IntentMandate] = {}

    def create_autonomous_mandate(
        self,
        description: str,
        max_budget: float,
        currency: str = "USD",
        duration_hours: int = 24,
        allowed_merchants: Optional[List[str]] = None,
        allowed_categories: Optional[List[str]] = None,
    ) -> IntentMandate:
        """Create an IntentMandate for autonomous shopping.

        Args:
            description: Natural language description of shopping intent
            max_budget: Maximum budget for shopping
            currency: Currency code (e.g., 'USD')
            duration_hours: How long the mandate should be valid
            allowed_merchants: Optional list of allowed merchant IDs
            allowed_categories: Optional list of allowed product categories

        Returns:
            IntentMandate configured for human-not-present flow
        """
        # Create session authorization
        session_auth = self._create_session_authorization(
            max_budget, currency, duration_hours
        )

        # Create spending rules
        spending_rules = self._create_spending_rules(
            max_budget, currency, allowed_merchants, allowed_categories
        )

        # Calculate expiry time
        expiry_time = datetime.now(timezone.utc) + timedelta(hours=duration_hours)

        # Create the mandate
        mandate = IntentMandate(
            user_cart_confirmation_required=False,  # Enable autonomous mode
            natural_language_description=description,
            merchants=allowed_merchants,
            intent_expiry=expiry_time.isoformat(),
            session_authorization=session_auth,
            spending_rules=spending_rules,
            agent_did=self.agent_did,
            delegation_depth=1,
            requires_consensus=False,
        )

        # Store the mandate
        mandate_id = str(uuid.uuid4())
        self.active_mandates[mandate_id] = mandate

        print(f"Created autonomous mandate {mandate_id}")
        print(f"Description: {description}")
        print(f"Budget: {max_budget} {currency}")
        print(f"Valid until: {expiry_time.isoformat()}")

        return mandate

    def _create_session_authorization(
        self, max_budget: float, currency: str, duration_hours: int
    ) -> SessionAuthorization:
        """Create session authorization for autonomous operations."""
        # Create session credential (mock implementation)
        credential = SessionCredential(
            credential_id=str(uuid.uuid4()),
            public_key="mock_public_key_" + str(uuid.uuid4()),
            signature_algorithm="ES256",
            key_derivation_method="random",
        )

        # Create session intent
        expiry_time = datetime.now(timezone.utc) + timedelta(hours=duration_hours)
        intent = SessionIntent(
            intent_id=str(uuid.uuid4()),
            action="purchase",
            max_amount=PaymentCurrencyAmount(currency=currency, value=max_budget),
            valid_until=expiry_time.isoformat(),
        )

        # Create session authorization
        session_auth = SessionAuthorization(
            session_id=str(uuid.uuid4()),
            agent_did=self.agent_did,
            user_wallet_address=self.user_wallet,
            auth_type=SessionAuthType.EPHEMERAL_KEY,
            credential=credential,
            intents=[intent],
            session_expiry=expiry_time.isoformat(),
            status=SessionStatus.ACTIVE,
            interaction_pattern="server-initiated",
        )

        return session_auth

    def _create_spending_rules(
        self,
        max_budget: float,
        currency: str,
        allowed_merchants: Optional[List[str]],
        allowed_categories: Optional[List[str]],
    ) -> SpendingRuleSet:
        """Create spending rules for the mandate."""
        rules = []

        # Add budget constraint
        budget_rule = AmountConstraint(
            rule_id=str(uuid.uuid4()),
            description=f"Maximum budget of {max_budget} {currency}",
            limit_amount=PaymentCurrencyAmount(currency=currency, value=max_budget),
            operator=ConstraintOperator.LESS_THAN_OR_EQUAL,
            priority=10,
        )
        rules.append(budget_rule)

        # Add time constraint (only during business hours for safety)
        time_rule = TimeConstraint(
            rule_id=str(uuid.uuid4()),
            description="Only allow purchases during business hours",
            allowed_hours=list(range(9, 18)),  # 9 AM to 6 PM
            priority=20,
        )
        rules.append(time_rule)

        # Add merchant constraint if specified
        if allowed_merchants:
            merchant_rule = CategoryConstraint(
                rule_id=str(uuid.uuid4()),
                description="Only allow purchases from specified merchants",
                categories=allowed_merchants,
                constraint_type="allow",
                category_system="merchant_id",
                priority=30,
            )
            rules.append(merchant_rule)

        # Add category constraint if specified
        if allowed_categories:
            category_rule = CategoryConstraint(
                rule_id=str(uuid.uuid4()),
                description="Only allow purchases in specified categories",
                categories=allowed_categories,
                constraint_type="allow",
                category_system="product_category",
                priority=40,
            )
            rules.append(category_rule)

        return SpendingRuleSet(rules=rules, evaluation_mode="all")

    def evaluate_purchase_opportunity(
        self,
        mandate_id: str,
        product_name: str,
        price: float,
        currency: str,
        merchant_id: str,
        categories: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Evaluate whether a purchase opportunity meets mandate criteria.

        Args:
            mandate_id: ID of the mandate to check against
            product_name: Name of the product being considered
            price: Price of the product
            currency: Currency of the price
            merchant_id: ID of the merchant selling the product
            categories: Product categories

        Returns:
            Dictionary with evaluation results
        """
        if mandate_id not in self.active_mandates:
            return {
                "allowed": False,
                "reason": f"Mandate {mandate_id} not found",
            }

        mandate = self.active_mandates[mandate_id]

        # Validate the mandate first
        validation_result = self.validator.validate_mandate(mandate)
        if not validation_result.is_valid:
            return {
                "allowed": False,
                "reason": f"Mandate validation failed: {', '.join(validation_result.errors)}",
                "validation_result": validation_result,
            }

        # Evaluate specific transaction
        transaction_amount = PaymentCurrencyAmount(currency=currency, value=price)
        transaction_result = self.validator.validate_transaction_against_mandate(
            mandate, transaction_amount, merchant_id, categories
        )

        return {
            "allowed": transaction_result.is_valid,
            "reason": "Transaction approved" if transaction_result.is_valid
                     else f"Transaction rejected: {', '.join(transaction_result.errors)}",
            "product_name": product_name,
            "price": f"{price} {currency}",
            "merchant_id": merchant_id,
            "validation_result": transaction_result,
        }

    def execute_autonomous_purchase(
        self,
        mandate_id: str,
        product_name: str,
        price: float,
        currency: str,
        merchant_id: str,
        categories: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Execute an autonomous purchase (simulation).

        Args:
            mandate_id: ID of the mandate authorizing the purchase
            product_name: Name of the product to purchase
            price: Price of the product
            currency: Currency of the price
            merchant_id: ID of the merchant
            categories: Product categories

        Returns:
            Dictionary with purchase results
        """
        # First evaluate the opportunity
        evaluation = self.evaluate_purchase_opportunity(
            mandate_id, product_name, price, currency, merchant_id, categories
        )

        if not evaluation["allowed"]:
            return {
                "success": False,
                "reason": evaluation["reason"],
                "evaluation": evaluation,
            }

        # Simulate purchase execution
        purchase_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        # In a real implementation, this would:
        # 1. Create CartMandate with the merchant
        # 2. Execute payment through credentials provider
        # 3. Create PaymentMandate for the transaction
        # 4. Update spending rule tracking

        purchase_result = {
            "success": True,
            "purchase_id": purchase_id,
            "product_name": product_name,
            "price": f"{price} {currency}",
            "merchant_id": merchant_id,
            "timestamp": timestamp,
            "agent_did": self.agent_did,
            "mandate_id": mandate_id,
            "categories": categories or [],
        }

        print("✅ Autonomous purchase completed:")
        print(f"   Product: {product_name}")
        print(f"   Price: {price} {currency}")
        print(f"   Merchant: {merchant_id}")
        print(f"   Purchase ID: {purchase_id}")

        return purchase_result

    def list_active_mandates(self) -> List[Dict[str, Any]]:
        """List all active mandates for this agent."""
        mandates = []
        for mandate_id, mandate in self.active_mandates.items():
            validation = self.validator.validate_mandate(mandate)
            mandates.append({
                "mandate_id": mandate_id,
                "description": mandate.natural_language_description,
                "agent_did": mandate.agent_did,
                "expiry": mandate.intent_expiry,
                "is_valid": validation.is_valid,
                "spending_rules_count": len(mandate.spending_rules.rules),
                "user_confirmation_required": mandate.user_cart_confirmation_required,
            })
        return mandates


def main():
    """Main function demonstrating autonomous shopping capabilities."""
    parser = argparse.ArgumentParser(description="Autonomous Shopping Agent Demo")
    parser.add_argument("--intent", required=True, help="Shopping intent description")
    parser.add_argument("--budget", type=float, required=True, help="Maximum budget")
    parser.add_argument("--currency", default="USD", help="Currency code")
    parser.add_argument("--duration", type=int, default=24, help="Duration in hours")
    parser.add_argument("--merchants", nargs="*", help="Allowed merchant IDs")
    parser.add_argument("--categories", nargs="*", help="Allowed product categories")

    args = parser.parse_args()

    # Initialize agent
    agent_did = "did:kite:1:autonomous_shopper_" + str(uuid.uuid4())
    user_wallet = "0x" + "".join([str(uuid.uuid4()).replace("-", "")][:40])

    agent = AutonomousShoppingAgent(agent_did, user_wallet)

    print("🤖 Autonomous Shopping Agent Demo")
    print("=" * 50)
    print(f"Agent DID: {agent_did}")
    print(f"User Wallet: {user_wallet}")
    print()

    # Create autonomous mandate
    agent.create_autonomous_mandate(
        description=args.intent,
        max_budget=args.budget,
        currency=args.currency,
        duration_hours=args.duration,
        allowed_merchants=args.merchants,
        allowed_categories=args.categories,
    )

    print()
    print("📋 Active Mandates:")
    for mandate_info in agent.list_active_mandates():
        print(f"  ID: {mandate_info['mandate_id'][:8]}...")
        print(f"  Description: {mandate_info['description']}")
        print(f"  Valid: {mandate_info['is_valid']}")
        print(f"  Rules: {mandate_info['spending_rules_count']}")
        print()

    # Simulate some purchase opportunities
    print("🛍️ Evaluating Purchase Opportunities:")
    print("-" * 40)

    opportunities = [
        {
            "product_name": "Nike Air Max Running Shoes",
            "price": 150.0,
            "merchant_id": "nike_official",
            "categories": ["footwear", "running"],
        },
        {
            "product_name": "Expensive Designer Shoes",
            "price": 500.0,
            "merchant_id": "luxury_store",
            "categories": ["footwear", "luxury"],
        },
        {
            "product_name": "Budget Running Shoes",
            "price": 80.0,
            "merchant_id": "discount_sports",
            "categories": ["footwear", "running"],
        },
    ]

    mandate_id = list(agent.active_mandates.keys())[0]

    for opportunity in opportunities:
        print(f"\nEvaluating: {opportunity['product_name']}")
        evaluation = agent.evaluate_purchase_opportunity(
            mandate_id=mandate_id,
            currency=args.currency,
            **opportunity
        )

        print(f"  Price: {opportunity['price']} {args.currency}")
        print(f"  Allowed: {'✅' if evaluation['allowed'] else '❌'}")
        print(f"  Reason: {evaluation['reason']}")

        # If allowed, simulate purchase
        if evaluation["allowed"]:
            purchase = agent.execute_autonomous_purchase(
                mandate_id=mandate_id,
                currency=args.currency,
                **opportunity
            )
            if purchase["success"]:
                print(f"  ✅ Purchase completed: {purchase['purchase_id'][:8]}...")


if __name__ == "__main__":
    main()