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

"""Enhanced AI Product Curation Engine.

This module provides advanced product recommendation, personalization,
and intelligent curation capabilities for the shopping agent.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import numpy as np
from pydantic import BaseModel, Field
from google import genai

from ap2.types.payment_request import PaymentItem
from ap2.types.mandate import CartMandate, IntentMandate

logger = logging.getLogger(__name__)


class CustomerPreference(BaseModel):
    """Customer preference model."""
    
    preference_type: str
    value: Any
    confidence: float = Field(ge=0.0, le=1.0)
    last_updated: datetime
    source: str  # "explicit", "implicit", "inferred"


class ProductCategory(Enum):
    """Product categories for better organization."""
    
    ELECTRONICS = "electronics"
    CLOTHING = "clothing"
    HOME_GARDEN = "home_garden"
    SPORTS_FITNESS = "sports_fitness"
    BOOKS_MEDIA = "books_media"
    HEALTH_BEAUTY = "health_beauty"
    AUTOMOTIVE = "automotive"
    TOYS_GAMES = "toys_games"
    FOOD_BEVERAGE = "food_beverage"
    OTHER = "other"


@dataclass
class ProductMetrics:
    """Product performance metrics."""
    
    popularity_score: float
    conversion_rate: float
    average_rating: float
    review_count: int
    price_competitiveness: float
    availability_score: float
    
    @property
    def overall_score(self) -> float:
        """Calculate overall product score."""
        weights = {
            'popularity': 0.2,
            'conversion': 0.25,
            'rating': 0.2,
            'reviews': 0.1,
            'price': 0.15,
            'availability': 0.1
        }
        
        # Normalize review count (log scale)
        normalized_reviews = min(np.log10(max(1, self.review_count)) / 4, 1.0)
        
        return (
            weights['popularity'] * self.popularity_score +
            weights['conversion'] * self.conversion_rate +
            weights['rating'] * (self.average_rating / 5.0) +
            weights['reviews'] * normalized_reviews +
            weights['price'] * self.price_competitiveness +
            weights['availability'] * self.availability_score
        )


class PersonalizationEngine:
    """Customer personalization and preference learning."""
    
    def __init__(self):
        self.customer_profiles: Dict[str, Dict[str, CustomerPreference]] = {}
        self.interaction_history: Dict[str, List[Dict[str, Any]]] = {}
        
    def update_customer_profile(
        self, 
        customer_id: str, 
        interaction_data: Dict[str, Any]
    ):
        """Update customer profile based on interaction."""
        
        if customer_id not in self.customer_profiles:
            self.customer_profiles[customer_id] = {}
            
        if customer_id not in self.interaction_history:
            self.interaction_history[customer_id] = []
            
        # Add interaction to history
        self.interaction_history[customer_id].append({
            **interaction_data,
            "timestamp": datetime.now(timezone.utc)
        })
        
        # Extract preferences from interaction
        preferences = self._extract_preferences(interaction_data)
        
        for pref_type, pref_data in preferences.items():
            self._update_preference(customer_id, pref_type, pref_data)
    
    def _extract_preferences(self, interaction: Dict[str, Any]) -> Dict[str, Any]:
        """Extract preferences from customer interaction."""
        
        preferences = {}
        
        # Price sensitivity
        if "budget" in interaction:
            preferences["price_range"] = {
                "value": interaction["budget"],
                "confidence": 0.8,
                "source": "explicit"
            }
        
        # Brand preferences
        if "selected_product" in interaction:
            product = interaction["selected_product"]
            if "brand" in product:
                preferences["preferred_brands"] = {
                    "value": product["brand"],
                    "confidence": 0.6,
                    "source": "implicit"
                }
        
        # Category interests
        if "viewed_categories" in interaction:
            for category in interaction["viewed_categories"]:
                preferences[f"category_interest_{category}"] = {
                    "value": 1.0,
                    "confidence": 0.5,
                    "source": "implicit"
                }
        
        return preferences
    
    def _update_preference(
        self, 
        customer_id: str, 
        pref_type: str, 
        pref_data: Dict[str, Any]
    ):
        """Update specific customer preference."""
        
        current_pref = self.customer_profiles[customer_id].get(pref_type)
        
        if current_pref:
            # Merge with existing preference
            if pref_data["source"] == "explicit":
                # Explicit preferences override implicit ones
                confidence = max(pref_data["confidence"], current_pref.confidence)
            else:
                # Gradually increase confidence for repeated implicit signals
                confidence = min(current_pref.confidence + 0.1, 0.9)
            
            self.customer_profiles[customer_id][pref_type] = CustomerPreference(
                preference_type=pref_type,
                value=pref_data["value"],
                confidence=confidence,
                last_updated=datetime.now(timezone.utc),
                source=pref_data["source"]
            )
        else:
            # New preference
            self.customer_profiles[customer_id][pref_type] = CustomerPreference(
                preference_type=pref_type,
                value=pref_data["value"],
                confidence=pref_data["confidence"],
                last_updated=datetime.now(timezone.utc),
                source=pref_data["source"]
            )
    
    def get_customer_preferences(self, customer_id: str) -> Dict[str, CustomerPreference]:
        """Get customer preferences."""
        return self.customer_profiles.get(customer_id, {})
    
    def predict_interest(self, customer_id: str, product: Dict[str, Any]) -> float:
        """Predict customer interest in a product."""
        
        preferences = self.get_customer_preferences(customer_id)
        if not preferences:
            return 0.5  # Neutral for new customers
        
        interest_score = 0.5
        total_weight = 0.0
        
        # Brand preference
        if "preferred_brands" in preferences and "brand" in product:
            pref = preferences["preferred_brands"]
            if product["brand"] == pref.value:
                interest_score += 0.3 * pref.confidence
            total_weight += 0.3 * pref.confidence
        
        # Price range preference
        if "price_range" in preferences and "price" in product:
            pref = preferences["price_range"]
            price_range = pref.value
            product_price = product["price"]
            
            if isinstance(price_range, dict):
                min_price = price_range.get("min", 0)
                max_price = price_range.get("max", float('inf'))
                
                if min_price <= product_price <= max_price:
                    interest_score += 0.4 * pref.confidence
                else:
                    # Penalize for being outside price range
                    interest_score -= 0.2 * pref.confidence
                
                total_weight += 0.4 * pref.confidence
        
        # Category interest
        product_category = product.get("category", "")
        category_pref_key = f"category_interest_{product_category}"
        
        if category_pref_key in preferences:
            pref = preferences[category_pref_key]
            interest_score += 0.3 * pref.confidence
            total_weight += 0.3 * pref.confidence
        
        # Normalize score
        if total_weight > 0:
            interest_score = interest_score / total_weight
        
        return max(0.0, min(1.0, interest_score))


class SmartCurationEngine:
    """Advanced product curation with AI-powered recommendations."""
    
    def __init__(self):
        self.personalization_engine = PersonalizationEngine()
        self.llm_client = genai.Client()
        self.product_metrics_cache: Dict[str, ProductMetrics] = {}
        
    async def curate_products(
        self, 
        intent_mandate: IntentMandate,
        customer_id: str,
        max_results: int = 10,
        include_bundles: bool = True
    ) -> List[Dict[str, Any]]:
        """Curate personalized product recommendations."""
        
        # Get base product recommendations
        base_products = await self._get_base_recommendations(intent_mandate)
        
        # Apply personalization
        personalized_products = self._apply_personalization(
            base_products, customer_id
        )
        
        # Generate smart bundles
        if include_bundles:
            bundles = await self._generate_smart_bundles(
                personalized_products, customer_id
            )
            personalized_products.extend(bundles)
        
        # Rank and filter
        ranked_products = self._rank_products(
            personalized_products, customer_id
        )
        
        return ranked_products[:max_results]
    
    async def _get_base_recommendations(
        self, 
        intent_mandate: IntentMandate
    ) -> List[Dict[str, Any]]:
        """Get base product recommendations using LLM."""
        
        prompt = f"""
        Based on the customer's intent: "{intent_mandate.natural_language_description}"
        
        Generate 15 diverse, realistic product recommendations in JSON format.
        Each product should include:
        - name: Product name
        - brand: Brand name
        - price: Price as a number
        - category: Product category
        - description: Brief description
        - features: List of key features
        - rating: Average rating (1-5)
        - review_count: Number of reviews
        - availability: "in_stock" or "limited" or "pre_order"
        - image_url: Mock image URL
        
        Focus on variety in price points, brands, and features.
        Include some premium and budget options.
        """
        
        try:
            response = self.llm_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": {"type": "array", "items": {"type": "object"}}
                }
            )
            
            return response.parsed if response.parsed else []
            
        except Exception as e:
            logger.error(f"Error getting base recommendations: {e}")
            return []
    
    def _apply_personalization(
        self, 
        products: List[Dict[str, Any]], 
        customer_id: str
    ) -> List[Dict[str, Any]]:
        """Apply personalization scoring to products."""
        
        for product in products:
            # Calculate personalization score
            interest_score = self.personalization_engine.predict_interest(
                customer_id, product
            )
            product["personalization_score"] = interest_score
            
            # Calculate product metrics
            metrics = self._calculate_product_metrics(product)
            product["metrics"] = metrics
            product["overall_score"] = metrics.overall_score
        
        return products
    
    def _calculate_product_metrics(self, product: Dict[str, Any]) -> ProductMetrics:
        """Calculate product performance metrics."""
        
        # Mock calculations - in production, these would come from real data
        review_count = product.get("review_count", 100)
        rating = product.get("rating", 4.0)
        price = product.get("price", 100)
        availability = product.get("availability", "in_stock")
        
        # Popularity based on review count and rating
        popularity_score = min(np.log10(max(1, review_count)) / 4, 1.0)
        
        # Mock conversion rate based on rating and price
        conversion_rate = max(0.1, (rating / 5.0) * (1 - min(price / 1000, 0.5)))
        
        # Price competitiveness (mock)
        price_competitiveness = max(0.1, 1 - (price / 2000))
        
        # Availability score
        availability_scores = {
            "in_stock": 1.0,
            "limited": 0.7,
            "pre_order": 0.4
        }
        availability_score = availability_scores.get(availability, 0.5)
        
        return ProductMetrics(
            popularity_score=popularity_score,
            conversion_rate=conversion_rate,
            average_rating=rating,
            review_count=review_count,
            price_competitiveness=price_competitiveness,
            availability_score=availability_score
        )
    
    async def _generate_smart_bundles(
        self, 
        products: List[Dict[str, Any]], 
        customer_id: str
    ) -> List[Dict[str, Any]]:
        """Generate intelligent product bundles."""
        
        if len(products) < 2:
            return []
        
        # Group products by category for complementary bundling
        category_groups = {}
        for product in products:
            category = product.get("category", "other")
            if category not in category_groups:
                category_groups[category] = []
            category_groups[category].append(product)
        
        bundles = []
        
        # Create bundles within categories (upgrade bundles)
        for category, cat_products in category_groups.items():
            if len(cat_products) >= 2:
                bundle = await self._create_category_bundle(cat_products, customer_id)
                if bundle:
                    bundles.append(bundle)
        
        # Create cross-category bundles (complementary bundles)
        if len(category_groups) >= 2:
            cross_bundle = await self._create_cross_category_bundle(
                category_groups, customer_id
            )
            if cross_bundle:
                bundles.append(cross_bundle)
        
        return bundles
    
    async def _create_category_bundle(
        self, 
        products: List[Dict[str, Any]], 
        customer_id: str
    ) -> Optional[Dict[str, Any]]:
        """Create bundle within same category."""
        
        # Sort by overall score and pick top 2-3
        sorted_products = sorted(
            products, 
            key=lambda x: x.get("overall_score", 0), 
            reverse=True
        )[:3]
        
        if len(sorted_products) < 2:
            return None
        
        # Calculate bundle pricing with discount
        total_price = sum(p.get("price", 0) for p in sorted_products)
        bundle_discount = 0.15  # 15% bundle discount
        bundle_price = total_price * (1 - bundle_discount)
        
        return {
            "type": "bundle",
            "name": f"{sorted_products[0].get('category', 'Product')} Bundle",
            "products": sorted_products,
            "original_price": total_price,
            "price": bundle_price,
            "savings": total_price - bundle_price,
            "discount_percentage": bundle_discount * 100,
            "category": "bundle",
            "description": f"Save ${total_price - bundle_price:.2f} with this curated bundle!",
            "bundle_type": "category_upgrade",
            "overall_score": np.mean([p.get("overall_score", 0) for p in sorted_products])
        }
    
    async def _create_cross_category_bundle(
        self, 
        category_groups: Dict[str, List[Dict[str, Any]]], 
        customer_id: str
    ) -> Optional[Dict[str, Any]]:
        """Create complementary cross-category bundle."""
        
        # Find complementary categories
        complementary_pairs = [
            ("electronics", "accessories"),
            ("sports_fitness", "health_beauty"),
            ("clothing", "accessories"),
            ("home_garden", "electronics")
        ]
        
        available_categories = set(category_groups.keys())
        
        for cat1, cat2 in complementary_pairs:
            if cat1 in available_categories and cat2 in available_categories:
                # Pick best product from each category
                product1 = max(
                    category_groups[cat1], 
                    key=lambda x: x.get("overall_score", 0)
                )
                product2 = max(
                    category_groups[cat2], 
                    key=lambda x: x.get("overall_score", 0)
                )
                
                total_price = product1.get("price", 0) + product2.get("price", 0)
                bundle_discount = 0.12  # 12% cross-category discount
                bundle_price = total_price * (1 - bundle_discount)
                
                return {
                    "type": "bundle",
                    "name": "Perfect Pair Bundle",
                    "products": [product1, product2],
                    "original_price": total_price,
                    "price": bundle_price,
                    "savings": total_price - bundle_price,
                    "discount_percentage": bundle_discount * 100,
                    "category": "bundle",
                    "description": f"Complete your experience with this perfect pair!",
                    "bundle_type": "complementary",
                    "overall_score": (product1.get("overall_score", 0) + product2.get("overall_score", 0)) / 2
                }
        
        return None
    
    def _rank_products(
        self, 
        products: List[Dict[str, Any]], 
        customer_id: str
    ) -> List[Dict[str, Any]]:
        """Rank products using combined scoring."""
        
        def calculate_final_score(product):
            overall_score = product.get("overall_score", 0.5)
            personalization_score = product.get("personalization_score", 0.5)
            
            # Weight: 60% product quality, 40% personalization
            final_score = 0.6 * overall_score + 0.4 * personalization_score
            
            # Boost bundles slightly
            if product.get("type") == "bundle":
                final_score *= 1.1
            
            return final_score
        
        # Add final scores
        for product in products:
            product["final_score"] = calculate_final_score(product)
        
        # Sort by final score
        return sorted(products, key=lambda x: x["final_score"], reverse=True)
    
    def get_product_analytics(self, customer_id: str) -> Dict[str, Any]:
        """Get analytics for product curation performance."""
        
        preferences = self.personalization_engine.get_customer_preferences(customer_id)
        interaction_history = self.personalization_engine.interaction_history.get(customer_id, [])
        
        return {
            "total_interactions": len(interaction_history),
            "preferences_learned": len(preferences),
            "high_confidence_preferences": len([
                p for p in preferences.values() if p.confidence > 0.7
            ]),
            "last_interaction": interaction_history[-1]["timestamp"] if interaction_history else None,
            "top_categories": self._get_top_categories(interaction_history),
            "average_session_length": self._calculate_avg_session_length(interaction_history)
        }
    
    def _get_top_categories(self, interactions: List[Dict[str, Any]]) -> List[str]:
        """Get top product categories for customer."""
        category_counts = {}
        
        for interaction in interactions:
            if "viewed_categories" in interaction:
                for category in interaction["viewed_categories"]:
                    category_counts[category] = category_counts.get(category, 0) + 1
        
        return sorted(category_counts.keys(), key=category_counts.get, reverse=True)[:5]
    
    def _calculate_avg_session_length(self, interactions: List[Dict[str, Any]]) -> float:
        """Calculate average session length in minutes."""
        if len(interactions) < 2:
            return 0.0
        
        session_lengths = []
        current_session_start = None
        
        for interaction in interactions:
            timestamp = interaction["timestamp"]
            
            if current_session_start is None:
                current_session_start = timestamp
            else:
                time_diff = (timestamp - current_session_start).total_seconds() / 60
                if time_diff > 30:  # New session if gap > 30 minutes
                    session_lengths.append(time_diff)
                    current_session_start = timestamp
        
        return np.mean(session_lengths) if session_lengths else 0.0


# Global instance
curation_engine = SmartCurationEngine()