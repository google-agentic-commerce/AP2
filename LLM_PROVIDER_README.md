# AP2 LLM Provider System

The AP2 project now supports multiple LLM providers in a provider-agnostic way, similar to the Vercel AI SDK. This allows you to easily switch between different LLM services and add new providers.

## Overview

The provider system consists of:

- **LLMConfig**: Configuration class for provider settings
- **LLMProvider**: Abstract base class for all providers
- **Provider implementations**: Concrete implementations for different services (Google Gemini, OpenAI, Anthropic, etc.)
- **LLMProviderFactory**: Factory for creating provider instances
- **ProviderAgnosticLlmAgent**: Updated agent that uses the provider system

## Quick Start

### Using Environment Variables

Set your API key and configure the provider:

```bash
export GOOGLE_API_KEY="your-api-key-here"
export GOOGLE_MODEL="gemini-2.5-flash"
```

Then use the updated agent:

```python
from ap2.providers.llm_agent import RetryingLlmAgent

# The agent will automatically use the GOOGLE_API_KEY and GOOGLE_MODEL environment variables
agent = RetryingLlmAgent(
    model="gemini-2.5-flash",  # This is now optional, defaults to env var
    provider="google",         # This is now optional, defaults to "google"
    max_retries=3
)
```

### Using Configuration Files

Create a configuration file:

```json
{
  "provider": "google",
  "model": "gemini-2.5-flash",
  "api_key": "your-api-key-here",
  "temperature": 0.7,
  "max_tokens": 4096
}
```

Load it in your code:

```python
from ap2.providers import LLMConfig, LLMProviderFactory, ProviderAgnosticLlmAgent

# Load from file
config = LLMConfig.from_dict(json.load(open('path/to/config.json')))
provider = LLMProviderFactory.create_provider(config)

# Use with agent
agent = ProviderAgnosticLlmAgent(
    provider=provider,
    name="my_agent",
    instruction="You are a helpful assistant."
)
```

## Supported Providers

### Google Gemini

```python
config = LLMConfig(
    provider="google",
    model="gemini-2.5-flash",
    api_key="your-google-api-key",
    temperature=0.7
)
```

### OpenAI

```python
config = LLMConfig(
    provider="openai",
    model="gpt-4",
    api_key="your-openai-api-key",
    base_url="https://api.openai.com/v1"  # Optional
)
```

### Anthropic Claude

```python
config = LLMConfig(
    provider="anthropic",
    model="claude-3-5-sonnet-20241022",
    api_key="your-anthropic-api-key"
)
```

## Migration from Old System

### Before (Hardcoded)

```python
# Old way - hardcoded model
agent = RetryingLlmAgent(
    model="gemini-2.5-flash",
    name="root_agent",
    instruction="You are a shopping agent...",
    max_retries=5
)
```

### After (Provider-agnostic)

```python
# New way - provider agnostic
agent = RetryingLlmAgent(
    model="gemini-2.5-flash",  # Still supported for backward compatibility
    provider="google",         # Explicitly specify provider
    name="root_agent",
    instruction="You are a shopping agent...",
    max_retries=5
)

# Or use configuration
config = LLMConfig.from_env(provider="google")
agent = ProviderAgnosticLlmAgent(
    provider_config=config,
    name="root_agent",
    instruction="You are a shopping agent...",
    max_retries=5
)
```

## Adding New Providers

To add a new LLM provider, follow these steps:

### 1. Create Provider Implementation

Create a new file in `ap2/providers/` (e.g., `custom_provider.py`):

```python
from . import LLMConfig, LLMProvider, LLMResponse

class CustomProvider(LLMProvider):
    """Custom LLM provider implementation."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        # Initialize your client here
        self._client = None

    def get_model_name(self) -> str:
        return self.config.model

    def validate_config(self) -> bool:
        # Validate your configuration
        return True

    async def generate_text(self, prompt: str, **kwargs) -> LLMResponse:
        # Implement text generation
        pass

    async def generate_text_stream(self, prompt: str, **kwargs) -> AsyncGenerator[LLMResponse, None]:
        # Implement streaming text generation
        pass

# Register the provider
LLMProviderFactory.register_provider("custom", CustomProvider)
```

### 2. Handle Dependencies

If your provider requires additional packages, make them optional:

```python
try:
    import custom_llm_library
    CUSTOM_AVAILABLE = True
except ImportError:
    CUSTOM_AVAILABLE = False

class CustomProvider(LLMProvider):
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        if not CUSTOM_AVAILABLE:
            raise ImportError("Custom LLM library not installed")

    def validate_config(self) -> bool:
        if not CUSTOM_AVAILABLE:
            return False
        # ... rest of validation
```

### 3. Add Configuration Example

Create a configuration file example:

```json
{
  "provider": "custom",
  "model": "custom-model-name",
  "api_key": "${CUSTOM_API_KEY}",
  "custom_param": "custom_value"
}
```

### 4. Update Documentation

Add your provider to this documentation with:

- Setup instructions
- Required environment variables
- Configuration options
- Any special considerations

## Environment Variables

The system supports these environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `{PROVIDER}_API_KEY` | API key for the provider | `GOOGLE_API_KEY=abc123` |
| `{PROVIDER}_MODEL` | Default model name | `GOOGLE_MODEL=gemini-2.5-flash` |
| `{PROVIDER}_BASE_URL` | Custom API endpoint | `OPENAI_BASE_URL=https://custom.api.com` |
| `{PROVIDER}_TEMPERATURE` | Default temperature | `ANTHROPIC_TEMPERATURE=0.5` |
| `{PROVIDER}_MAX_TOKENS` | Default max tokens | `OPENAI_MAX_TOKENS=4096` |
| `{PROVIDER}_TIMEOUT` | Request timeout | `GOOGLE_TIMEOUT=60` |
| `{PROVIDER}_MAX_RETRIES` | Max retry attempts | `ANTHROPIC_MAX_RETRIES=3` |

## Best Practices

1. **Use Environment Variables**: Store API keys and sensitive configuration in environment variables
2. **Version Pin Dependencies**: Pin specific versions of provider libraries for stability
3. **Handle Rate Limits**: Implement appropriate retry logic and rate limiting
4. **Monitor Usage**: Track API usage and costs across different providers
5. **Fallback Configuration**: Provide fallback configurations for production deployments
6. **Error Handling**: Implement proper error handling and user feedback

## Troubleshooting

### Common Issues

1. **"Unknown provider" error**: Make sure to register your provider with `LLMProviderFactory.register_provider()`
2. **Import errors**: Ensure optional dependencies are properly handled with try/except
3. **API key issues**: Verify environment variables are set correctly
4. **Network timeouts**: Adjust timeout settings in your configuration

### Debug Mode

Enable debug logging to troubleshoot provider issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Your provider initialization code here
```

## Examples

See the `configs/` directory for example configurations for different providers.
