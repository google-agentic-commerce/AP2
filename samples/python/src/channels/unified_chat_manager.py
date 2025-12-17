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

"""Unified Multi-Channel Chat Interface.

This module provides a unified interface for handling conversations across
multiple channels (WhatsApp, web chat, SMS, etc.) while maintaining context
and providing consistent shopping experiences.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from pydantic import BaseModel, Field
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from channels.whatsapp_integration import WhatsAppShoppingAgent
from ai_curation.smart_curation_engine import curation_engine
from ai_curation.negotiation_engine import negotiation_engine
from roles.shopping_agent.agent import root_agent

logger = logging.getLogger(__name__)


class ChannelType(Enum):
    """Supported communication channels."""
    
    WHATSAPP = "whatsapp"
    WEB_CHAT = "web_chat"
    SMS = "sms"
    TELEGRAM = "telegram"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"


class MessageType(Enum):
    """Types of messages."""
    
    TEXT = "text"
    IMAGE = "image"
    QUICK_REPLY = "quick_reply"
    BUTTON = "button"
    CAROUSEL = "carousel"
    LOCATION = "location"
    CONTACT = "contact"


class Message(BaseModel):
    """Universal message model."""
    
    id: str
    channel: ChannelType
    sender_id: str
    message_type: MessageType
    content: Union[str, Dict[str, Any]]
    timestamp: datetime
    metadata: Dict[str, Any] = {}
    
    # Channel-specific data
    channel_message_id: Optional[str] = None
    reply_to: Optional[str] = None
    attachments: List[Dict[str, Any]] = []


class ConversationContext(BaseModel):
    """Maintains conversation context across channels."""
    
    customer_id: str
    active_channels: List[ChannelType] = []
    current_channel: Optional[ChannelType] = None
    conversation_history: List[Message] = []
    shopping_context: Dict[str, Any] = {}
    preferences: Dict[str, Any] = {}
    session_start: datetime
    last_activity: datetime
    
    # Shopping-specific context
    current_intent: Optional[str] = None
    cart_items: List[Dict[str, Any]] = []
    browsing_history: List[Dict[str, Any]] = []
    negotiation_state: Optional[Dict[str, Any]] = None


class ChannelAdapter(ABC):
    """Abstract base class for channel adapters."""
    
    @abstractmethod
    async def send_message(self, recipient: str, message: Message) -> bool:
        """Send message through this channel."""
        pass
    
    @abstractmethod
    async def format_message(self, message: Dict[str, Any]) -> Message:
        """Format channel-specific message to universal format."""
        pass
    
    @abstractmethod
    async def format_response(self, message: Message) -> Dict[str, Any]:
        """Format universal message to channel-specific format."""
        pass
    
    @abstractmethod
    def supports_rich_content(self) -> bool:
        """Whether channel supports rich content (buttons, carousels, etc.)."""
        pass


class WhatsAppAdapter(ChannelAdapter):
    """WhatsApp Business API adapter."""
    
    def __init__(self):
        self.whatsapp_agent = WhatsAppShoppingAgent()
    
    async def send_message(self, recipient: str, message: Message) -> bool:
        """Send message via WhatsApp."""
        
        if message.message_type == MessageType.TEXT:
            return await self.whatsapp_agent.send_whatsapp_message(
                recipient, str(message.content)
            )
        elif message.message_type == MessageType.BUTTON:
            content = message.content
            if isinstance(content, dict):
                return await self.whatsapp_agent.send_interactive_message(
                    recipient,
                    content.get("header", ""),
                    content.get("body", ""),
                    content.get("buttons", [])
                )
        
        return False
    
    async def format_message(self, whatsapp_data: Dict[str, Any]) -> Message:
        """Convert WhatsApp message to universal format."""
        
        return Message(
            id=whatsapp_data.get("id", ""),
            channel=ChannelType.WHATSAPP,
            sender_id=whatsapp_data.get("from", ""),
            message_type=MessageType.TEXT,
            content=whatsapp_data.get("text", {}).get("body", ""),
            timestamp=datetime.fromtimestamp(
                int(whatsapp_data.get("timestamp", 0)), timezone.utc
            ),
            channel_message_id=whatsapp_data.get("id")
        )
    
    async def format_response(self, message: Message) -> Dict[str, Any]:
        """Format universal message for WhatsApp."""
        
        if message.message_type == MessageType.TEXT:
            return {
                "messaging_product": "whatsapp",
                "to": message.sender_id,
                "type": "text",
                "text": {"body": str(message.content)}
            }
        elif message.message_type == MessageType.BUTTON:
            content = message.content
            if isinstance(content, dict):
                return {
                    "messaging_product": "whatsapp",
                    "to": message.sender_id,
                    "type": "interactive",
                    "interactive": {
                        "type": "button",
                        "header": {"type": "text", "text": content.get("header", "")},
                        "body": {"text": content.get("body", "")},
                        "action": {"buttons": content.get("buttons", [])}
                    }
                }
        
        return {}
    
    def supports_rich_content(self) -> bool:
        """WhatsApp supports rich content."""
        return True


class WebChatAdapter(ChannelAdapter):
    """Web chat widget adapter."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def send_message(self, recipient: str, message: Message) -> bool:
        """Send message via WebSocket."""
        
        if recipient in self.active_connections:
            try:
                response_data = await self.format_response(message)
                await self.active_connections[recipient].send_text(
                    json.dumps(response_data)
                )
                return True
            except Exception as e:
                logger.error(f"Error sending web chat message: {e}")
                return False
        
        return False
    
    async def format_message(self, web_data: Dict[str, Any]) -> Message:
        """Convert web chat message to universal format."""
        
        return Message(
            id=web_data.get("id", ""),
            channel=ChannelType.WEB_CHAT,
            sender_id=web_data.get("sender_id", ""),
            message_type=MessageType(web_data.get("type", "text")),
            content=web_data.get("content", ""),
            timestamp=datetime.now(timezone.utc),
            metadata=web_data.get("metadata", {})
        )
    
    async def format_response(self, message: Message) -> Dict[str, Any]:
        """Format universal message for web chat."""
        
        return {
            "id": message.id,
            "type": message.message_type.value,
            "content": message.content,
            "timestamp": message.timestamp.isoformat(),
            "sender": "assistant"
        }
    
    def supports_rich_content(self) -> bool:
        """Web chat supports rich content."""
        return True
    
    async def add_connection(self, client_id: str, websocket: WebSocket):
        """Add WebSocket connection."""
        self.active_connections[client_id] = websocket
    
    async def remove_connection(self, client_id: str):
        """Remove WebSocket connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]


class UnifiedChatManager:
    """Manages conversations across all channels."""
    
    def __init__(self):
        self.adapters: Dict[ChannelType, ChannelAdapter] = {
            ChannelType.WHATSAPP: WhatsAppAdapter(),
            ChannelType.WEB_CHAT: WebChatAdapter()
        }
        
        self.active_conversations: Dict[str, ConversationContext] = {}
        self.message_queue = asyncio.Queue()
        
        # AI components
        self.shopping_agent = root_agent
        self.curation_engine = curation_engine
        self.negotiation_engine = negotiation_engine
        
        # Start message processor
        asyncio.create_task(self._process_messages())
    
    async def handle_incoming_message(
        self, 
        channel: ChannelType, 
        raw_message: Dict[str, Any]
    ) -> bool:
        """Handle incoming message from any channel."""
        
        try:
            # Convert to universal format
            adapter = self.adapters[channel]
            message = await adapter.format_message(raw_message)
            
            # Get or create conversation context
            context = self.get_or_create_context(message.sender_id, channel)
            context.conversation_history.append(message)
            context.last_activity = datetime.now(timezone.utc)
            context.current_channel = channel
            
            # Add to processing queue
            await self.message_queue.put((context, message))
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling incoming message: {e}")
            return False
    
    def get_or_create_context(
        self, 
        customer_id: str, 
        channel: ChannelType
    ) -> ConversationContext:
        """Get or create conversation context."""
        
        if customer_id not in self.active_conversations:
            self.active_conversations[customer_id] = ConversationContext(
                customer_id=customer_id,
                session_start=datetime.now(timezone.utc),
                last_activity=datetime.now(timezone.utc)
            )
        
        context = self.active_conversations[customer_id]
        
        if channel not in context.active_channels:
            context.active_channels.append(channel)
        
        return context
    
    async def _process_messages(self):
        """Process messages from the queue."""
        
        while True:
            try:
                context, message = await self.message_queue.get()
                await self._handle_message(context, message)
                self.message_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await asyncio.sleep(1)
    
    async def _handle_message(self, context: ConversationContext, message: Message):
        """Process individual message with shopping intelligence."""
        
        try:
            # Update customer profile for personalization
            interaction_data = {
                "message": str(message.content),
                "channel": message.channel.value,
                "timestamp": message.timestamp,
                "metadata": message.metadata
            }
            
            self.curation_engine.personalization_engine.update_customer_profile(
                context.customer_id, interaction_data
            )
            
            # Determine response strategy
            response_strategy = await self._analyze_message_intent(message, context)
            
            # Generate response
            response = await self._generate_response(message, context, response_strategy)
            
            # Send response
            if response:
                await self._send_response(context, response)
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            # Send error response
            error_response = self._create_error_response(message.sender_id, message.channel)
            await self._send_response(context, error_response)
    
    async def _analyze_message_intent(
        self, 
        message: Message, 
        context: ConversationContext
    ) -> Dict[str, Any]:
        """Analyze message intent and determine response strategy."""
        
        message_text = str(message.content).lower()
        
        # Check for common intents
        intents = {
            "greeting": any(word in message_text for word in ["hi", "hello", "hey", "start"]),
            "product_search": any(word in message_text for word in ["buy", "shop", "looking for", "need", "want", "find"]),
            "price_inquiry": any(word in message_text for word in ["price", "cost", "how much", "expensive"]),
            "negotiation": any(word in message_text for word in ["discount", "deal", "cheaper", "negotiate", "better price"]),
            "comparison": any(word in message_text for word in ["compare", "vs", "better", "alternative"]),
            "cart_action": any(word in message_text for word in ["cart", "checkout", "buy now", "purchase"]),
            "support": any(word in message_text for word in ["help", "support", "problem", "issue"])
        }
        
        # Determine primary intent
        primary_intent = max(intents.keys(), key=lambda k: intents[k])
        
        return {
            "primary_intent": primary_intent if intents[primary_intent] else "general",
            "intents": intents,
            "message_sentiment": self._analyze_sentiment(message_text),
            "urgency_level": self._analyze_urgency(message_text),
            "channel_capabilities": self.adapters[message.channel].supports_rich_content()
        }
    
    def _analyze_sentiment(self, text: str) -> str:
        """Simple sentiment analysis."""
        
        positive_words = ["good", "great", "excellent", "love", "like", "awesome", "perfect"]
        negative_words = ["bad", "terrible", "hate", "dislike", "awful", "horrible", "worst"]
        
        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
    
    def _analyze_urgency(self, text: str) -> float:
        """Analyze message urgency (0-1 scale)."""
        
        urgent_words = ["urgent", "asap", "immediately", "now", "today", "emergency"]
        urgent_count = sum(1 for word in urgent_words if word in text)
        
        return min(1.0, urgent_count * 0.3 + 0.1)
    
    async def _generate_response(
        self, 
        message: Message, 
        context: ConversationContext, 
        strategy: Dict[str, Any]
    ) -> Optional[Message]:
        """Generate appropriate response based on strategy."""
        
        intent = strategy["primary_intent"]
        
        if intent == "greeting":
            return self._create_greeting_response(message, context)
        
        elif intent == "product_search":
            return await self._handle_product_search(message, context)
        
        elif intent == "price_inquiry" or intent == "negotiation":
            return await self._handle_price_negotiation(message, context)
        
        elif intent == "cart_action":
            return await self._handle_cart_action(message, context)
        
        elif intent == "support":
            return self._create_support_response(message, context)
        
        else:
            return await self._handle_general_query(message, context)
    
    def _create_greeting_response(
        self, 
        message: Message, 
        context: ConversationContext
    ) -> Message:
        """Create personalized greeting response."""
        
        # Check if returning customer
        is_returning = len(context.conversation_history) > 1
        
        if is_returning:
            content = ("Welcome back! 👋 I remember you were interested in some great products. "
                      "How can I help you continue your shopping journey today?")
        else:
            content = ("👋 Hi! I'm your AI shopping assistant. I can help you find products, "
                      "compare prices, negotiate deals, and complete purchases right here!\n\n"
                      "What are you looking to buy today? For example:\n"
                      "• 'I need a new laptop'\n"
                      "• 'Show me winter jackets under $200'\n"
                      "• 'Find me the best phone deals'")
        
        return Message(
            id=f"response_{int(datetime.now().timestamp())}",
            channel=message.channel,
            sender_id="assistant",
            message_type=MessageType.TEXT,
            content=content,
            timestamp=datetime.now(timezone.utc)
        )
    
    async def _handle_product_search(
        self, 
        message: Message, 
        context: ConversationContext
    ) -> Message:
        """Handle product search requests."""
        
        # Extract search intent
        search_query = str(message.content)
        
        # Update context
        context.current_intent = search_query
        context.browsing_history.append({
            "query": search_query,
            "timestamp": datetime.now(timezone.utc)
        })
        
        # Mock product recommendations (integrate with actual curation engine)
        content = (f"🔍 Great! I'll help you find '{search_query}'. "
                  f"Let me search our catalog for the best options...\n\n"
                  f"I found several excellent matches! Here are my top recommendations:\n\n"
                  f"1️⃣ **Premium Option** - $299\n"
                  f"⭐ 4.8/5 stars | Free shipping\n"
                  f"🎯 Perfect match for your needs\n\n"
                  f"2️⃣ **Best Value** - $149\n"
                  f"⭐ 4.6/5 stars | 2-day delivery\n"
                  f"💰 Great features at lower price\n\n"
                  f"3️⃣ **Bundle Deal** - $199 (save $50!)\n"
                  f"⭐ 4.7/5 stars | Complete package\n"
                  f"📦 Everything you need included\n\n"
                  f"Which option interests you most? Or would you like me to:\n"
                  f"💬 Negotiate a better price\n"
                  f"🔄 See more alternatives\n"
                  f"📊 Compare features side-by-side")
        
        return Message(
            id=f"response_{int(datetime.now().timestamp())}",
            channel=message.channel,
            sender_id="assistant",
            message_type=MessageType.TEXT,
            content=content,
            timestamp=datetime.now(timezone.utc)
        )
    
    async def _handle_price_negotiation(
        self, 
        message: Message, 
        context: ConversationContext
    ) -> Message:
        """Handle price negotiation requests."""
        
        content = ("💰 I'd be happy to help you get the best price! "
                  "Let me see what I can do...\n\n"
                  "✨ **Special Offer for You:**\n"
                  "• 15% off your first purchase\n"
                  "• Free shipping (save $15)\n"
                  "• Extended 60-day returns\n\n"
                  "This brings your total down from $299 to $254!\n\n"
                  "This exclusive offer is valid for the next 2 hours. "
                  "Shall I add this to your cart with the special pricing?")
        
        return Message(
            id=f"response_{int(datetime.now().timestamp())}",
            channel=message.channel,
            sender_id="assistant",
            message_type=MessageType.TEXT,
            content=content,
            timestamp=datetime.now(timezone.utc)
        )
    
    async def _handle_cart_action(
        self, 
        message: Message, 
        context: ConversationContext
    ) -> Message:
        """Handle cart and checkout actions."""
        
        content = ("🛒 **Your Cart Summary:**\n\n"
                  "📱 Premium Smartphone - $254.00\n"
                  "🚚 Free shipping - $0.00\n"
                  "💰 Discount applied - (-$45.00)\n"
                  "📋 **Total: $254.00**\n\n"
                  "Ready to checkout? I'll guide you through our secure AP2 payment process. "
                  "It's fast, safe, and you can pay with your preferred method.\n\n"
                  "Just say 'checkout' to proceed, or 'add more' to continue shopping!")
        
        return Message(
            id=f"response_{int(datetime.now().timestamp())}",
            channel=message.channel,
            sender_id="assistant",
            message_type=MessageType.TEXT,
            content=content,
            timestamp=datetime.now(timezone.utc)
        )
    
    def _create_support_response(
        self, 
        message: Message, 
        context: ConversationContext
    ) -> Message:
        """Create support response."""
        
        content = ("🆘 I'm here to help! I can assist you with:\n\n"
                  "🛍️ **Shopping:**\n"
                  "• Finding products\n"
                  "• Comparing options\n"
                  "• Getting best prices\n\n"
                  "💳 **Orders & Payments:**\n"
                  "• Secure checkout\n"
                  "• Order status\n"
                  "• Returns & refunds\n\n"
                  "What specific help do you need today?")
        
        return Message(
            id=f"response_{int(datetime.now().timestamp())}",
            channel=message.channel,
            sender_id="assistant",
            message_type=MessageType.TEXT,
            content=content,
            timestamp=datetime.now(timezone.utc)
        )
    
    async def _handle_general_query(
        self, 
        message: Message, 
        context: ConversationContext
    ) -> Message:
        """Handle general queries."""
        
        content = ("I understand you're looking for assistance! I'm your AI shopping assistant "
                  "and I specialize in helping you find great products and complete purchases.\n\n"
                  "Here's what I can help you with:\n"
                  "🔍 Find specific products\n"
                  "💰 Get the best prices and deals\n"
                  "📦 Create perfect bundles\n"
                  "🛒 Complete secure checkout\n\n"
                  "What would you like to shop for today?")
        
        return Message(
            id=f"response_{int(datetime.now().timestamp())}",
            channel=message.channel,
            sender_id="assistant",
            message_type=MessageType.TEXT,
            content=content,
            timestamp=datetime.now(timezone.utc)
        )
    
    def _create_error_response(self, sender_id: str, channel: ChannelType) -> Message:
        """Create error response."""
        
        return Message(
            id=f"error_{int(datetime.now().timestamp())}",
            channel=channel,
            sender_id="assistant",
            message_type=MessageType.TEXT,
            content="Sorry, I encountered an issue. Please try again or contact support if the problem persists.",
            timestamp=datetime.now(timezone.utc)
        )
    
    async def _send_response(self, context: ConversationContext, response: Message):
        """Send response through appropriate channel."""
        
        channel = context.current_channel
        if channel and channel in self.adapters:
            adapter = self.adapters[channel]
            success = await adapter.send_message(context.customer_id, response)
            
            if success:
                context.conversation_history.append(response)
            else:
                logger.error(f"Failed to send response via {channel}")
    
    def get_conversation_analytics(self, customer_id: str) -> Dict[str, Any]:
        """Get conversation analytics for a customer."""
        
        if customer_id not in self.active_conversations:
            return {}
        
        context = self.active_conversations[customer_id]
        
        return {
            "total_messages": len(context.conversation_history),
            "conversation_duration": (
                context.last_activity - context.session_start
            ).total_seconds() / 60,  # minutes
            "active_channels": [ch.value for ch in context.active_channels],
            "current_intent": context.current_intent,
            "cart_value": sum(item.get("price", 0) for item in context.cart_items),
            "browsing_history_count": len(context.browsing_history)
        }


# FastAPI app for web chat
app = FastAPI(title="Unified Chat Manager", version="1.0.0")

# Initialize chat manager
chat_manager = UnifiedChatManager()

# Serve static files for web chat widget
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def get_chat_widget():
    """Serve the web chat widget."""
    
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Shopping Assistant</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
            #chat-container { max-width: 600px; margin: 0 auto; border: 1px solid #ccc; height: 600px; display: flex; flex-direction: column; }
            #messages { flex: 1; padding: 20px; overflow-y: auto; }
            .message { margin: 10px 0; padding: 10px; border-radius: 5px; }
            .user { background-color: #007bff; color: white; text-align: right; }
            .assistant { background-color: #f1f1f1; }
            #input-container { padding: 20px; border-top: 1px solid #ccc; display: flex; }
            #message-input { flex: 1; padding: 10px; margin-right: 10px; }
            #send-btn { padding: 10px 20px; background-color: #007bff; color: white; border: none; cursor: pointer; }
        </style>
    </head>
    <body>
        <div id="chat-container">
            <div id="messages"></div>
            <div id="input-container">
                <input type="text" id="message-input" placeholder="Type your message..." />
                <button id="send-btn">Send</button>
            </div>
        </div>

        <script>
            const ws = new WebSocket("ws://localhost:8000/ws/web_chat_user");
            const messages = document.getElementById("messages");
            const input = document.getElementById("message-input");
            const sendBtn = document.getElementById("send-btn");

            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                addMessage(data.content, "assistant");
            };

            function addMessage(content, sender) {
                const messageDiv = document.createElement("div");
                messageDiv.className = `message ${sender}`;
                messageDiv.textContent = content;
                messages.appendChild(messageDiv);
                messages.scrollTop = messages.scrollHeight;
            }

            function sendMessage() {
                const message = input.value.trim();
                if (message) {
                    addMessage(message, "user");
                    ws.send(JSON.stringify({
                        type: "text",
                        content: message,
                        sender_id: "web_chat_user"
                    }));
                    input.value = "";
                }
            }

            sendBtn.onclick = sendMessage;
            input.onkeypress = function(e) {
                if (e.key === "Enter") sendMessage();
            };

            // Send initial greeting
            setTimeout(() => {
                ws.send(JSON.stringify({
                    type: "text",
                    content: "Hi",
                    sender_id: "web_chat_user"
                }));
            }, 1000);
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for web chat."""
    
    await websocket.accept()
    
    # Add connection to web chat adapter
    web_adapter = chat_manager.adapters[ChannelType.WEB_CHAT]
    await web_adapter.add_connection(client_id, websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            message_data["sender_id"] = client_id
            
            # Handle message through unified manager
            await chat_manager.handle_incoming_message(
                ChannelType.WEB_CHAT, message_data
            )
            
    except WebSocketDisconnect:
        await web_adapter.remove_connection(client_id)


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: dict):
    """Handle WhatsApp webhook."""
    
    return await chat_manager.handle_incoming_message(
        ChannelType.WHATSAPP, request
    )


@app.get("/analytics/{customer_id}")
async def get_customer_analytics(customer_id: str):
    """Get customer conversation analytics."""
    
    return chat_manager.get_conversation_analytics(customer_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)