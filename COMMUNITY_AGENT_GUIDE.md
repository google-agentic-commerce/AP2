# Community Agent Development Guide

> **Note**: This is a community-driven guide based on analysis of the AP2 codebase and implementation patterns. It complements the official [AP2 specification](docs/specification.md) by providing practical development insights derived from the working sample implementations.

## Overview

The Agent Payments Protocol (AP2) provides a framework for building secure, interoperable AI agents that can participate in commerce transactions. This guide analyzes the implementation patterns found in the AP2 samples to help developers understand how to build their own agents.

## Agent Architecture Patterns

### Core Agent Structure

All AP2 agents follow a consistent architectural pattern built around the `RetryingLlmAgent` class:

```python
from common.retrying_llm_agent import RetryingLlmAgent
from common.system_utils import DEBUG_MODE_INSTRUCTIONS

# Module-level constants
_GEMINI_MODEL = "gemini-2.5-flash"

root_agent = RetryingLlmAgent(
    max_retries=3,  # Varies by agent (3-5 typically)
    model=_GEMINI_MODEL,
    name="agent_name",
    instruction="""
        Agent-specific instructions here...

        %s  # DEBUG_MODE_INSTRUCTIONS injection point
    """ % DEBUG_MODE_INSTRUCTIONS,
    tools=[
        # Agent-specific tools
    ],
    sub_agents=[
        # Optional sub-agents for delegation
    ],
)
```

### The Four Agent Roles

AP2 defines four distinct agent roles:

#### 1. Shopping Agent (`samples/python/src/roles/shopping_agent/`)
- **Purpose**: User-facing agent that orchestrates the shopping experience
- **Key Features**: Sub-agent delegation, workflow coordination
- **Tools**: Payment processing, cart management, mandate signing
- **Sub-agents**: `shopper`, `shipping_address_collector`, `payment_method_collector`

#### 2. Merchant Agent (`samples/python/src/roles/merchant_agent/`)
- **Purpose**: Represents merchant capabilities and catalog search
- **Key Features**: Dual-mode operation (ADK web + A2A server)
- **Tools**: Catalog search, cart updates, payment initiation
- **Dual Architecture**:
  - `agent.py` - ADK web interface mode
  - `__main__.py` + `agent_executor.py` - A2A server mode

#### 3. Credentials Provider Agent (`samples/python/src/roles/credentials_provider_agent/`)
- **Purpose**: Manages user payment credentials and authentication
- **Key Features**: Secure credential handling, authentication flows
- **Tools**: Payment method retrieval, credential validation

#### 4. Payment Processor Agent (`samples/python/src/roles/merchant_payment_processor_agent/`)
- **Purpose**: Handles actual payment processing and network communication
- **Key Features**: Transaction processing, challenge handling
- **Tools**: Payment authorization, fraud detection, settlement

## Dual-Mode Architecture Pattern

The merchant agent demonstrates a sophisticated dual-mode pattern that other agents can adopt:

### ADK Web Interface Mode (`agent.py`)
```python
# For development and testing with web interface
async def search_catalog(shopping_intent: str) -> str:
    """Tool function for ADK web interface."""
    # Implementation here...

root_agent = RetryingLlmAgent(
    # Configuration for web interface mode
)
```

### A2A Server Mode (`__main__.py` + `agent_executor.py`)
```python
# For production server deployment
def main(argv: Sequence[str]) -> None:
    agent_card = server.load_local_agent_card(__file__)
    server.run_agent_blocking(
        port=AGENT_PORT,
        agent_card=agent_card,
        executor=AgentExecutor(agent_card.capabilities.extensions),
        rpc_url="/a2a/agent_name",
    )
```

This pattern allows agents to:
- ✅ **Development**: Use ADK web interface for interactive testing
- ✅ **Production**: Deploy as A2A servers for agent-to-agent communication
- ✅ **Flexibility**: Switch modes without code changes

## Tool Implementation Patterns

### Async Tool Functions
All agent tools follow this pattern:

```python
async def tool_name(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
    debug_mode: bool = False,
) -> None:
    """Tool description for LLM understanding.

    Args:
        data_parts: Input data from previous agent interactions
        updater: Task updater for progress tracking
        current_task: Current task context
        debug_mode: Whether agent is in debug mode
    """
    try:
        # Tool implementation
        # Use updater.add_artifact() to return data
        # Use await updater.complete() to finish successfully
    except Exception as e:
        # Error handling pattern
        error_message = updater.new_agent_message(
            parts=[Part(root=TextPart(text=f"Error: {e}"))]
        )
        await updater.failed(message=error_message)
```

### ADK-Compatible Tool Functions
For ADK web interface mode, use simpler function signatures:

```python
async def simple_tool(parameter: str) -> str:
    """Simple tool for ADK web interface.

    Args:
        parameter: Input parameter

    Returns:
        String response for user
    """
    # Implementation
    return "Response text"
```

## Sub-Agent Delegation Pattern

The shopping agent demonstrates effective sub-agent usage:

```python
# In main agent instruction
"""
1. Delegate to the `shopper` agent to collect products
2. Once successful, delegate to `shipping_address_collector`
3. Finally, delegate to `payment_method_collector`
"""

# Sub-agent definitions
sub_agents=[
    shopper,
    shipping_address_collector,
    payment_method_collector,
],
```

### Sub-Agent Implementation
```python
# Each sub-agent is also a RetryingLlmAgent
shopper = RetryingLlmAgent(
    model="gemini-2.5-flash",
    name="shopper",
    max_retries=5,
    instruction="""
        You are a specialized agent for product discovery...
    """,
    tools=[
        # Sub-agent specific tools
    ],
)
```

## Configuration Management

### Agent Cards (`agent.json`)
Every agent requires an agent card configuration:

```json
{
  "name": "AgentName",
  "description": "Agent description",
  "capabilities": {
    "extensions": [
      {
        "description": "Supports the A2A payments extension.",
        "required": true,
        "uri": "https://google-a2a.github.io/A2A/extensions/payments/v1"
      }
    ]
  },
  "skills": [
    {
      "id": "skill_name",
      "name": "Skill Display Name",
      "description": "What this skill does",
      "tags": ["category", "keywords"]
    }
  ],
  "url": "http://localhost:PORT/a2a/agent_name",
  "version": "1.0.0"
}
```

### Server Configuration Pattern
```python

from common import server

AGENT_PORT = 8001  # Unique port per agent

def main(argv: Sequence[str]) -> None:
    agent_card = server.load_local_agent_card(__file__)
    server.run_agent_blocking(
        port=AGENT_PORT,
        agent_card=agent_card,
        executor=YourAgentExecutor(agent_card.capabilities.extensions),
        rpc_url="/a2a/your_agent",
    )

if __name__ == "__main__":
    app.run(main)
```

## Error Handling and Retry Logic

### RetryingLlmAgent Benefits
The codebase uses `RetryingLlmAgent` instead of basic `LlmAgent` for:

- **Automatic retry logic**: Configurable `max_retries` parameter
- **Error surfacing**: Shows errors to users before retrying
- **Graceful degradation**: Handles Gemini server failures

### Implementation
```python
class RetryingLlmAgent(LlmAgent):
    def __init__(self, *args, max_retries: int = 1, **kwargs):
        super().__init__(*args, **kwargs)
        self._max_retries = max_retries

    async def _retry_async(self, ctx: InvocationContext, retries_left: int = 0):
        if retries_left <= 0:
            yield Event(error_message="Maximum retries exhausted...")
        else:
            try:
                async for event in super()._run_async_impl(ctx):
                    yield event
            except Exception as e:
                yield Event(error_message="Gemini server error. Retrying...")
                async for event in self._retry_async(ctx, retries_left - 1):
                    yield event
```

## A2A Communication Patterns

### Remote Agent Client
```python
from common.payment_remote_a2a_client import PaymentRemoteA2aClient

remote_agent = PaymentRemoteA2aClient(
    name="target_agent",
    base_url="http://localhost:PORT/a2a/target_agent",
    required_extensions={"https://google-a2a.github.io/A2A/extensions/payments/v1"},
)

# Send message to remote agent
message = A2aMessageBuilder().add_text("Request").build()
task = await remote_agent.send_a2a_message(message)
```

### Message Building
```python
from common.a2a_message_builder import A2aMessageBuilder

message = (
    A2aMessageBuilder()
    .set_context_id(context_id)
    .add_text("Message text")
    .add_data_part({"key": "value"})
    .build()
)
```

## Development Best Practices

### 1. Model Configuration
```python
# Extract model names as constants
_GEMINI_MODEL = "gemini-2.5-flash"

# Use in agent configuration
model=_GEMINI_MODEL,
```

### 2. Debug Mode Support
```python
# Always include debug mode instructions
instruction="""
    Agent instructions...

    %s
""" % DEBUG_MODE_INSTRUCTIONS,
```

### 3. JSON Parsing Robustness
```python
# Robust JSON parsing pattern
intent_text = shopping_intent
try:
    intent_data = json.loads(shopping_intent)
    if isinstance(intent_data, dict):
        intent_text = intent_data.get('query', shopping_intent)
except json.JSONDecodeError:
    # Not valid JSON, treat as plain text
    pass
```

### 4. Error Handling in Tools
```python
try:
    # Tool implementation
    await updater.complete()
except ValidationError as e:
    error_message = updater.new_agent_message(
        parts=[Part(root=TextPart(text=f"Validation error: {e}"))]
    )
    await updater.failed(message=error_message)
except Exception as e:
    # Generic error handling
    await _fail_task(updater, f"Unexpected error: {e}")
```

## Testing Patterns

### Development Server Testing
```bash
# Start individual agents for testing
uv run python -m roles.shopping_agent
uv run python -m roles.merchant_agent
uv run python -m roles.credentials_provider_agent
uv run python -m roles.merchant_payment_processor_agent
```

### ADK Web Interface Testing
```bash
# Start ADK web server for interactive testing
uv run adk web samples/python/src/roles
```

### Scenario Testing
```bash
# Run complete scenarios
bash samples/python/scenarios/a2a/human-present/cards/run.sh
```

## Common Patterns Summary

1. **Module Constants**: Extract configuration values as module-level constants
2. **Dual Mode Support**: Separate ADK and A2A implementations when needed
3. **Robust Error Handling**: Use try/catch with proper error messaging
4. **JSON Parsing**: Handle both JSON and plain text inputs gracefully
5. **Sub-Agent Delegation**: Clear delegation patterns with specific instructions
6. **Tool Consistency**: Consistent async function signatures and return patterns
7. **Retry Logic**: Use RetryingLlmAgent for production robustness

## Next Steps

1. **Study the samples**: Review `samples/python/src/roles/` for complete implementations
2. **Start with ADK mode**: Begin with simple agent.py for web interface testing
3. **Add A2A mode**: Implement server mode when ready for agent-to-agent communication
4. **Follow patterns**: Use the established patterns for consistency and reliability

---

*This guide is derived from analysis of the AP2 sample implementations as of October 2025. For the latest official specifications, see the [AP2 documentation](docs/).*
