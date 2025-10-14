"""OpenAI provider implementation."""

import logging
import os

from collections.abc import AsyncGenerator
from typing import Any


try:
    from openai import AsyncOpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from . import LLMConfig, LLMProvider, LLMProviderFactory, LLMResponse


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        if not OPENAI_AVAILABLE:
            raise ImportError(
                'OpenAI package is not installed. Install it with: pip install openai'
            )
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        """Get or create the OpenAI client."""
        if self._client is None:
            client_config = {}
            if self.config.api_key:
                client_config['api_key'] = self.config.api_key
            if self.config.base_url:
                client_config['base_url'] = self.config.base_url

            self._client = AsyncOpenAI(**client_config)
        return self._client

    def get_model_name(self) -> str:
        """Get the model name for this provider."""
        return self.config.model

    def validate_config(self) -> bool:
        """Validate the provider configuration."""
        if not OPENAI_AVAILABLE:
            logging.error('OpenAI package is not available')
            return False
        if not self.config.api_key and not os.getenv('OPENAI_API_KEY'):
            logging.warning('OpenAI API key not found in config or environment')
            return False
        return True

    def _convert_tools_to_openai_format(
        self, tools: list[dict[str, Any]] | None
    ) -> list[dict[str, Any]] | None:
        """Convert tools to OpenAI format."""
        if not tools:
            return None

        # OpenAI expects tools in a different format
        # This is a simplified conversion - you might need more sophisticated mapping
        openai_tools = []
        for tool in tools:
            if 'function' in tool:
                openai_tools.append(
                    {'type': 'function', 'function': tool['function']}
                )

        return openai_tools if openai_tools else None

    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate text using OpenAI."""
        try:
            client = self._get_client()
            messages = []

            # Add system instruction if provided
            if system_instruction:
                messages.append(
                    {'role': 'system', 'content': system_instruction}
                )

            # Add user prompt
            messages.append({'role': 'user', 'content': prompt})

            # Prepare request parameters
            request_params = {
                'model': self.config.model,
                'messages': messages,
                'temperature': self.config.temperature,
                'max_tokens': self.config.max_tokens,
            }

            # Add tools if provided
            openai_tools = self._convert_tools_to_openai_format(tools)
            if openai_tools:
                request_params['tools'] = openai_tools

            response = await client.chat.completions.create(**request_params)

            # Extract content from response
            content = ''
            if response.choices and response.choices[0].message.content:
                content = response.choices[0].message.content

            # Extract usage information
            usage = None
            if response.usage:
                usage = {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens,
                }

            return LLMResponse(
                content=content,
                usage=usage,
                finish_reason=response.choices[0].finish_reason
                if response.choices
                else None,
                metadata={'model': response.model},
            )

        except Exception as e:
            logging.error(f'Error generating text with OpenAI: {e}')
            raise

    async def generate_text_stream(
        self,
        prompt: str,
        system_instruction: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> AsyncGenerator[LLMResponse, None]:
        """Generate text using streaming with OpenAI."""
        try:
            client = self._get_client()
            messages = []

            # Add system instruction if provided
            if system_instruction:
                messages.append(
                    {'role': 'system', 'content': system_instruction}
                )

            # Add user prompt
            messages.append({'role': 'user', 'content': prompt})

            # Prepare request parameters
            request_params = {
                'model': self.config.model,
                'messages': messages,
                'temperature': self.config.temperature,
                'max_tokens': self.config.max_tokens,
                'stream': True,
            }

            # Add tools if provided
            openai_tools = self._convert_tools_to_openai_format(tools)
            if openai_tools:
                request_params['tools'] = openai_tools

            stream = await client.chat.completions.create(**request_params)

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield LLMResponse(
                        content=chunk.choices[0].delta.content,
                        metadata={'chunk': True},
                    )

        except Exception as e:
            logging.error(f'Error generating text stream with OpenAI: {e}')
            raise


# Register the OpenAI provider
LLMProviderFactory.register_provider('openai', OpenAIProvider)
