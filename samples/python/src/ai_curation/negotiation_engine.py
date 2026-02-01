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

"""AI-Powered Negotiation and Dynamic Pricing Engine.

This module provides intelligent negotiation capabilities, dynamic pricing,
and advanced bundling strategies to maximize conversions and AOV.
"""

import json
import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import numpy as np
from pydantic import BaseModel, Field
from google import genai

logger = logging.getLogger(__name__)


class NegotiationStrategy(Enum):
    """Different negotiation strategies."""
    
    AGGRESSIVE = "aggressive"      # High discounts to close quickly
    BALANCED = "balanced"          # Moderate discounts with conditions
    CONSERVATIVE = "conservative"  # Small discounts, focus on value
    PREMIUM = "premium"           # No discounts, emphasize quality


class NegotiationStage(Enum):
    """Stages of negotiation process."""
    
    INITIAL_INTEREST = "initial_interest"
    PRICE_OBJECTION = "price_objection"
    COMPARISON_SHOPPING = "comparison_shopping"
    BUNDLE_CONSIDERATION = "bundle_consideration"
    FINAL_DECISION = "final_decision"
    ABANDONED = "abandoned"
    CLOSED = "closed"


@dataclass
class CustomerProfile:
    """Customer profile for negotiation."""
    
    customer_id: str
    price_sensitivity: float  # 0-1, higher = more price sensitive
    loyalty_score: float     # 0-1, higher = more loyal
    purchase_history_value: float
    negotiation_history: List[Dict[str, Any]]
    preferred_communication_style: str  # "direct", "consultative", "friendly"
    urgency_level: float    # 0-1, higher = more urgent
    
    def get_negotiation_strategy(self) -> NegotiationStrategy:
        """Determine best negotiation strategy for this customer."""
        
        if self.price_sensitivity > 0.8 and self.urgency_level > 0.7:
            return NegotiationStrategy.AGGRESSIVE
        elif self.loyalty_score > 0.7 and self.purchase_history_value > 1000:
            return NegotiationStrategy.PREMIUM
        elif self.price_sensitivity > 0.6:
            return NegotiationStrategy.BALANCED
        else:
            return NegotiationStrategy.CONSERVATIVE


class NegotiationOffer(BaseModel):
    """Represents a negotiation offer."""
    
    offer_id: str
    original_price: float
    offered_price: float
    discount_amount: float
    discount_percentage: float
    conditions: List[str] = []
    valid_until: datetime
    reasoning: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    bundle_items: Optional[List[Dict[str, Any]]] = None


class PricingRule(BaseModel):
    """Dynamic pricing rule."""
    
    rule_id: str
    condition: str
    action: str
    priority: int
    active: bool = True
    
    # Conditions
    min_cart_value: Optional[float] = None
    customer_segment: Optional[str] = None
    time_constraint: Optional[str] = None  # "hours_left", "days_left"
    inventory_level: Optional[str] = None  # "low", "medium", "high"
    
    # Actions
    discount_percentage: Optional[float] = None
    fixed_discount: Optional[float] = None
    free_shipping: bool = False
    bonus_items: Optional[List[str]] = None


class NegotiationEngine:
    """AI-powered negotiation and pricing engine."""
    
    def __init__(self):
        self.llm_client = genai.Client()
        self.active_negotiations: Dict[str, Dict[str, Any]] = {}
        self.pricing_rules: List[PricingRule] = self._initialize_pricing_rules()
        self.customer_profiles: Dict[str, CustomerProfile] = {}
        
    def _initialize_pricing_rules(self) -> List[PricingRule]:
        """Initialize default dynamic pricing rules."""
        
        return [
            PricingRule(
                rule_id="cart_value_discount",
                condition="cart_value >= min_cart_value",
                action="apply_percentage_discount",
                priority=1,
                min_cart_value=200,
                discount_percentage=10,
                free_shipping=True
            ),
            PricingRule(
                rule_id="new_customer_welcome",
                condition="customer_segment == 'new'",
                action="apply_percentage_discount",
                priority=2,
                customer_segment="new",
                discount_percentage=15
            ),
            PricingRule(
                rule_id="loyalty_reward",
                condition="customer_segment == 'vip'",
                action="apply_fixed_discount",
                priority=1,
                customer_segment="vip",
                fixed_discount=50,
                bonus_items=["free_gift_wrap"]
            ),
            PricingRule(
                rule_id="urgency_discount",
                condition="time_constraint == 'hours_left'",
                action="apply_percentage_discount",
                priority=3,
                time_constraint="hours_left",
                discount_percentage=20
            ),
            PricingRule(
                rule_id="low_inventory_push",
                condition="inventory_level == 'low'",
                action="apply_percentage_discount",
                priority=2,
                inventory_level="low",
                discount_percentage=12
            )
        ]
    
    def get_customer_profile(self, customer_id: str) -> CustomerProfile:
        """Get or create customer profile."""
        
        if customer_id not in self.customer_profiles:
            # Create new profile with default values
            self.customer_profiles[customer_id] = CustomerProfile(
                customer_id=customer_id,
                price_sensitivity=0.5,  # Will learn over time
                loyalty_score=0.0,
                purchase_history_value=0.0,
                negotiation_history=[],
                preferred_communication_style="friendly",
                urgency_level=0.3
            )
        
        return self.customer_profiles[customer_id]
    
    async def start_negotiation(
        self, 
        customer_id: str, 
        product: Dict[str, Any],
        customer_message: str
    ) -> NegotiationOffer:
        """Start a new negotiation session."""
        
        profile = self.get_customer_profile(customer_id)
        strategy = profile.get_negotiation_strategy()
        
        # Analyze customer intent
        intent_analysis = await self._analyze_negotiation_intent(customer_message)
        
        # Generate initial offer
        offer = self._generate_initial_offer(
            product, 
            profile, 
            strategy, 
            intent_analysis
        )
        
        # Track negotiation
        negotiation_id = f"{customer_id}_{product.get('id', 'unknown')}_{int(datetime.now().timestamp())}"
        self.active_negotiations[negotiation_id] = {
            "customer_id": customer_id,
            "product": product,
            "stage": NegotiationStage.INITIAL_INTEREST,
            "offers": [offer],
            "customer_messages": [customer_message],
            "start_time": datetime.now(timezone.utc)
        }
        
        return offer
    
    async def _analyze_negotiation_intent(self, message: str) -> Dict[str, Any]:
        """Analyze customer message for negotiation intent."""
        
        prompt = f"""
        Analyze this customer message for negotiation intent: "{message}"
        
        Return JSON with:
        - intent_type: "price_inquiry", "discount_request", "comparison", "bundle_interest", "value_concern"
        - urgency_level: 0.0-1.0 (how urgent they seem)
        - price_sensitivity: 0.0-1.0 (how price-focused they are)
        - negotiation_openness: 0.0-1.0 (how open to negotiation)
        - specific_concerns: list of specific concerns mentioned
        - budget_mentioned: true/false if they mentioned a budget
        - competitor_mentioned: true/false if they mentioned competitors
        """
        
        try:
            response = self.llm_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": {"type": "object"}
                }
            )
            
            return response.parsed if response.parsed else {}
            
        except Exception as e:
            logger.error(f"Error analyzing negotiation intent: {e}")
            return {
                "intent_type": "price_inquiry",
                "urgency_level": 0.5,
                "price_sensitivity": 0.5,
                "negotiation_openness": 0.5,
                "specific_concerns": [],
                "budget_mentioned": False,
                "competitor_mentioned": False
            }
    
    def _generate_initial_offer(
        self, 
        product: Dict[str, Any], 
        profile: CustomerProfile,
        strategy: NegotiationStrategy,
        intent_analysis: Dict[str, Any]
    ) -> NegotiationOffer:
        """Generate initial negotiation offer."""
        
        original_price = product.get("price", 100)
        
        # Base discount based on strategy
        strategy_discounts = {
            NegotiationStrategy.AGGRESSIVE: (0.15, 0.25),    # 15-25%
            NegotiationStrategy.BALANCED: (0.08, 0.15),      # 8-15%
            NegotiationStrategy.CONSERVATIVE: (0.03, 0.08),  # 3-8%
            NegotiationStrategy.PREMIUM: (0.0, 0.03)         # 0-3%
        }
        
        min_discount, max_discount = strategy_discounts[strategy]
        
        # Adjust based on customer analysis
        urgency_boost = intent_analysis.get("urgency_level", 0.5) * 0.05
        sensitivity_boost = intent_analysis.get("price_sensitivity", 0.5) * 0.08
        
        final_discount = min_discount + (max_discount - min_discount) * 0.7
        final_discount += urgency_boost + sensitivity_boost
        final_discount = max(0.0, min(0.3, final_discount))  # Cap at 30%
        
        # Apply dynamic pricing rules
        rule_discount = self._apply_pricing_rules(profile, original_price)
        final_discount = max(final_discount, rule_discount)
        
        # Calculate offer
        discount_amount = original_price * final_discount
        offered_price = original_price - discount_amount
        
        # Generate conditions and reasoning
        conditions = self._generate_offer_conditions(strategy, intent_analysis)
        reasoning = self._generate_offer_reasoning(strategy, final_discount, conditions)
        
        return NegotiationOffer(
            offer_id=f"offer_{int(datetime.now().timestamp())}",
            original_price=original_price,
            offered_price=offered_price,
            discount_amount=discount_amount,
            discount_percentage=final_discount * 100,
            conditions=conditions,
            valid_until=datetime.now(timezone.utc) + timedelta(hours=24),
            reasoning=reasoning,
            confidence_score=0.8
        )
    
    def _apply_pricing_rules(self, profile: CustomerProfile, cart_value: float) -> float:
        """Apply dynamic pricing rules."""
        
        max_discount = 0.0
        
        for rule in sorted(self.pricing_rules, key=lambda x: x.priority):
            if not rule.active:
                continue
                
            discount = 0.0
            
            # Check conditions
            if rule.min_cart_value and cart_value < rule.min_cart_value:
                continue
                
            if rule.customer_segment:
                customer_segment = self._determine_customer_segment(profile)
                if customer_segment != rule.customer_segment:
                    continue
            
            # Apply discount
            if rule.discount_percentage:
                discount = rule.discount_percentage / 100
            elif rule.fixed_discount:
                discount = rule.fixed_discount / cart_value
                
            max_discount = max(max_discount, discount)
        
        return max_discount
    
    def _determine_customer_segment(self, profile: CustomerProfile) -> str:
        """Determine customer segment."""
        
        if profile.purchase_history_value > 2000 and profile.loyalty_score > 0.8:
            return "vip"
        elif profile.purchase_history_value == 0:
            return "new"
        elif profile.purchase_history_value > 500:
            return "regular"
        else:
            return "occasional"
    
    def _generate_offer_conditions(
        self, 
        strategy: NegotiationStrategy, 
        intent_analysis: Dict[str, Any]
    ) -> List[str]:
        """Generate conditions for the offer."""
        
        conditions = []
        
        if strategy == NegotiationStrategy.AGGRESSIVE:
            conditions.extend([
                "Limited time offer - expires in 24 hours",
                "While supplies last"
            ])
        elif strategy == NegotiationStrategy.BALANCED:
            conditions.extend([
                "Add to cart within 2 hours to secure this price",
                "Free shipping included"
            ])
        elif strategy == NegotiationStrategy.CONSERVATIVE:
            conditions.extend([
                "Valid for 48 hours",
                "Minimum purchase of $100"
            ])
        
        # Add conditions based on intent
        if intent_analysis.get("comparison_shopping"):
            conditions.append("Price match guarantee included")
            
        if intent_analysis.get("urgency_level", 0) > 0.7:
            conditions.append("Express shipping available")
        
        return conditions
    
    def _generate_offer_reasoning(
        self, 
        strategy: NegotiationStrategy, 
        discount: float, 
        conditions: List[str]
    ) -> str:
        """Generate reasoning for the offer."""
        
        discount_percent = discount * 100
        
        if strategy == NegotiationStrategy.AGGRESSIVE:
            return (f"I can offer you an exclusive {discount_percent:.0f}% discount "
                   f"because we're clearing inventory this week. This is our best price!")
        elif strategy == NegotiationStrategy.BALANCED:
            return (f"I'd like to offer you {discount_percent:.0f}% off this great product. "
                   f"It's a fantastic deal that includes free shipping.")
        elif strategy == NegotiationStrategy.CONSERVATIVE:
            return (f"I can provide a {discount_percent:.0f}% valued customer discount "
                   f"on this premium item. The quality speaks for itself.")
        else:  # PREMIUM
            return ("This is a premium product at its regular price. "
                   "The value comes from the exceptional quality and service.")
    
    async def create_smart_bundle(
        self, 
        primary_product: Dict[str, Any],
        related_products: List[Dict[str, Any]],
        customer_id: str
    ) -> Dict[str, Any]:
        """Create an intelligent product bundle."""
        
        profile = self.get_customer_profile(customer_id)
        
        # Select complementary products using AI
        bundle_products = await self._select_bundle_products(
            primary_product, related_products, profile
        )
        
        # Calculate bundle pricing
        total_original_price = sum(p.get("price", 0) for p in bundle_products)
        
        # Dynamic bundle discount based on customer profile
        base_bundle_discount = 0.12  # 12% base bundle discount
        loyalty_bonus = profile.loyalty_score * 0.05
        volume_bonus = min(len(bundle_products) * 0.02, 0.08)
        
        total_discount = base_bundle_discount + loyalty_bonus + volume_bonus
        total_discount = min(total_discount, 0.25)  # Cap at 25%
        
        bundle_price = total_original_price * (1 - total_discount)
        savings = total_original_price - bundle_price
        
        # Generate bundle description
        bundle_description = await self._generate_bundle_description(bundle_products)
        
        return {
            "type": "smart_bundle",
            "id": f"bundle_{int(datetime.now().timestamp())}",
            "name": bundle_description["name"],
            "description": bundle_description["description"],
            "products": bundle_products,
            "original_price": total_original_price,
            "bundle_price": bundle_price,
            "savings": savings,
            "discount_percentage": total_discount * 100,
            "value_proposition": bundle_description["value_proposition"],
            "valid_until": datetime.now(timezone.utc) + timedelta(hours=48),
            "personalization_score": self._calculate_bundle_score(bundle_products, profile)
        }
    
    async def _select_bundle_products(
        self, 
        primary_product: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        profile: CustomerProfile
    ) -> List[Dict[str, Any]]:
        """Select best products for bundle using AI."""
        
        # Start with primary product
        bundle_products = [primary_product]
        
        if not candidates:
            return bundle_products
        
        # Use LLM to select complementary products
        prompt = f"""
        Given this primary product: {json.dumps(primary_product, indent=2)}
        
        And these candidate products: {json.dumps(candidates[:10], indent=2)}
        
        Select 1-3 products that would create the most compelling bundle for a customer.
        Consider:
        - Complementary functionality
        - Price balance (not all expensive items)
        - Logical grouping
        - Customer value
        
        Return JSON array of selected product indices (0-based).
        """
        
        try:
            response = self.llm_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": {"type": "array", "items": {"type": "integer"}}
                }
            )
            
            selected_indices = response.parsed if response.parsed else [0]
            
            # Add selected products to bundle
            for idx in selected_indices:
                if 0 <= idx < len(candidates):
                    bundle_products.append(candidates[idx])
                    
        except Exception as e:
            logger.error(f"Error selecting bundle products: {e}")
            # Fallback: add first candidate
            if candidates:
                bundle_products.append(candidates[0])
        
        return bundle_products
    
    async def _generate_bundle_description(
        self, 
        products: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """Generate compelling bundle name and description."""
        
        prompt = f"""
        Create a compelling bundle name and description for these products:
        {json.dumps(products, indent=2)}
        
        Return JSON with:
        - name: Catchy bundle name (max 50 chars)
        - description: Brief description explaining why these go together (max 100 chars)
        - value_proposition: Why this bundle is a great deal (max 80 chars)
        """
        
        try:
            response = self.llm_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": {"type": "object"}
                }
            )
            
            return response.parsed if response.parsed else {
                "name": "Perfect Bundle",
                "description": "Everything you need in one package",
                "value_proposition": "Save money and get complete solution"
            }
            
        except Exception as e:
            logger.error(f"Error generating bundle description: {e}")
            return {
                "name": "Special Bundle",
                "description": "Carefully selected products that work great together",
                "value_proposition": "Better value when purchased together"
            }
    
    def _calculate_bundle_score(
        self, 
        products: List[Dict[str, Any]], 
        profile: CustomerProfile
    ) -> float:
        """Calculate bundle appeal score for customer."""
        
        # Factor in customer preferences, price sensitivity, etc.
        base_score = 0.7
        
        # Adjust for price sensitivity
        total_price = sum(p.get("price", 0) for p in products)
        if profile.price_sensitivity > 0.7 and total_price > 300:
            base_score -= 0.2
        elif profile.price_sensitivity < 0.3:
            base_score += 0.1
        
        # Adjust for product variety
        categories = set(p.get("category", "other") for p in products)
        if len(categories) > 1:
            base_score += 0.1
        
        return max(0.0, min(1.0, base_score))
    
    def handle_counter_offer(
        self, 
        negotiation_id: str, 
        customer_message: str
    ) -> NegotiationOffer:
        """Handle customer counter-offer or objection."""
        
        if negotiation_id not in self.active_negotiations:
            raise ValueError("Negotiation not found")
        
        negotiation = self.active_negotiations[negotiation_id]
        profile = self.get_customer_profile(negotiation["customer_id"])
        
        # Analyze counter-offer
        intent = self._analyze_counter_offer(customer_message)
        
        # Update negotiation stage
        negotiation["stage"] = self._determine_next_stage(intent, negotiation["stage"])
        negotiation["customer_messages"].append(customer_message)
        
        # Generate counter-offer
        counter_offer = self._generate_counter_offer(negotiation, profile, intent)
        negotiation["offers"].append(counter_offer)
        
        return counter_offer
    
    def _analyze_counter_offer(self, message: str) -> Dict[str, Any]:
        """Analyze customer counter-offer."""
        
        # Simple analysis - in production, use more sophisticated NLP
        message_lower = message.lower()
        
        intent = {
            "type": "general",
            "price_mentioned": any(word in message_lower for word in ["price", "cost", "expensive", "cheap", "budget"]),
            "comparison_mentioned": any(word in message_lower for word in ["competitor", "amazon", "elsewhere", "found"]),
            "value_concern": any(word in message_lower for word in ["worth", "value", "quality", "features"]),
            "urgency": any(word in message_lower for word in ["urgent", "need", "soon", "today", "now"]),
            "interest_level": 0.5
        }
        
        # Estimate interest level
        positive_words = ["interested", "like", "good", "great", "yes", "okay"]
        negative_words = ["expensive", "much", "high", "no", "not", "can't"]
        
        positive_count = sum(1 for word in positive_words if word in message_lower)
        negative_count = sum(1 for word in negative_words if word in message_lower)
        
        if positive_count > negative_count:
            intent["interest_level"] = 0.7
        elif negative_count > positive_count:
            intent["interest_level"] = 0.3
        
        return intent
    
    def _determine_next_stage(
        self, 
        intent: Dict[str, Any], 
        current_stage: NegotiationStage
    ) -> NegotiationStage:
        """Determine next negotiation stage."""
        
        if intent["price_mentioned"]:
            return NegotiationStage.PRICE_OBJECTION
        elif intent["comparison_mentioned"]:
            return NegotiationStage.COMPARISON_SHOPPING
        elif intent["interest_level"] > 0.6:
            return NegotiationStage.FINAL_DECISION
        elif intent["interest_level"] < 0.3:
            return NegotiationStage.ABANDONED
        else:
            return current_stage
    
    def _generate_counter_offer(
        self, 
        negotiation: Dict[str, Any], 
        profile: CustomerProfile,
        intent: Dict[str, Any]
    ) -> NegotiationOffer:
        """Generate counter-offer based on negotiation progress."""
        
        last_offer = negotiation["offers"][-1]
        product = negotiation["product"]
        
        # Adjust offer based on negotiation progress
        additional_discount = 0.0
        
        if negotiation["stage"] == NegotiationStage.PRICE_OBJECTION:
            additional_discount = 0.05  # Additional 5%
        elif negotiation["stage"] == NegotiationStage.COMPARISON_SHOPPING:
            additional_discount = 0.08  # Beat competition
        elif len(negotiation["offers"]) > 2:
            additional_discount = 0.03  # Persistence bonus
        
        # Cap total discount
        new_discount = last_offer.discount_percentage / 100 + additional_discount
        new_discount = min(new_discount, 0.35)  # Max 35% total discount
        
        # Generate new offer
        original_price = product.get("price", 100)
        discount_amount = original_price * new_discount
        offered_price = original_price - discount_amount
        
        # Update conditions
        conditions = last_offer.conditions.copy()
        if negotiation["stage"] == NegotiationStage.FINAL_DECISION:
            conditions.append("Final offer - expires in 2 hours")
        
        return NegotiationOffer(
            offer_id=f"offer_{int(datetime.now().timestamp())}",
            original_price=original_price,
            offered_price=offered_price,
            discount_amount=discount_amount,
            discount_percentage=new_discount * 100,
            conditions=conditions,
            valid_until=datetime.now(timezone.utc) + timedelta(hours=2),
            reasoning=f"Based on your feedback, I can offer an additional {additional_discount*100:.1f}% discount.",
            confidence_score=0.7
        )
    
    def get_negotiation_analytics(self) -> Dict[str, Any]:
        """Get negotiation performance analytics."""
        
        total_negotiations = len(self.active_negotiations)
        closed_negotiations = sum(
            1 for n in self.active_negotiations.values() 
            if n["stage"] == NegotiationStage.CLOSED
        )
        
        average_discount = 0.0
        if total_negotiations > 0:
            total_discount = sum(
                offer.discount_percentage for n in self.active_negotiations.values()
                for offer in n["offers"]
            ) / max(1, sum(len(n["offers"]) for n in self.active_negotiations.values()))
            average_discount = total_discount
        
        return {
            "total_negotiations": total_negotiations,
            "closed_negotiations": closed_negotiations,
            "conversion_rate": closed_negotiations / max(1, total_negotiations),
            "average_discount_offered": average_discount,
            "active_negotiations": total_negotiations - closed_negotiations,
            "average_offers_per_negotiation": sum(
                len(n["offers"]) for n in self.active_negotiations.values()
            ) / max(1, total_negotiations)
        }


# Global instance
negotiation_engine = NegotiationEngine()