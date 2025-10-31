"""Anthropic provider implementation."""

import logging
import os
from typing import TYPE_CHECKING

from collections.abc import AsyncGenerator
from typing import Any


if TYPE_CHECKING:
    import anthropic

try:
    import anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    # Create a dummy class for type checking when anthropic is not available
    class anthropic:
        class AsyncAnthropic:
            pass

from ap2 import LLMConfig, LLMProvider, LLMProviderFactory, LLMResponse


class AnthropicProvider(LLMProvider):
    """Anthropic Claude LLM provider."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                'Anthropic package is not installed. Install it with: pip install anthropic'
            )
        self._client: anthropic.AsyncAnthropic | None = None

    def _get_client(self) -> anthropic.AsyncAnthropic:
        """Get or create the Anthropic client."""
        if self._client is None:
            client_config = {}
            if self.config.api_key:
                client_config['api_key'] = self.config.api_key
            if self.config.base_url:
                client_config['base_url'] = self.config.base_url

            self._client = anthropic.AsyncAnthropic(**client_config)
        return self._client

    def get_model_name(self) -> str:
        """Get the model name for this provider."""
        return self.config.model

    def validate_config(self) -> bool:
        """Validate the provider configuration."""
        if not ANTHROPIC_AVAILABLE:
            logging.error('Anthropic package is not available')
            return False
        if not self.config.api_key and not os.getenv('ANTHROPIC_API_KEY'):
            logging.warning(
                'Anthropic API key not found in config or environment'
            )
            return False
        return True

    def _convert_tools_to_anthropic_format(
        self, tools: list[dict[str, Any]] | None
    ) -> list[dict[str, Any]] | None:
        """Convert tools to Anthropic format."""
        if not tools:
            return None

        # Anthropic has a different tool format
        # This is a simplified conversion - you might need more sophisticated mapping
        anthropic_tools = []
        for tool in tools:
            if 'function' in tool:
                anthropic_tools.append(
                    {
                        'name': tool['function'].get('name', ''),
                        'description': tool['function'].get('description', ''),
                        'input_schema': tool['function'].get('parameters', {}),
                    }
                )

        return anthropic_tools if anthropic_tools else None

    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate text using Anthropic Claude."""
        try:
            client = self._get_client()

            # Prepare messages
            messages = [{'role': 'user', 'content': prompt}]

            # Prepare request parameters
            request_params = {
                'model': self.config.model,
                'messages': messages,
                'temperature': self.config.temperature,
                'max_tokens': self.config.max_tokens or 4096,
            }

            # Add system instruction if provided
            if system_instruction:
                request_params['system'] = system_instruction

            # Add tools if provided (Anthropic supports tools)
            anthropic_tools = self._convert_tools_to_anthropic_format(tools)
            if anthropic_tools:
                request_params['tools'] = anthropic_tools

            response = await client.messages.create(**request_params)

            # Extract content from response
            content = ''
            if response.content:
                for block in response.content:
                    if hasattr(block, 'text') and block.text:
                        content += block.text

            # Extract usage information
            usage = None
            if response.usage:
                usage = {
                    'input_tokens': response.usage.input_tokens,
                    'output_tokens': response.usage.output_tokens,
                }

            return LLMResponse(
                content=content, usage=usage, metadata={'model': response.model}
            )

        except Exception as e:
            logging.error(f'Error generating text with Anthropic: {e}')
            raise

    async def generate_text_stream(
        self,
        prompt: str,
        system_instruction: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> AsyncGenerator[LLMResponse, None]:
        """Generate text using streaming with Anthropic Claude."""
        try:
            client = self._get_client()

            # Prepare messages
            messages = [{'role': 'user', 'content': prompt}]

            # Prepare request parameters
            request_params = {
                'model': self.config.model,
                'messages': messages,
                'temperature': self.config.temperature,
                'max_tokens': self.config.max_tokens or 4096,
                'stream': True,
            }

            # Add system instruction if provided
            if system_instruction:
                request_params['system'] = system_instruction

            # Add tools if provided
            anthropic_tools = self._convert_tools_to_anthropic_format(tools)
            if anthropic_tools:
                request_params['tools'] = anthropic_tools

            stream = await client.messages.create(**request_params)

            async for event in stream:
                if event.type == 'content_block_delta' and event.delta.text:
                    yield LLMResponse(
                        content=event.delta.text, metadata={'chunk': True}
                    )

        except Exception as e:
            logging.error(f'Error generating text stream with Anthropic: {e}')
            raise


# Register the Anthropic provider
LLMProviderFactory.register_provider('anthropic', AnthropicProvider)
