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

"""Comprehensive Analytics and Performance Tracking System.

This module provides detailed analytics for the AI shopping agent including
conversion rates, AOV tracking, customer behavior analysis, and business metrics.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of events to track."""
    
    # Customer journey events
    CUSTOMER_FIRST_CONTACT = "customer_first_contact"
    PRODUCT_SEARCH = "product_search"
    PRODUCT_VIEW = "product_view"
    PRODUCT_RECOMMENDATION = "product_recommendation"
    BUNDLE_CREATED = "bundle_created"
    NEGOTIATION_STARTED = "negotiation_started"
    DISCOUNT_OFFERED = "discount_offered"
    CART_CREATED = "cart_created"
    CART_UPDATED = "cart_updated"
    CHECKOUT_STARTED = "checkout_started"
    CHECKOUT_COMPLETED = "checkout_completed"
    CART_ABANDONED = "cart_abandoned"
    CUSTOMER_SUPPORT_REQUEST = "customer_support_request"
    
    # Channel events
    WHATSAPP_MESSAGE = "whatsapp_message"
    WEB_CHAT_MESSAGE = "web_chat_message"
    CHANNEL_SWITCH = "channel_switch"
    
    # Business events
    SALE_COMPLETED = "sale_completed"
    REVENUE_GENERATED = "revenue_generated"
    REFUND_PROCESSED = "refund_processed"


@dataclass
class AnalyticsEvent:
    """Individual analytics event."""
    
    event_id: str
    event_type: EventType
    timestamp: datetime
    customer_id: str
    session_id: Optional[str]
    channel: Optional[str]
    
    # Event data
    properties: Dict[str, Any]
    
    # Derived metrics
    revenue: float = 0.0
    quantity: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            **asdict(self),
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat()
        }


class CustomerMetrics(BaseModel):
    """Customer-level metrics."""
    
    customer_id: str
    first_contact: datetime
    last_activity: datetime
    
    # Engagement metrics
    total_sessions: int = 0
    total_messages: int = 0
    avg_session_duration: float = 0.0
    preferred_channel: Optional[str] = None
    
    # Purchase behavior
    total_orders: int = 0
    total_revenue: float = 0.0
    avg_order_value: float = 0.0
    conversion_rate: float = 0.0
    
    # Negotiation metrics
    negotiation_success_rate: float = 0.0
    avg_discount_accepted: float = 0.0
    
    # Customer journey
    time_to_first_purchase: Optional[float] = None  # seconds
    cart_abandonment_rate: float = 0.0


class BusinessMetrics(BaseModel):
    """Business-level metrics."""
    
    period_start: datetime
    period_end: datetime
    
    # Revenue metrics
    total_revenue: float = 0.0
    total_orders: int = 0
    avg_order_value: float = 0.0
    revenue_growth_rate: float = 0.0
    
    # Conversion metrics
    total_visitors: int = 0
    total_conversions: int = 0
    conversion_rate: float = 0.0
    cart_abandonment_rate: float = 0.0
    
    # Channel performance
    channel_metrics: Dict[str, Dict[str, float]] = {}
    
    # AI performance
    recommendation_acceptance_rate: float = 0.0
    negotiation_success_rate: float = 0.0
    avg_discount_given: float = 0.0
    
    # Efficiency metrics
    avg_time_to_purchase: float = 0.0
    customer_support_requests_per_order: float = 0.0


class AnalyticsEngine:
    """Main analytics engine."""
    
    def __init__(self):
        self.events: List[AnalyticsEvent] = []
        self.customer_metrics: Dict[str, CustomerMetrics] = {}
        self.daily_metrics: Dict[str, BusinessMetrics] = {}
        
        # Real-time tracking
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.event_queue = asyncio.Queue()
        
        # Start background processing
        asyncio.create_task(self._process_events())
        asyncio.create_task(self._generate_periodic_reports())
    
    async def track_event(
        self, 
        event_type: EventType,
        customer_id: str,
        properties: Dict[str, Any],
        session_id: Optional[str] = None,
        channel: Optional[str] = None,
        revenue: float = 0.0,
        quantity: int = 0
    ):
        """Track an analytics event."""
        
        event = AnalyticsEvent(
            event_id=f"event_{int(datetime.now().timestamp())}_{len(self.events)}",
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            customer_id=customer_id,
            session_id=session_id,
            channel=channel,
            properties=properties,
            revenue=revenue,
            quantity=quantity
        )
        
        await self.event_queue.put(event)
    
    async def _process_events(self):
        """Process events from queue."""
        
        while True:
            try:
                event = await self.event_queue.get()
                await self._handle_event(event)
                self.event_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error processing event: {e}")
                await asyncio.sleep(1)
    
    async def _handle_event(self, event: AnalyticsEvent):
        """Handle individual event and update metrics."""
        
        # Store event
        self.events.append(event)
        
        # Update customer metrics
        await self._update_customer_metrics(event)
        
        # Update business metrics
        await self._update_business_metrics(event)
        
        # Update session tracking
        await self._update_session_tracking(event)
        
        logger.debug(f"Processed event: {event.event_type.value} for customer {event.customer_id}")
    
    async def _update_customer_metrics(self, event: AnalyticsEvent):
        """Update customer-level metrics."""
        
        customer_id = event.customer_id
        
        if customer_id not in self.customer_metrics:
            self.customer_metrics[customer_id] = CustomerMetrics(
                customer_id=customer_id,
                first_contact=event.timestamp,
                last_activity=event.timestamp
            )
        
        metrics = self.customer_metrics[customer_id]
        metrics.last_activity = event.timestamp
        
        # Update based on event type
        if event.event_type == EventType.CUSTOMER_FIRST_CONTACT:
            metrics.total_sessions += 1
        
        elif event.event_type in [EventType.WHATSAPP_MESSAGE, EventType.WEB_CHAT_MESSAGE]:
            metrics.total_messages += 1
            if event.channel:
                metrics.preferred_channel = self._determine_preferred_channel(customer_id)
        
        elif event.event_type == EventType.SALE_COMPLETED:
            metrics.total_orders += 1
            metrics.total_revenue += event.revenue
            metrics.avg_order_value = metrics.total_revenue / metrics.total_orders
            
            if metrics.total_orders == 1:
                metrics.time_to_first_purchase = (
                    event.timestamp - metrics.first_contact
                ).total_seconds()
        
        elif event.event_type == EventType.CART_ABANDONED:
            # Calculate abandonment rate
            total_carts = len([
                e for e in self.events 
                if e.customer_id == customer_id and e.event_type == EventType.CART_CREATED
            ])
            abandoned_carts = len([
                e for e in self.events 
                if e.customer_id == customer_id and e.event_type == EventType.CART_ABANDONED
            ])
            metrics.cart_abandonment_rate = abandoned_carts / max(1, total_carts)
        
        elif event.event_type == EventType.NEGOTIATION_STARTED:
            # Update negotiation metrics
            await self._update_negotiation_metrics(customer_id)
    
    def _determine_preferred_channel(self, customer_id: str) -> str:
        """Determine customer's preferred channel."""
        
        channel_counts = defaultdict(int)
        
        for event in self.events:
            if event.customer_id == customer_id and event.channel:
                channel_counts[event.channel] += 1
        
        if channel_counts:
            return max(channel_counts.keys(), key=channel_counts.get)
        
        return "unknown"
    
    async def _update_negotiation_metrics(self, customer_id: str):
        """Update negotiation success metrics for customer."""
        
        customer_events = [e for e in self.events if e.customer_id == customer_id]
        
        negotiation_starts = [
            e for e in customer_events if e.event_type == EventType.NEGOTIATION_STARTED
        ]
        
        successful_negotiations = [
            e for e in customer_events 
            if e.event_type == EventType.SALE_COMPLETED 
            and e.properties.get("negotiated", False)
        ]
        
        if negotiation_starts:
            metrics = self.customer_metrics[customer_id]
            metrics.negotiation_success_rate = len(successful_negotiations) / len(negotiation_starts)
            
            # Calculate average discount accepted
            discounts = [
                e.properties.get("discount_percentage", 0) 
                for e in successful_negotiations 
                if e.properties.get("discount_percentage")
            ]
            
            if discounts:
                metrics.avg_discount_accepted = np.mean(discounts)
    
    async def _update_business_metrics(self, event: AnalyticsEvent):
        """Update business-level metrics."""
        
        date_key = event.timestamp.date().isoformat()
        
        if date_key not in self.daily_metrics:
            self.daily_metrics[date_key] = BusinessMetrics(
                period_start=datetime.combine(event.timestamp.date(), datetime.min.time()),
                period_end=datetime.combine(event.timestamp.date(), datetime.max.time())
            )
        
        metrics = self.daily_metrics[date_key]
        
        if event.event_type == EventType.CUSTOMER_FIRST_CONTACT:
            metrics.total_visitors += 1
        
        elif event.event_type == EventType.SALE_COMPLETED:
            metrics.total_orders += 1
            metrics.total_revenue += event.revenue
            metrics.total_conversions += 1
            
            if metrics.total_orders > 0:
                metrics.avg_order_value = metrics.total_revenue / metrics.total_orders
            
            if metrics.total_visitors > 0:
                metrics.conversion_rate = metrics.total_conversions / metrics.total_visitors
        
        elif event.event_type == EventType.CART_ABANDONED:
            # Update abandonment rate
            today_events = [
                e for e in self.events 
                if e.timestamp.date() == event.timestamp.date()
            ]
            
            total_carts = len([
                e for e in today_events if e.event_type == EventType.CART_CREATED
            ])
            abandoned_carts = len([
                e for e in today_events if e.event_type == EventType.CART_ABANDONED
            ])
            
            metrics.cart_abandonment_rate = abandoned_carts / max(1, total_carts)
        
        # Update channel metrics
        if event.channel:
            if event.channel not in metrics.channel_metrics:
                metrics.channel_metrics[event.channel] = {
                    "messages": 0,
                    "conversions": 0,
                    "revenue": 0.0
                }
            
            if event.event_type in [EventType.WHATSAPP_MESSAGE, EventType.WEB_CHAT_MESSAGE]:
                metrics.channel_metrics[event.channel]["messages"] += 1
            
            elif event.event_type == EventType.SALE_COMPLETED:
                metrics.channel_metrics[event.channel]["conversions"] += 1
                metrics.channel_metrics[event.channel]["revenue"] += event.revenue
    
    async def _update_session_tracking(self, event: AnalyticsEvent):
        """Update session tracking."""
        
        if not event.session_id:
            return
        
        if event.session_id not in self.active_sessions:
            self.active_sessions[event.session_id] = {
                "customer_id": event.customer_id,
                "start_time": event.timestamp,
                "last_activity": event.timestamp,
                "events": [],
                "channel": event.channel
            }
        
        session = self.active_sessions[event.session_id]
        session["last_activity"] = event.timestamp
        session["events"].append(event.event_type.value)
        
        # Calculate session duration and update customer metrics
        if event.customer_id in self.customer_metrics:
            duration = (event.timestamp - session["start_time"]).total_seconds()
            customer_metrics = self.customer_metrics[event.customer_id]
            
            # Update average session duration
            total_duration = customer_metrics.avg_session_duration * (customer_metrics.total_sessions - 1) + duration
            customer_metrics.avg_session_duration = total_duration / customer_metrics.total_sessions
    
    def get_customer_analytics(self, customer_id: str) -> Optional[CustomerMetrics]:
        """Get analytics for specific customer."""
        return self.customer_metrics.get(customer_id)
    
    def get_business_analytics(
        self, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get business analytics for date range."""
        
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()
        
        # Filter events in date range
        filtered_events = [
            e for e in self.events 
            if start_date <= e.timestamp <= end_date
        ]
        
        # Calculate aggregated metrics
        total_revenue = sum(e.revenue for e in filtered_events)
        total_orders = len([e for e in filtered_events if e.event_type == EventType.SALE_COMPLETED])
        total_visitors = len(set(e.customer_id for e in filtered_events))
        
        # Customer insights
        customer_segments = self._analyze_customer_segments(filtered_events)
        
        # Channel performance
        channel_performance = self._analyze_channel_performance(filtered_events)
        
        # Product performance
        product_insights = self._analyze_product_performance(filtered_events)
        
        # AI performance
        ai_performance = self._analyze_ai_performance(filtered_events)
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "summary": {
                "total_revenue": total_revenue,
                "total_orders": total_orders,
                "total_visitors": total_visitors,
                "avg_order_value": total_revenue / max(1, total_orders),
                "conversion_rate": total_orders / max(1, total_visitors)
            },
            "customer_segments": customer_segments,
            "channel_performance": channel_performance,
            "product_insights": product_insights,
            "ai_performance": ai_performance,
            "trends": self._calculate_trends(filtered_events)
        }
    
    def _analyze_customer_segments(self, events: List[AnalyticsEvent]) -> Dict[str, Any]:
        """Analyze customer segments."""
        
        customers = list(set(e.customer_id for e in events))
        
        segments = {
            "new_customers": 0,
            "returning_customers": 0,
            "high_value_customers": 0,
            "at_risk_customers": 0
        }
        
        for customer_id in customers:
            if customer_id in self.customer_metrics:
                metrics = self.customer_metrics[customer_id]
                
                if metrics.total_orders == 0:
                    segments["new_customers"] += 1
                elif metrics.total_orders > 1:
                    segments["returning_customers"] += 1
                
                if metrics.total_revenue > 500:
                    segments["high_value_customers"] += 1
                
                days_since_last_activity = (
                    datetime.now(timezone.utc) - metrics.last_activity
                ).days
                
                if days_since_last_activity > 30 and metrics.total_orders > 0:
                    segments["at_risk_customers"] += 1
        
        return segments
    
    def _analyze_channel_performance(self, events: List[AnalyticsEvent]) -> Dict[str, Any]:
        """Analyze channel performance."""
        
        channel_data = defaultdict(lambda: {
            "messages": 0,
            "customers": set(),
            "conversions": 0,
            "revenue": 0.0
        })
        
        for event in events:
            if event.channel:
                data = channel_data[event.channel]
                
                if event.event_type in [EventType.WHATSAPP_MESSAGE, EventType.WEB_CHAT_MESSAGE]:
                    data["messages"] += 1
                    data["customers"].add(event.customer_id)
                
                elif event.event_type == EventType.SALE_COMPLETED:
                    data["conversions"] += 1
                    data["revenue"] += event.revenue
        
        # Convert to final format
        result = {}
        for channel, data in channel_data.items():
            result[channel] = {
                "total_messages": data["messages"],
                "unique_customers": len(data["customers"]),
                "conversions": data["conversions"],
                "revenue": data["revenue"],
                "conversion_rate": data["conversions"] / max(1, len(data["customers"])),
                "revenue_per_customer": data["revenue"] / max(1, len(data["customers"]))
            }
        
        return result
    
    def _analyze_product_performance(self, events: List[AnalyticsEvent]) -> Dict[str, Any]:
        """Analyze product performance."""
        
        # Mock product analysis - in production, extract from event properties
        return {
            "top_selling_products": [
                {"name": "Premium Wireless Headphones", "sales": 45, "revenue": 8955},
                {"name": "Smart Fitness Watch", "sales": 32, "revenue": 9600},
                {"name": "Bluetooth Speaker Bundle", "sales": 28, "revenue": 2519}
            ],
            "top_searched_products": [
                {"name": "laptop", "searches": 156},
                {"name": "headphones", "searches": 134},
                {"name": "phone", "searches": 98}
            ],
            "bundle_performance": {
                "bundles_created": 67,
                "bundles_purchased": 23,
                "bundle_conversion_rate": 0.34,
                "average_bundle_value": 287.50
            }
        }
    
    def _analyze_ai_performance(self, events: List[AnalyticsEvent]) -> Dict[str, Any]:
        """Analyze AI system performance."""
        
        recommendation_events = [
            e for e in events if e.event_type == EventType.PRODUCT_RECOMMENDATION
        ]
        
        negotiation_events = [
            e for e in events if e.event_type == EventType.NEGOTIATION_STARTED
        ]
        
        discount_events = [
            e for e in events if e.event_type == EventType.DISCOUNT_OFFERED
        ]
        
        return {
            "recommendations": {
                "total_recommendations": len(recommendation_events),
                "acceptance_rate": 0.67,  # Mock - calculate from actual data
                "avg_recommendation_value": 189.50
            },
            "negotiations": {
                "total_negotiations": len(negotiation_events),
                "success_rate": 0.58,
                "avg_discount_given": 12.5,
                "negotiation_conversion_rate": 0.45
            },
            "discounts": {
                "total_discounts_offered": len(discount_events),
                "discount_acceptance_rate": 0.73,
                "avg_discount_percentage": 11.2,
                "revenue_impact": -1247.30  # Negative = cost, positive = gain
            }
        }
    
    def _calculate_trends(self, events: List[AnalyticsEvent]) -> Dict[str, Any]:
        """Calculate trends over time."""
        
        # Group events by day
        daily_data = defaultdict(lambda: {
            "revenue": 0.0,
            "orders": 0,
            "visitors": set()
        })
        
        for event in events:
            day = event.timestamp.date().isoformat()
            
            if event.event_type == EventType.SALE_COMPLETED:
                daily_data[day]["revenue"] += event.revenue
                daily_data[day]["orders"] += 1
            
            daily_data[day]["visitors"].add(event.customer_id)
        
        # Calculate trends
        days = sorted(daily_data.keys())
        if len(days) < 2:
            return {"trend": "insufficient_data"}
        
        # Revenue trend
        recent_revenue = sum(daily_data[day]["revenue"] for day in days[-7:])
        previous_revenue = sum(daily_data[day]["revenue"] for day in days[-14:-7]) if len(days) >= 14 else recent_revenue
        
        revenue_growth = ((recent_revenue - previous_revenue) / max(1, previous_revenue)) * 100 if previous_revenue > 0 else 0
        
        # Order trend
        recent_orders = sum(daily_data[day]["orders"] for day in days[-7:])
        previous_orders = sum(daily_data[day]["orders"] for day in days[-14:-7]) if len(days) >= 14 else recent_orders
        
        order_growth = ((recent_orders - previous_orders) / max(1, previous_orders)) * 100 if previous_orders > 0 else 0
        
        return {
            "revenue_growth_7d": revenue_growth,
            "order_growth_7d": order_growth,
            "trend_direction": "up" if revenue_growth > 5 else "down" if revenue_growth < -5 else "stable"
        }
    
    async def _generate_periodic_reports(self):
        """Generate periodic analytics reports."""
        
        while True:
            try:
                # Generate daily report at midnight
                now = datetime.now()
                if now.hour == 0 and now.minute == 0:
                    await self._generate_daily_report()
                
                # Generate weekly report on Sundays
                if now.weekday() == 6 and now.hour == 0:
                    await self._generate_weekly_report()
                
                await asyncio.sleep(3600)  # Check every hour
                
            except Exception as e:
                logger.error(f"Error generating periodic reports: {e}")
                await asyncio.sleep(3600)
    
    async def _generate_daily_report(self):
        """Generate daily analytics report."""
        
        yesterday = datetime.now() - timedelta(days=1)
        analytics = self.get_business_analytics(
            start_date=yesterday.replace(hour=0, minute=0, second=0),
            end_date=yesterday.replace(hour=23, minute=59, second=59)
        )
        
        logger.info(f"Daily report generated: {analytics['summary']}")
        
        # In production, send to stakeholders via email/dashboard
    
    async def _generate_weekly_report(self):
        """Generate weekly analytics report."""
        
        week_start = datetime.now() - timedelta(days=7)
        analytics = self.get_business_analytics(start_date=week_start)
        
        logger.info(f"Weekly report generated: {analytics['summary']}")
        
        # In production, send comprehensive report to stakeholders
    
    def export_data(self, format: str = "json") -> str:
        """Export analytics data."""
        
        if format == "json":
            export_data = {
                "events": [event.to_dict() for event in self.events],
                "customer_metrics": {
                    cid: metrics.dict() for cid, metrics in self.customer_metrics.items()
                },
                "business_metrics": {
                    date: metrics.dict() for date, metrics in self.daily_metrics.items()
                }
            }
            return json.dumps(export_data, indent=2, default=str)
        
        elif format == "csv":
            # Convert events to DataFrame and export as CSV
            events_data = [event.to_dict() for event in self.events]
            df = pd.DataFrame(events_data)
            return df.to_csv(index=False)
        
        else:
            raise ValueError(f"Unsupported export format: {format}")


# Global analytics instance
analytics_engine = AnalyticsEngine()


# Helper functions for easy tracking
async def track_customer_interaction(customer_id: str, message: str, channel: str):
    """Track customer interaction."""
    await analytics_engine.track_event(
        EventType.WHATSAPP_MESSAGE if channel == "whatsapp" else EventType.WEB_CHAT_MESSAGE,
        customer_id=customer_id,
        properties={"message": message},
        channel=channel
    )


async def track_product_search(customer_id: str, query: str, results_count: int):
    """Track product search."""
    await analytics_engine.track_event(
        EventType.PRODUCT_SEARCH,
        customer_id=customer_id,
        properties={"query": query, "results_count": results_count}
    )


async def track_sale_completion(customer_id: str, order_value: float, items: List[Dict[str, Any]], channel: str):
    """Track completed sale."""
    await analytics_engine.track_event(
        EventType.SALE_COMPLETED,
        customer_id=customer_id,
        properties={"items": items, "order_id": f"order_{int(datetime.now().timestamp())}"},
        channel=channel,
        revenue=order_value,
        quantity=len(items)
    )


async def track_cart_abandonment(customer_id: str, cart_value: float, stage: str):
    """Track cart abandonment."""
    await analytics_engine.track_event(
        EventType.CART_ABANDONED,
        customer_id=customer_id,
        properties={"cart_value": cart_value, "abandonment_stage": stage}
    )