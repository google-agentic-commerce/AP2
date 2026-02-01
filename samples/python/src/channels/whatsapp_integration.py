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

"""WhatsApp Business API integration for the AI Shopping Agent.

This module provides a seamless integration between WhatsApp Business API
and the AP2 shopping agent, enabling customers to shop through WhatsApp chat.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from roles.shopping_agent.agent import root_agent
from common.system_utils import get_env_var

logger = logging.getLogger(__name__)


class WhatsAppMessage(BaseModel):
    """WhatsApp message structure."""
    
    from_number: str = Field(..., alias="from")
    to_number: str = Field(..., alias="to")
    message_type: str = Field(..., alias="type")
    text: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    timestamp: datetime
    message_id: str


class WhatsAppContact(BaseModel):
    """WhatsApp contact information."""
    
    phone_number: str
    name: Optional[str] = None
    profile_name: Optional[str] = None


class WhatsAppWebhookEvent(BaseModel):
    """WhatsApp webhook event structure."""
    
    entry: List[Dict[str, Any]]
    object: str


class CustomerSession:
    """Manages individual customer shopping sessions."""
    
    def __init__(self, phone_number: str):
        self.phone_number = phone_number
        self.session_id = f"whatsapp_{phone_number}_{int(datetime.now().timestamp())}"
        self.conversation_history: List[Dict[str, Any]] = []
        self.shopping_context: Dict[str, Any] = {}
        self.last_activity = datetime.now(timezone.utc)
        self.cart_items: List[Dict[str, Any]] = []
        self.customer_preferences: Dict[str, Any] = {}
        
    def add_message(self, message: str, sender: str):
        """Add a message to conversation history."""
        self.conversation_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sender": sender,
            "message": message
        })
        self.last_activity = datetime.now(timezone.utc)


class WhatsAppShoppingAgent:
    """Main WhatsApp shopping agent integration."""
    
    def __init__(self):
        self.whatsapp_token = get_env_var("WHATSAPP_BUSINESS_TOKEN")
        self.whatsapp_phone_id = get_env_var("WHATSAPP_PHONE_NUMBER_ID")
        self.webhook_verify_token = get_env_var("WHATSAPP_WEBHOOK_VERIFY_TOKEN")
        self.base_url = f"https://graph.facebook.com/v18.0/{self.whatsapp_phone_id}"
        
        # Session management
        self.active_sessions: Dict[str, CustomerSession] = {}
        self.session_timeout = 3600  # 1 hour timeout
        
        # Agent integration
        self.shopping_agent = root_agent
        
    async def send_whatsapp_message(
        self, 
        to_number: str, 
        message: str, 
        message_type: str = "text"
    ) -> bool:
        """Send a message via WhatsApp Business API."""
        
        headers = {
            "Authorization": f"Bearer {self.whatsapp_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": message_type,
            "text": {"body": message}
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/messages",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        logger.info(f"Message sent successfully to {to_number}")
                        return True
                    else:
                        logger.error(f"Failed to send message: {await response.text()}")
                        return False
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {e}")
            return False
    
    async def send_interactive_message(
        self, 
        to_number: str, 
        header: str,
        body: str, 
        buttons: List[Dict[str, str]]
    ) -> bool:
        """Send an interactive message with buttons."""
        
        headers = {
            "Authorization": f"Bearer {self.whatsapp_token}",
            "Content-Type": "application/json"
        }
        
        interactive_buttons = []
        for i, button in enumerate(buttons):
            interactive_buttons.append({
                "type": "reply",
                "reply": {
                    "id": f"btn_{i}",
                    "title": button["title"]
                }
            })
        
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "header": {"type": "text", "text": header},
                "body": {"text": body},
                "action": {"buttons": interactive_buttons}
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/messages",
                    headers=headers,
                    json=payload
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Error sending interactive message: {e}")
            return False
    
    def get_or_create_session(self, phone_number: str) -> CustomerSession:
        """Get existing session or create new one."""
        
        # Clean up expired sessions
        self._cleanup_expired_sessions()
        
        if phone_number not in self.active_sessions:
            self.active_sessions[phone_number] = CustomerSession(phone_number)
            logger.info(f"Created new session for {phone_number}")
        
        return self.active_sessions[phone_number]
    
    def _cleanup_expired_sessions(self):
        """Remove expired sessions."""
        current_time = datetime.now(timezone.utc)
        expired_sessions = []
        
        for phone_number, session in self.active_sessions.items():
            time_diff = (current_time - session.last_activity).total_seconds()
            if time_diff > self.session_timeout:
                expired_sessions.append(phone_number)
        
        for phone_number in expired_sessions:
            del self.active_sessions[phone_number]
            logger.info(f"Expired session for {phone_number}")
    
    async def process_incoming_message(self, webhook_data: Dict[str, Any]) -> bool:
        """Process incoming WhatsApp message."""
        
        try:
            for entry in webhook_data.get("entry", []):
                for change in entry.get("changes", []):
                    if change.get("field") == "messages":
                        messages = change.get("value", {}).get("messages", [])
                        
                        for message in messages:
                            await self._handle_message(message)
                            
            return True
            
        except Exception as e:
            logger.error(f"Error processing webhook data: {e}")
            return False
    
    async def _handle_message(self, message: Dict[str, Any]):
        """Handle individual WhatsApp message."""
        
        phone_number = message.get("from")
        message_type = message.get("type")
        timestamp = datetime.fromtimestamp(int(message.get("timestamp")), timezone.utc)
        
        if not phone_number:
            logger.error("No phone number in message")
            return
        
        # Get or create customer session
        session = self.get_or_create_session(phone_number)
        
        # Extract message content
        message_text = ""
        if message_type == "text":
            message_text = message.get("text", {}).get("body", "")
        elif message_type == "interactive":
            # Handle button responses
            button_reply = message.get("interactive", {}).get("button_reply", {})
            message_text = button_reply.get("title", "")
        
        if not message_text:
            await self.send_whatsapp_message(
                phone_number, 
                "Sorry, I can only handle text messages right now. How can I help you shop today?"
            )
            return
        
        # Add to conversation history
        session.add_message(message_text, "customer")
        
        # Process with shopping agent
        agent_response = await self._get_agent_response(session, message_text)
        
        # Send response back to customer
        if agent_response:
            await self.send_whatsapp_message(phone_number, agent_response)
            session.add_message(agent_response, "agent")
    
    async def _get_agent_response(self, session: CustomerSession, message: str) -> str:
        """Get response from the shopping agent."""
        
        try:
            # Prepare context for the agent
            context = {
                "customer_phone": session.phone_number,
                "session_id": session.session_id,
                "conversation_history": session.conversation_history[-5:],  # Last 5 messages
                "shopping_context": session.shopping_context,
                "channel": "whatsapp"
            }
            
            # TODO: Integrate with actual shopping agent
            # For now, return a simple response
            
            # Check for common shopping intents
            message_lower = message.lower()
            
            if any(word in message_lower for word in ["hi", "hello", "hey", "start"]):
                return ("👋 Hi! I'm your AI shopping assistant. I can help you find products, "
                       "compare prices, create bundles, and complete your purchase right here in WhatsApp!\n\n"
                       "What are you looking to buy today? For example:\n"
                       "• 'I need a new phone'\n"
                       "• 'Show me winter jackets'\n"
                       "• 'Find me a laptop under $1000'")
            
            elif any(word in message_lower for word in ["buy", "shop", "looking for", "need", "want"]):
                # Extract product intent
                return (f"Great! I'll help you find '{message}'. "
                       f"Let me search our catalog for the best options...\n\n"
                       f"🔍 *Searching for products...*\n\n"
                       f"I found several great options! Would you like me to:\n"
                       f"1️⃣ Show you the top 3 recommendations\n"
                       f"2️⃣ Filter by price range\n"
                       f"3️⃣ Show bundle deals\n\n"
                       f"Just reply with 1, 2, or 3!")
            
            elif message_lower in ["1", "2", "3"]:
                if message_lower == "1":
                    return self._generate_product_recommendations()
                elif message_lower == "2":
                    return "💰 What's your budget range?\n\n• Under $50\n• $50-$200\n• $200-$500\n• Over $500\n\nJust tell me your range!"
                elif message_lower == "3":
                    return self._generate_bundle_offers()
            
            else:
                return ("I understand you're interested in shopping! Let me help you find what you need. "
                       "Could you tell me more specifically what you're looking for?")
                
        except Exception as e:
            logger.error(f"Error getting agent response: {e}")
            return "Sorry, I encountered an error. Please try again!"
    
    def _generate_product_recommendations(self) -> str:
        """Generate mock product recommendations with negotiation options."""
        return (
            "🛍️ *Top 3 Recommendations:*\n\n"
            
            "1️⃣ **Premium Wireless Headphones**\n"
            "💰 $199.99 ~~$249.99~~\n"
            "⭐ 4.8/5 stars | Free shipping\n"
            "🎵 Noise cancelling, 30hr battery\n\n"
            
            "2️⃣ **Smart Fitness Watch**\n"
            "💰 $299.99\n"
            "⭐ 4.6/5 stars | 2-day delivery\n"
            "❤️ Heart rate, GPS, waterproof\n\n"
            
            "3️⃣ **Bluetooth Speaker Bundle**\n"
            "💰 $89.99 for 2 speakers!\n"
            "⭐ 4.7/5 stars | Limited time offer\n"
            "🔊 360° sound, 20hr battery each\n\n"
            
            "💬 Reply with the number to select, or:\n"
            "💸 'Negotiate 1' to discuss pricing\n"
            "📦 'Bundle deal' for combo offers\n"
            "🔄 'More options' to see alternatives"
        )
    
    def _generate_bundle_offers(self) -> str:
        """Generate bundle offers with negotiation."""
        return (
            "🎁 *Special Bundle Deals:*\n\n"
            
            "📱 **Tech Bundle** - Save $100!\n"
            "• Wireless Headphones\n"
            "• Phone Case\n"
            "• Wireless Charger\n"
            "💰 $179.99 (was $279.99)\n\n"
            
            "🏃 **Fitness Bundle** - Save $75!\n"
            "• Fitness Watch\n"
            "• Bluetooth Earbuds\n"
            "• Gym Bag\n"
            "💰 $324.99 (was $399.99)\n\n"
            
            "🏠 **Home Audio Bundle** - Save $50!\n"
            "• 2x Bluetooth Speakers\n"
            "• Smart Display\n"
            "• Streaming Device\n"
            "💰 $249.99 (was $299.99)\n\n"
            
            "💬 Interested? Reply:\n"
            "• Bundle name to select\n"
            "• 'Custom bundle' to create your own\n"
            "• 'Negotiate' + bundle name to discuss pricing"
        )


# FastAPI app for webhook handling
app = FastAPI(title="WhatsApp Shopping Agent", version="1.0.0")
whatsapp_agent = WhatsAppShoppingAgent()


@app.get("/webhook")
async def verify_webhook(request: Request):
    """Verify WhatsApp webhook."""
    hub_mode = request.query_params.get("hub.mode")
    hub_token = request.query_params.get("hub.verify_token")
    hub_challenge = request.query_params.get("hub.challenge")
    
    if hub_mode == "subscribe" and hub_token == whatsapp_agent.webhook_verify_token:
        logger.info("Webhook verified successfully")
        return int(hub_challenge)
    else:
        logger.error("Webhook verification failed")
        raise HTTPException(status_code=403, detail="Forbidden")


@app.post("/webhook")
async def handle_webhook(request: Request):
    """Handle incoming WhatsApp messages."""
    try:
        body = await request.json()
        logger.info(f"Received webhook: {json.dumps(body, indent=2)}")
        
        success = await whatsapp_agent.process_incoming_message(body)
        
        if success:
            return {"status": "ok"}
        else:
            raise HTTPException(status_code=500, detail="Processing failed")
            
    except Exception as e:
        logger.error(f"Webhook handling error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "WhatsApp Shopping Agent"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)