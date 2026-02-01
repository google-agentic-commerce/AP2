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

"""Advanced Checkout Optimization and Cart Abandonment Recovery.

This module provides intelligent checkout optimization, cart abandonment recovery,
one-click purchasing, and conversion optimization features to maximize sales.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal, ROUND_HALF_UP

import numpy as np
import aiohttp
from pydantic import BaseModel, Field
from google import genai

from ap2.types.mandate import CartMandate
from ai_curation.negotiation_engine import negotiation_engine

logger = logging.getLogger(__name__)


class CheckoutStage(Enum):
    """Checkout process stages."""
    
    CART_REVIEW = "cart_review"
    SHIPPING_INFO = "shipping_info"
    PAYMENT_METHOD = "payment_method"
    CURRENCY_CONVERSION = "currency_conversion"
    ORDER_CONFIRMATION = "order_confirmation"
    PAYMENT_PROCESSING = "payment_processing"
    SETTLEMENT_PROCESSING = "settlement_processing"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class PaymentStatus(Enum):
    """Payment processing status."""
    
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    SETTLED = "settled"
    FAILED = "failed"
    REFUNDED = "refunded"
    DISPUTED = "disputed"


class CurrencyCode(Enum):
    """Supported currency codes."""
    
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    CAD = "CAD"
    AUD = "AUD"
    CHF = "CHF"
    CNY = "CNY"
    INR = "INR"
    BRL = "BRL"


class AbandonmentReason(Enum):
    """Common cart abandonment reasons."""
    
    HIGH_PRICE = "high_price"
    UNEXPECTED_COSTS = "unexpected_costs"
    COMPLEX_CHECKOUT = "complex_checkout"
    SECURITY_CONCERNS = "security_concerns"
    COMPARISON_SHOPPING = "comparison_shopping"
    NO_URGENCY = "no_urgency"
    TECHNICAL_ISSUES = "technical_issues"
    CHANGED_MIND = "changed_mind"
    CURRENCY_CONCERNS = "currency_concerns"
    PAYMENT_FAILED = "payment_failed"


@dataclass
class PaymentDetails:
    """Payment processing details."""
    
    payment_id: str
    amount: Decimal
    original_currency: CurrencyCode
    customer_currency: CurrencyCode
    converted_amount: Decimal
    exchange_rate: Decimal
    payment_method: str
    status: PaymentStatus
    
    # Transaction details
    authorization_id: Optional[str] = None
    capture_id: Optional[str] = None
    settlement_id: Optional[str] = None
    
    # Timestamps
    initiated_at: Optional[datetime] = None
    authorized_at: Optional[datetime] = None
    captured_at: Optional[datetime] = None
    settled_at: Optional[datetime] = None
    
    # Fees and processing
    processing_fee: Decimal = Decimal('0.00')
    currency_conversion_fee: Decimal = Decimal('0.00')
    settlement_fee: Decimal = Decimal('0.00')
    
    # Error handling
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0


@dataclass
class SettlementDetails:
    """Settlement processing details."""
    
    settlement_id: str
    payment_id: str
    merchant_account: str
    settlement_amount: Decimal
    settlement_currency: CurrencyCode
    settlement_date: datetime
    
    # Batch processing
    batch_id: Optional[str] = None
    batch_sequence: Optional[int] = None
    
    # Fees breakdown
    processing_fees: Decimal = Decimal('0.00')
    network_fees: Decimal = Decimal('0.00')
    fx_fees: Decimal = Decimal('0.00')
    
    # Status tracking
    status: str = "pending"
    confirmation_number: Optional[str] = None


@dataclass
class CheckoutSession:
    """Tracks individual checkout session."""
    
    session_id: str
    customer_id: str
    cart_items: List[Dict[str, Any]]
    current_stage: CheckoutStage
    start_time: datetime
    last_activity: datetime
    
    # Progress tracking
    stages_completed: List[CheckoutStage]
    time_per_stage: Dict[CheckoutStage, float]
    
    # Customer behavior
    hesitation_points: List[Dict[str, Any]]
    support_requests: List[str]
    price_sensitivity_signals: List[str]
    
    # Optimization data
    applied_incentives: List[Dict[str, Any]]
    recovery_attempts: int
    conversion_probability: float
    
    # Payment processing
    payment_details: Optional[PaymentDetails] = None
    settlement_details: Optional[SettlementDetails] = None
    
    # Currency preferences
    customer_currency: Optional[CurrencyCode] = None
    detected_location: Optional[str] = None
    currency_auto_detected: bool = False


class ConversionOptimizer:
    """Optimizes checkout conversion rates with automatic payment processing."""
    
    def __init__(self):
        self.llm_client = genai.Client()
        self.active_sessions: Dict[str, CheckoutSession] = {}
        self.abandonment_patterns: Dict[str, List[Dict[str, Any]]] = {}
        
        # Payment processing
        self.payment_processors = self._initialize_payment_processors()
        self.currency_service = CurrencyConversionService()
        self.settlement_service = SettlementService()
        
        # Recovery strategies
        self.recovery_strategies = self._initialize_recovery_strategies()
        
        # Start background tasks
        asyncio.create_task(self._monitor_sessions())
        asyncio.create_task(self._process_recovery_queue())
        asyncio.create_task(self._process_settlements())
    
    def _initialize_payment_processors(self) -> Dict[str, Any]:
        """Initialize payment processing configurations."""
        
        return {
            "stripe": {
                "api_key": "sk_test_...",  # From environment
                "webhook_secret": "whsec_...",
                "supported_currencies": ["USD", "EUR", "GBP", "CAD", "AUD"],
                "fees": {
                    "domestic": Decimal("0.029"),  # 2.9%
                    "international": Decimal("0.039"),  # 3.9%
                    "currency_conversion": Decimal("0.01")  # 1%
                }
            },
            "paypal": {
                "client_id": "...",
                "client_secret": "...",
                "supported_currencies": ["USD", "EUR", "GBP", "JPY", "CAD"],
                "fees": {
                    "domestic": Decimal("0.0349"),  # 3.49%
                    "international": Decimal("0.0499"),  # 4.99%
                    "currency_conversion": Decimal("0.025")  # 2.5%
                }
            },
            "ap2": {
                "merchant_id": "...",
                "api_endpoint": "https://ap2.googleapis.com/v1",
                "supported_currencies": ["USD", "EUR", "GBP", "JPY", "CAD", "AUD"],
                "fees": {
                    "domestic": Decimal("0.015"),  # 1.5%
                    "international": Decimal("0.025"),  # 2.5%
                    "currency_conversion": Decimal("0.005")  # 0.5%
                }
            }
        }
    
    def _initialize_recovery_strategies(self) -> List[Dict[str, Any]]:
        """Initialize cart abandonment recovery strategies."""
        
        return [
            {
                "name": "immediate_discount",
                "trigger_delay": 30,  # seconds
                "conditions": ["price_sensitivity_high"],
                "action": "offer_discount",
                "discount_percentage": 10,
                "message": "Wait! I can offer you 10% off if you complete your purchase in the next 15 minutes!"
            },
            {
                "name": "free_shipping",
                "trigger_delay": 60,
                "conditions": ["unexpected_costs"],
                "action": "offer_free_shipping",
                "message": "I noticed shipping costs might be a concern. Let me offer you free shipping on this order!"
            },
            {
                "name": "limited_time_offer",
                "trigger_delay": 120,
                "conditions": ["no_urgency"],
                "action": "create_urgency",
                "message": "🔥 This item is popular! Only 3 left in stock. Secure yours now before it's gone!"
            },
            {
                "name": "customer_support",
                "trigger_delay": 180,
                "conditions": ["technical_issues", "security_concerns"],
                "action": "offer_support",
                "message": "Having trouble with checkout? I'm here to help! Let me guide you through the process."
            },
            {
                "name": "social_proof",
                "trigger_delay": 240,
                "conditions": ["comparison_shopping"],
                "action": "show_social_proof",
                "message": "💯 Over 1,000 customers bought this item this month! Join them with our secure, trusted checkout."
            },
            {
                "name": "payment_options",
                "trigger_delay": 300,
                "conditions": ["payment_concerns"],
                "action": "show_payment_options",
                "message": "💳 Multiple secure payment options available: Credit card, PayPal, Apple Pay, and more!"
            },
            {
                "name": "currency_assistance",
                "trigger_delay": 120,
                "conditions": ["currency_concerns"],
                "action": "offer_currency_help",
                "message": "💱 I can display prices in your local currency and handle automatic conversion at checkout!"
            },
            {
                "name": "payment_retry",
                "trigger_delay": 60,
                "conditions": ["payment_failed"],
                "action": "offer_payment_retry",
                "message": "💳 Payment didn't go through? Let me help you try a different payment method or resolve any issues."
            }
        ]
    
    # Payment Processing Methods
    
    async def detect_customer_currency(self, session_id: str, customer_ip: str = None) -> CurrencyCode:
        """Auto-detect customer's preferred currency based on location."""
        
        if session_id not in self.active_sessions:
            return CurrencyCode.USD  # Default fallback
        
        session = self.active_sessions[session_id]
        
        # Try to detect from IP geolocation
        if customer_ip:
            try:
                async with aiohttp.ClientSession() as http_session:
                    async with http_session.get(f"http://ip-api.com/json/{customer_ip}") as response:
                        if response.status == 200:
                            geo_data = await response.json()
                            country_code = geo_data.get("countryCode", "US")
                            
                            # Map country to currency
                            currency_map = {
                                "US": CurrencyCode.USD,
                                "GB": CurrencyCode.GBP,
                                "DE": CurrencyCode.EUR, "FR": CurrencyCode.EUR, "IT": CurrencyCode.EUR,
                                "JP": CurrencyCode.JPY,
                                "CA": CurrencyCode.CAD,
                                "AU": CurrencyCode.AUD,
                                "CH": CurrencyCode.CHF,
                                "CN": CurrencyCode.CNY,
                                "IN": CurrencyCode.INR,
                                "BR": CurrencyCode.BRL
                            }
                            
                            detected_currency = currency_map.get(country_code, CurrencyCode.USD)
                            session.customer_currency = detected_currency
                            session.detected_location = country_code
                            session.currency_auto_detected = True
                            
                            logger.info(f"Auto-detected currency {detected_currency.value} for session {session_id}")
                            return detected_currency
                            
            except Exception as e:
                logger.warning(f"Failed to detect currency from IP: {e}")
        
        # Fallback to USD
        session.customer_currency = CurrencyCode.USD
        return CurrencyCode.USD
    
    async def initiate_payment(
        self, 
        session_id: str, 
        payment_method: str = "ap2",
        amount: Decimal = None,
        original_currency: CurrencyCode = CurrencyCode.USD
    ) -> PaymentDetails:
        """Initiate payment processing with automatic currency conversion."""
        
        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.active_sessions[session_id]
        
        # Calculate total amount if not provided
        if amount is None:
            amount = Decimal(str(sum(item.get("price", 0) for item in session.cart_items)))
        
        # Detect customer currency if not set
        if not session.customer_currency:
            await self.detect_customer_currency(session_id)
        
        customer_currency = session.customer_currency or CurrencyCode.USD
        
        # Get exchange rate and convert amount
        exchange_rate, converted_amount, conversion_fee = await self.currency_service.convert_currency(
            amount, original_currency, customer_currency
        )
        
        # Generate payment ID
        payment_id = f"pay_{session_id}_{int(datetime.now().timestamp())}"
        
        # Create payment details
        payment_details = PaymentDetails(
            payment_id=payment_id,
            amount=amount,
            original_currency=original_currency,
            customer_currency=customer_currency,
            converted_amount=converted_amount,
            exchange_rate=exchange_rate,
            payment_method=payment_method,
            status=PaymentStatus.PENDING,
            initiated_at=datetime.now(timezone.utc),
            currency_conversion_fee=conversion_fee
        )
        
        # Store payment details
        session.payment_details = payment_details
        session.current_stage = CheckoutStage.PAYMENT_PROCESSING
        
        # Process payment based on method
        try:
            if payment_method == "ap2":
                await self._process_ap2_payment(payment_details)
            elif payment_method == "stripe":
                await self._process_stripe_payment(payment_details)
            elif payment_method == "paypal":
                await self._process_paypal_payment(payment_details)
            else:
                raise ValueError(f"Unsupported payment method: {payment_method}")
            
            logger.info(f"Payment initiated for session {session_id}: {payment_id}")
            
        except Exception as e:
            payment_details.status = PaymentStatus.FAILED
            payment_details.error_message = str(e)
            logger.error(f"Payment failed for session {session_id}: {e}")
            raise
        
        return payment_details
    
    async def start_checkout_session(
        self, 
        customer_id: str, 
        cart_items: List[Dict[str, Any]]
    ) -> str:
        """Start a new checkout session."""
        
        session_id = f"checkout_{customer_id}_{int(datetime.now().timestamp())}"
        
        session = CheckoutSession(
            session_id=session_id,
            customer_id=customer_id,
            cart_items=cart_items,
            current_stage=CheckoutStage.CART_REVIEW,
            start_time=datetime.now(timezone.utc),
            last_activity=datetime.now(timezone.utc),
            stages_completed=[],
            time_per_stage={},
            hesitation_points=[],
            support_requests=[],
            price_sensitivity_signals=[],
            applied_incentives=[],
            recovery_attempts=0,
            conversion_probability=self._calculate_initial_conversion_probability(customer_id, cart_items)
        )
        
        self.active_sessions[session_id] = session
        
        logger.info(f"Started checkout session {session_id} for customer {customer_id}")
        
        return session_id
    
    def _calculate_initial_conversion_probability(
        self, 
        customer_id: str, 
        cart_items: List[Dict[str, Any]]
    ) -> float:
        """Calculate initial conversion probability."""
        
        base_probability = 0.7  # 70% base conversion rate
        
        # Adjust based on cart value
        cart_value = sum(item.get("price", 0) for item in cart_items)
        if cart_value > 500:
            base_probability -= 0.1  # Higher cart value = slight hesitation
        elif cart_value < 50:
            base_probability += 0.1  # Low cart value = easier decision
        
        # Adjust based on customer history (mock)
        # In production, this would use real customer data
        customer_history_score = 0.8  # Mock score
        base_probability = (base_probability + customer_history_score) / 2
        
        return max(0.1, min(0.9, base_probability))
    
    async def track_checkout_progress(
        self, 
        session_id: str, 
        stage: CheckoutStage,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Track checkout progress and detect potential issues."""
        
        if session_id not in self.active_sessions:
            logger.warning(f"Session {session_id} not found")
            return
        
        session = self.active_sessions[session_id]
        previous_stage = session.current_stage
        
        # Calculate time spent in previous stage
        if previous_stage not in session.time_per_stage:
            session.time_per_stage[previous_stage] = 0
        
        time_spent = (datetime.now(timezone.utc) - session.last_activity).total_seconds()
        session.time_per_stage[previous_stage] += time_spent
        
        # Update session
        session.current_stage = stage
        session.last_activity = datetime.now(timezone.utc)
        
        if stage not in session.stages_completed:
            session.stages_completed.append(stage)
        
        # Detect hesitation patterns
        await self._detect_hesitation(session, previous_stage, time_spent, metadata)
        
        # Update conversion probability
        session.conversion_probability = await self._update_conversion_probability(session)
        
        logger.info(f"Session {session_id} progressed to {stage.value}")
    
    async def _detect_hesitation(
        self, 
        session: CheckoutSession, 
        stage: CheckoutStage,
        time_spent: float,
        metadata: Optional[Dict[str, Any]]
    ):
        """Detect customer hesitation patterns."""
        
        # Time-based hesitation detection
        stage_thresholds = {
            CheckoutStage.CART_REVIEW: 120,      # 2 minutes
            CheckoutStage.SHIPPING_INFO: 180,    # 3 minutes
            CheckoutStage.PAYMENT_METHOD: 240,   # 4 minutes
            CheckoutStage.ORDER_CONFIRMATION: 60 # 1 minute
        }
        
        if stage in stage_thresholds and time_spent > stage_thresholds[stage]:
            hesitation_point = {
                "stage": stage.value,
                "time_spent": time_spent,
                "timestamp": datetime.now(timezone.utc),
                "reason": "excessive_time",
                "metadata": metadata or {}
            }
            session.hesitation_points.append(hesitation_point)
            
            # Trigger intervention
            await self._trigger_intervention(session, hesitation_point)
    
    async def _trigger_intervention(
        self, 
        session: CheckoutSession, 
        hesitation_point: Dict[str, Any]
    ):
        """Trigger appropriate intervention for hesitation."""
        
        # Find suitable recovery strategy
        suitable_strategies = []
        
        for strategy in self.recovery_strategies:
            if self._strategy_matches_situation(strategy, session, hesitation_point):
                suitable_strategies.append(strategy)
        
        if suitable_strategies:
            # Use most relevant strategy
            best_strategy = max(
                suitable_strategies, 
                key=lambda s: self._calculate_strategy_relevance(s, session)
            )
            
            await self._apply_recovery_strategy(session, best_strategy)
    
    def _strategy_matches_situation(
        self, 
        strategy: Dict[str, Any], 
        session: CheckoutSession,
        hesitation_point: Dict[str, Any]
    ) -> bool:
        """Check if strategy matches current situation."""
        
        conditions = strategy.get("conditions", [])
        
        # Check various conditions
        if "price_sensitivity_high" in conditions:
            return len(session.price_sensitivity_signals) > 0
        
        if "unexpected_costs" in conditions:
            return hesitation_point["stage"] == CheckoutStage.SHIPPING_INFO.value
        
        if "technical_issues" in conditions:
            return len(session.support_requests) > 0
        
        if "no_urgency" in conditions:
            cart_value = sum(item.get("price", 0) for item in session.cart_items)
            return cart_value < 200
        
        return True  # Default: strategy applies
    
    def _calculate_strategy_relevance(
        self, 
        strategy: Dict[str, Any], 
        session: CheckoutSession
    ) -> float:
        """Calculate how relevant a strategy is for this session."""
        
        relevance = 0.5  # Base relevance
        
        # Higher relevance for fewer recovery attempts
        if session.recovery_attempts == 0:
            relevance += 0.3
        elif session.recovery_attempts == 1:
            relevance += 0.1
        else:
            relevance -= 0.2
        
        # Adjust based on conversion probability
        if session.conversion_probability < 0.5:
            relevance += 0.2  # More aggressive for low probability
        
        return max(0.0, min(1.0, relevance))
    
    async def _apply_recovery_strategy(
        self, 
        session: CheckoutSession, 
        strategy: Dict[str, Any]
    ):
        """Apply recovery strategy to prevent abandonment."""
        
        incentive = {
            "strategy_name": strategy["name"],
            "applied_at": datetime.now(timezone.utc),
            "stage": session.current_stage.value,
            "message": strategy["message"]
        }
        
        # Apply specific actions
        action = strategy.get("action")
        
        if action == "offer_discount":
            discount_percentage = strategy.get("discount_percentage", 10)
            incentive["discount_percentage"] = discount_percentage
            incentive["discount_amount"] = self._calculate_discount_amount(session, discount_percentage)
        
        elif action == "offer_free_shipping":
            incentive["free_shipping"] = True
            incentive["shipping_savings"] = 15  # Mock shipping cost
        
        elif action == "create_urgency":
            incentive["urgency_message"] = True
            incentive["stock_level"] = "low"
        
        session.applied_incentives.append(incentive)
        session.recovery_attempts += 1
        
        # Send intervention message (would integrate with chat system)
        await self._send_intervention_message(session, incentive)
        
        logger.info(f"Applied recovery strategy '{strategy['name']}' to session {session.session_id}")
    
    def _calculate_discount_amount(self, session: CheckoutSession, percentage: float) -> float:
        """Calculate discount amount for cart."""
        
        cart_total = sum(item.get("price", 0) for item in session.cart_items)
        return cart_total * (percentage / 100)
    
    async def _send_intervention_message(
        self, 
        session: CheckoutSession, 
        incentive: Dict[str, Any]
    ):
        """Send intervention message to customer."""
        
        # This would integrate with the unified chat manager
        message = incentive["message"]
        
        # Add specific details based on incentive type
        if "discount_percentage" in incentive:
            savings = incentive["discount_amount"]
            message += f" You'll save ${savings:.2f}!"
        
        if "free_shipping" in incentive:
            message += f" Plus free shipping (save ${incentive['shipping_savings']})!"
        
        # Mock sending message
        logger.info(f"Intervention message for {session.customer_id}: {message}")
        
        # In production, this would send through the chat system:
        # await chat_manager.send_message(session.customer_id, message)
    
    async def _update_conversion_probability(self, session: CheckoutSession) -> float:
        """Update conversion probability based on session progress."""
        
        base_probability = session.conversion_probability
        
        # Positive factors
        stages_completed_count = len(session.stages_completed)
        stage_completion_bonus = stages_completed_count * 0.05
        
        # Negative factors
        hesitation_penalty = len(session.hesitation_points) * 0.1
        time_penalty = max(0, (datetime.now(timezone.utc) - session.start_time).total_seconds() / 3600 - 0.5) * 0.1
        
        # Recovery factor
        recovery_bonus = len(session.applied_incentives) * 0.05
        
        new_probability = base_probability + stage_completion_bonus + recovery_bonus - hesitation_penalty - time_penalty
        
        return max(0.1, min(0.9, new_probability))
    
    async def handle_abandonment(self, session_id: str, reason: AbandonmentReason):
        """Handle cart abandonment with follow-up strategy."""
        
        if session_id not in self.active_sessions:
            return
        
        session = self.active_sessions[session_id]
        session.current_stage = CheckoutStage.ABANDONED
        
        # Record abandonment pattern
        abandonment_data = {
            "customer_id": session.customer_id,
            "reason": reason.value,
            "stage": session.current_stage.value,
            "cart_value": sum(item.get("price", 0) for item in session.cart_items),
            "time_to_abandonment": (datetime.now(timezone.utc) - session.start_time).total_seconds(),
            "hesitation_points": len(session.hesitation_points),
            "recovery_attempts": session.recovery_attempts
        }
        
        if session.customer_id not in self.abandonment_patterns:
            self.abandonment_patterns[session.customer_id] = []
        
        self.abandonment_patterns[session.customer_id].append(abandonment_data)
        
        # Schedule follow-up recovery
        await self._schedule_follow_up_recovery(session, reason)
        
        logger.info(f"Session {session_id} abandoned at {reason.value}")
    
    async def _schedule_follow_up_recovery(
        self, 
        session: CheckoutSession, 
        reason: AbandonmentReason
    ):
        """Schedule follow-up recovery messages."""
        
        # Immediate follow-up (5 minutes)
        asyncio.create_task(
            self._delayed_recovery_message(
                session, 300, "immediate_followup"
            )
        )
        
        # Short-term follow-up (2 hours)
        asyncio.create_task(
            self._delayed_recovery_message(
                session, 7200, "short_term_followup"
            )
        )
        
        # Long-term follow-up (24 hours)
        asyncio.create_task(
            self._delayed_recovery_message(
                session, 86400, "long_term_followup"
            )
        )
    
    async def _delayed_recovery_message(
        self, 
        session: CheckoutSession, 
        delay_seconds: int, 
        recovery_type: str
    ):
        """Send delayed recovery message."""
        
        await asyncio.sleep(delay_seconds)
        
        # Check if customer hasn't completed purchase elsewhere
        if session.current_stage == CheckoutStage.ABANDONED:
            message = await self._generate_recovery_message(session, recovery_type)
            await self._send_intervention_message(session, {"message": message})
    
    async def _generate_recovery_message(
        self, 
        session: CheckoutSession, 
        recovery_type: str
    ) -> str:
        """Generate personalized recovery message."""
        
        cart_items = [item.get("name", "item") for item in session.cart_items]
        cart_value = sum(item.get("price", 0) for item in session.cart_items)
        
        if recovery_type == "immediate_followup":
            return (f"Hi! I noticed you were interested in {', '.join(cart_items[:2])}. "
                   f"Your cart is still saved. Would you like to complete your purchase?")
        
        elif recovery_type == "short_term_followup":
            return (f"🛍️ Your cart (${cart_value:.2f}) is waiting! "
                   f"Complete your purchase now and get free shipping. "
                   f"Items are selling fast!")
        
        elif recovery_type == "long_term_followup":
            return (f"💎 Special offer just for you! "
                   f"Come back and get 15% off your saved cart. "
                   f"This exclusive offer expires in 48 hours.")
        
        return "Your cart is still waiting for you!"
    
    async def enable_one_click_purchase(self, customer_id: str) -> Dict[str, Any]:
        """Enable one-click purchasing for returning customers."""
        
        # Mock customer payment profile
        payment_profile = {
            "customer_id": customer_id,
            "has_saved_payment": True,
            "has_saved_address": True,
            "preferred_payment_method": "credit_card_ending_1234",
            "default_shipping_address": {
                "street": "123 Main St",
                "city": "Anytown",
                "state": "CA",
                "zip": "12345"
            },
            "one_click_enabled": True
        }
        
        return payment_profile
    
    async def process_one_click_purchase(
        self, 
        customer_id: str, 
        cart_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Process one-click purchase."""
        
        # Simulate instant checkout
        order_id = f"order_{int(datetime.now().timestamp())}"
        
        result = {
            "order_id": order_id,
            "customer_id": customer_id,
            "items": cart_items,
            "total": sum(item.get("price", 0) for item in cart_items),
            "status": "completed",
            "processing_time": 0.5,  # 500ms
            "payment_method": "saved_card_1234",
            "shipping_address": "default",
            "estimated_delivery": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        }
        
        logger.info(f"One-click purchase completed: {order_id}")
        
        return result
    
    async def _monitor_sessions(self):
        """Monitor active sessions for abandonment signs."""
        
        while True:
            try:
                current_time = datetime.now(timezone.utc)
                
                for session_id, session in list(self.active_sessions.items()):
                    # Check for session timeout
                    time_since_activity = (current_time - session.last_activity).total_seconds()
                    
                    if time_since_activity > 1800:  # 30 minutes
                        await self.handle_abandonment(session_id, AbandonmentReason.NO_URGENCY)
                        del self.active_sessions[session_id]
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error monitoring sessions: {e}")
                await asyncio.sleep(60)
    
    async def _process_recovery_queue(self):
        """Process recovery actions queue."""
        
        while True:
            try:
                # Process any queued recovery actions
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error processing recovery queue: {e}")
                await asyncio.sleep(30)
    
    def get_optimization_analytics(self) -> Dict[str, Any]:
        """Get checkout optimization analytics."""
        
        total_sessions = len(self.active_sessions)
        completed_sessions = sum(
            1 for s in self.active_sessions.values() 
            if s.current_stage == CheckoutStage.COMPLETED
        )
        abandoned_sessions = sum(
            1 for s in self.active_sessions.values() 
            if s.current_stage == CheckoutStage.ABANDONED
        )
        
        return {
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "abandoned_sessions": abandoned_sessions,
            "conversion_rate": completed_sessions / max(1, total_sessions),
            "abandonment_rate": abandoned_sessions / max(1, total_sessions),
            "average_recovery_attempts": np.mean([
                s.recovery_attempts for s in self.active_sessions.values()
            ]) if self.active_sessions else 0,
            "total_interventions": sum(
                len(s.applied_incentives) for s in self.active_sessions.values()
            )
        }
    
    # Payment Processing Implementation Methods
    
    async def _process_ap2_payment(self, payment_details: PaymentDetails):
        """Process payment using AP2 protocol."""
        
        try:
            # Create AP2 payment request
            ap2_config = self.payment_processors["ap2"]
            
            payment_request = {
                "merchant_id": ap2_config["merchant_id"],
                "amount": str(payment_details.converted_amount),
                "currency": payment_details.customer_currency.value,
                "payment_id": payment_details.payment_id,
                "description": f"Purchase via AI Shopping Agent"
            }
            
            # Calculate processing fee
            is_international = payment_details.original_currency != payment_details.customer_currency
            fee_rate = ap2_config["fees"]["international" if is_international else "domestic"]
            payment_details.processing_fee = payment_details.converted_amount * fee_rate
            
            # Mock AP2 API call (in production, use actual AP2 SDK)
            # Mock successful authorization
            payment_details.authorization_id = f"ap2_auth_{payment_details.payment_id}"
            payment_details.status = PaymentStatus.AUTHORIZED
            payment_details.authorized_at = datetime.now(timezone.utc)
            
            # Auto-capture for AP2
            await self._capture_payment(payment_details)
                        
        except Exception as e:
            payment_details.status = PaymentStatus.FAILED
            payment_details.error_message = str(e)
            raise
    
    async def _process_stripe_payment(self, payment_details: PaymentDetails):
        """Process payment using Stripe."""
        
        try:
            stripe_config = self.payment_processors["stripe"]
            
            # Calculate fees
            is_international = payment_details.original_currency != payment_details.customer_currency
            fee_rate = stripe_config["fees"]["international" if is_international else "domestic"]
            payment_details.processing_fee = payment_details.converted_amount * fee_rate
            
            # Mock successful authorization (in production, use Stripe SDK)
            payment_details.authorization_id = f"stripe_auth_{payment_details.payment_id}"
            payment_details.status = PaymentStatus.AUTHORIZED
            payment_details.authorized_at = datetime.now(timezone.utc)
            
            # Auto-capture
            await self._capture_payment(payment_details)
            
        except Exception as e:
            payment_details.status = PaymentStatus.FAILED
            payment_details.error_message = str(e)
            raise
    
    async def _process_paypal_payment(self, payment_details: PaymentDetails):
        """Process payment using PayPal."""
        
        try:
            paypal_config = self.payment_processors["paypal"]
            
            # Calculate fees
            is_international = payment_details.original_currency != payment_details.customer_currency
            fee_rate = paypal_config["fees"]["international" if is_international else "domestic"]
            payment_details.processing_fee = payment_details.converted_amount * fee_rate
            
            # Mock successful authorization (in production, use PayPal SDK)
            payment_details.authorization_id = f"paypal_auth_{payment_details.payment_id}"
            payment_details.status = PaymentStatus.AUTHORIZED
            payment_details.authorized_at = datetime.now(timezone.utc)
            
            # Auto-capture
            await self._capture_payment(payment_details)
            
        except Exception as e:
            payment_details.status = PaymentStatus.FAILED
            payment_details.error_message = str(e)
            raise
    
    async def _capture_payment(self, payment_details: PaymentDetails):
        """Capture authorized payment."""
        
        try:
            # Mock capture process
            payment_details.capture_id = f"capture_{payment_details.payment_id}"
            payment_details.status = PaymentStatus.CAPTURED
            payment_details.captured_at = datetime.now(timezone.utc)
            
            # Queue for settlement
            await self._queue_for_settlement(payment_details)
            
            logger.info(f"Payment captured: {payment_details.payment_id}")
            
        except Exception as e:
            payment_details.status = PaymentStatus.FAILED
            payment_details.error_message = str(e)
            raise
    
    async def _queue_for_settlement(self, payment_details: PaymentDetails):
        """Queue payment for settlement processing."""
        
        try:
            settlement_id = f"settle_{payment_details.payment_id}"
            
            settlement_details = SettlementDetails(
                settlement_id=settlement_id,
                payment_id=payment_details.payment_id,
                merchant_account="default",
                settlement_amount=payment_details.converted_amount - payment_details.processing_fee,
                settlement_currency=payment_details.customer_currency,
                settlement_date=datetime.now(timezone.utc) + timedelta(days=1),  # T+1 settlement
                processing_fees=payment_details.processing_fee,
                fx_fees=payment_details.currency_conversion_fee
            )
            
            # Store settlement details in session
            for session in self.active_sessions.values():
                if (session.payment_details and 
                    session.payment_details.payment_id == payment_details.payment_id):
                    session.settlement_details = settlement_details
                    session.current_stage = CheckoutStage.SETTLEMENT_PROCESSING
                    break
            
            # Queue in settlement service
            await self.settlement_service.queue_settlement(settlement_details)
            
            logger.info(f"Queued for settlement: {settlement_id}")
            
        except Exception as e:
            logger.error(f"Failed to queue settlement: {e}")
    
    async def _process_settlements(self):
        """Background task to process settlements."""
        
        while True:
            try:
                await self.settlement_service.process_pending_settlements()
                await asyncio.sleep(3600)  # Process every hour
                
            except Exception as e:
                logger.error(f"Settlement processing error: {e}")
                await asyncio.sleep(60)  # Retry in 1 minute


class CurrencyConversionService:
    """Handles currency conversion and exchange rates."""
    
    def __init__(self):
        self.exchange_rates_cache = {}
        self.cache_expiry = {}
        self.base_currency = CurrencyCode.USD
        
    async def convert_currency(
        self, 
        amount: Decimal, 
        from_currency: CurrencyCode, 
        to_currency: CurrencyCode
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """Convert currency and return (exchange_rate, converted_amount, conversion_fee)."""
        
        if from_currency == to_currency:
            return Decimal('1.0'), amount, Decimal('0.00')
        
        try:
            # Get exchange rate
            exchange_rate = await self._get_exchange_rate(from_currency, to_currency)
            
            # Convert amount
            converted_amount = (amount * exchange_rate).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            
            # Calculate conversion fee (0.5% of converted amount)
            conversion_fee = (converted_amount * Decimal('0.005')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            
            return exchange_rate, converted_amount, conversion_fee
            
        except Exception as e:
            logger.error(f"Currency conversion failed: {e}")
            # Return original amount as fallback
            return Decimal('1.0'), amount, Decimal('0.00')
    
    async def _get_exchange_rate(
        self, 
        from_currency: CurrencyCode, 
        to_currency: CurrencyCode
    ) -> Decimal:
        """Get current exchange rate between currencies."""
        
        cache_key = f"{from_currency.value}_{to_currency.value}"
        current_time = datetime.now(timezone.utc)
        
        # Check cache first
        if (cache_key in self.exchange_rates_cache and 
            cache_key in self.cache_expiry and
            current_time < self.cache_expiry[cache_key]):
            return self.exchange_rates_cache[cache_key]
        
        try:
            # In production, use real exchange rate API
            # For demo, use mock rates
            mock_rates = {
                "USD_EUR": Decimal('0.85'),
                "USD_GBP": Decimal('0.73'),
                "USD_JPY": Decimal('110.0'),
                "USD_CAD": Decimal('1.25'),
                "USD_AUD": Decimal('1.35'),
                "EUR_USD": Decimal('1.18'),
                "GBP_USD": Decimal('1.37'),
                "JPY_USD": Decimal('0.009'),
                "CAD_USD": Decimal('0.80'),
                "AUD_USD": Decimal('0.74')
            }
            
            # Try direct rate
            if cache_key in mock_rates:
                rate = mock_rates[cache_key]
            else:
                # Try reverse rate
                reverse_key = f"{to_currency.value}_{from_currency.value}"
                if reverse_key in mock_rates:
                    rate = Decimal('1.0') / mock_rates[reverse_key]
                else:
                    # Fallback to 1.0
                    rate = Decimal('1.0')
            
            # Cache for 1 hour
            self.exchange_rates_cache[cache_key] = rate
            self.cache_expiry[cache_key] = current_time + timedelta(hours=1)
            
            return rate
            
        except Exception as e:
            logger.error(f"Failed to get exchange rate: {e}")
            return Decimal('1.0')


class SettlementService:
    """Handles payment settlement processing."""
    
    def __init__(self):
        self.pending_settlements = []
        self.processed_settlements = []
        
    async def queue_settlement(self, settlement_details: SettlementDetails):
        """Queue a settlement for processing."""
        
        self.pending_settlements.append(settlement_details)
        logger.info(f"Settlement queued: {settlement_details.settlement_id}")
    
    async def process_pending_settlements(self):
        """Process all pending settlements."""
        
        if not self.pending_settlements:
            return
        
        logger.info(f"Processing {len(self.pending_settlements)} pending settlements")
        
        # Process settlements that are due
        current_time = datetime.now(timezone.utc)
        
        settlements_to_process = [
            s for s in self.pending_settlements 
            if s.settlement_date <= current_time
        ]
        
        for settlement in settlements_to_process:
            try:
                await self._process_settlement(settlement)
                self.pending_settlements.remove(settlement)
                self.processed_settlements.append(settlement)
                
            except Exception as e:
                logger.error(f"Settlement processing failed for {settlement.settlement_id}: {e}")
    
    async def _process_settlement(self, settlement: SettlementDetails):
        """Process individual settlement."""
        
        try:
            # Mock settlement processing
            settlement.status = "completed"
            settlement.confirmation_number = f"conf_{settlement.settlement_id}"
            
            # In production, this would:
            # 1. Transfer funds to merchant account
            # 2. Generate settlement report
            # 3. Send notifications
            # 4. Update accounting records
            
            logger.info(f"Settlement processed: {settlement.settlement_id}")
            
        except Exception as e:
            settlement.status = "failed"
            logger.error(f"Settlement failed: {settlement.settlement_id} - {e}")
            raise


# Global instance
checkout_optimizer = ConversionOptimizer()


# Usage Example for Enhanced Payment Processing
async def example_enhanced_checkout():
    """Example demonstrating enhanced payment processing with currency conversion."""
    
    # Start checkout session
    cart_items = [
        {"name": "Laptop", "price": 999.99, "currency": "USD"},
        {"name": "Mouse", "price": 29.99, "currency": "USD"}
    ]
    
    session_id = await checkout_optimizer.start_checkout_session(
        customer_id="customer_123",
        cart_items=cart_items
    )
    
    # Auto-detect customer currency (mock IP from UK)
    detected_currency = await checkout_optimizer.detect_customer_currency(
        session_id, 
        customer_ip="81.2.69.142"  # UK IP
    )
    print(f"Detected customer currency: {detected_currency.value}")
    
    # Initiate payment with automatic currency conversion
    try:
        payment_details = await checkout_optimizer.initiate_payment(
            session_id=session_id,
            payment_method="ap2",
            amount=Decimal("1029.98"),  # Total cart value
            original_currency=CurrencyCode.USD
        )
        
        print(f"Payment processed:")
        print(f"  Payment ID: {payment_details.payment_id}")
        print(f"  Original Amount: {payment_details.amount} {payment_details.original_currency.value}")
        print(f"  Converted Amount: {payment_details.converted_amount} {payment_details.customer_currency.value}")
        print(f"  Exchange Rate: {payment_details.exchange_rate}")
        print(f"  Processing Fee: {payment_details.processing_fee}")
        print(f"  Conversion Fee: {payment_details.currency_conversion_fee}")
        print(f"  Status: {payment_details.status.value}")
        
        # Check settlement details
        session = checkout_optimizer.active_sessions[session_id]
        if session.settlement_details:
            settlement = session.settlement_details
            print(f"\nSettlement Details:")
            print(f"  Settlement ID: {settlement.settlement_id}")
            print(f"  Settlement Amount: {settlement.settlement_amount} {settlement.settlement_currency.value}")
            print(f"  Settlement Date: {settlement.settlement_date}")
            print(f"  Status: {settlement.status}")
    
    except Exception as e:
        print(f"Payment failed: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_enhanced_checkout())