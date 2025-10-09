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

"""A merchant agent for AP2.

The merchant agent's role is to:
1. Provide catalog search capabilities for customers
2. Handle customer inquiries about products and services
3. Support the Agent Payments Protocol for transaction processing

This agent can be run in two modes:
1. ADK mode (for web interface): Uses the root_agent definition below
2. A2A server mode (for production): Uses the __main__.py entry point
"""

import json
from . import tools
from .sub_agents.catalog_agent import find_items_workflow
from common.retrying_llm_agent import RetryingLlmAgent
from common.system_utils import DEBUG_MODE_INSTRUCTIONS


async def search_catalog(shopping_intent: str) -> str:
    """Search the merchant's catalog based on shopping intent.
    
    Args:
        shopping_intent: A JSON string or text describing what the user wants to buy
        
    Returns:
        A string describing the search results and available products
    """
    # This is a simplified wrapper around the catalog agent for ADK compatibility
    # In production, this would delegate to the full find_items_workflow
    try:
        # Parse the shopping intent if it's JSON
        if shopping_intent.strip().startswith('{'):
            intent_data = json.loads(shopping_intent)
            intent_text = intent_data.get('query', shopping_intent)
        else:
            intent_text = shopping_intent
            
        # For now, return a helpful response - in a full implementation,
        # this would call the catalog_agent.find_items_workflow
        return f"""I found several products matching "{intent_text}". Here are some options:

        🛍️ Product Search Results:
        - Premium Running Shoes - $129.99 (Free shipping)
        - Wireless Bluetooth Headphones - $79.99 (On sale)
        - Organic Cotton T-Shirt - $24.99 (Multiple colors)
        - Laptop Backpack - $49.99 (Water-resistant)
        
        Would you like more details about any of these items, or would you like me to search for something more specific?
        
        Note: This is the ADK web interface demo. For full catalog functionality, 
        use the A2A server mode with other agents."""
        
    except json.JSONDecodeError:
        return f"""I found products related to "{shopping_intent}". Let me show you what's available:
        
        🛍️ Available Products:
        - Featured items matching your search
        - Popular products in this category
        - Special offers and deals
        
        Please let me know if you'd like specific product details or have other questions!"""


root_agent = RetryingLlmAgent(
    max_retries=3,
    model="gemini-2.5-flash",
    name="merchant_agent",
    instruction="""
          You are a merchant agent responsible for helping customers find 
          products and providing information about your catalog.

          Follow these instructions based on the customer's request:

    %s

          Primary Functions:

          1. Product Search & Discovery:
             - When customers ask about products, use the `search_catalog` tool
             - Provide detailed product information including prices, availability
             - Help customers find products that match their shopping intent
             - Suggest alternatives if requested products are not available

          2. Customer Service:
             - Answer questions about products, pricing, and policies
             - Provide helpful recommendations based on customer needs
             - Maintain a professional and helpful tone

          3. Agent Payments Protocol Support:
             - Support AP2 mandate creation and payment processing
             - Work with other agents in the payment ecosystem
             - Ensure secure and compliant transaction handling

          Response Guidelines:
          - Always be helpful and professional
          - Provide accurate product information
          - If you cannot find a product, suggest alternatives
          - Keep responses concise but informative
          - Use the search_catalog tool when customers express shopping intent

          Example Interactions:
          - "I'm looking for running shoes" → Use search_catalog tool
          - "Do you have laptops under $1000?" → Search and filter results
          - "What's your return policy?" → Provide merchant policy information
          
          Note: You are running in ADK web interface mode. For full AP2 functionality
          including payment processing, the A2A server mode should be used with
          all four agents (shopping, merchant, credentials, payment processor).
          """ % DEBUG_MODE_INSTRUCTIONS,
    tools=[
        search_catalog,
    ],
    sub_agents=[
        # Note: sub_agents are not available in ADK mode for this demo
    ],
)