"""Google Gemini provider implementation."""

import asyncio
import logging
import os
from typing import TYPE_CHECKING

from collections.abc import AsyncGenerator
from typing import Any


if TYPE_CHECKING:
    from google import genai
    from google.genai import types

try:
    from google import genai
    from google.genai import types

    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    # Create a dummy class for type checking when google-genai is not available
    class genai:
        class Client:
            pass
    
    class types:
        class Tool:
            def __init__(self, function_declarations=None):
                self.function_declarations = function_declarations or []
        
        class FunctionDeclaration:
            def __init__(self, name='', description='', parameters=None):
                self.name = name
                self.description = description
                self.parameters = parameters or {}
        
        class GenerateContentConfig:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

from ap2 import LLMConfig, LLMProvider, LLMProviderFactory, LLMResponse


class GoogleGeminiProvider(LLMProvider):
    """Google Gemini LLM provider."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        """Get or create the Gemini client."""
        if self._client is None:
            client_config = {}
            if self.config.api_key:
                client_config['api_key'] = self.config.api_key
            if self.config.base_url:
                # Note: Google GenAI client doesn't support base_url directly
                # This would need custom implementation for custom endpoints
                pass

            self._client = genai.Client(**client_config)
        return self._client

    def get_model_name(self) -> str:
        """Get the model name for this provider."""
        return self.config.model

    def validate_config(self) -> bool:
        """Validate the provider configuration."""
        if not GOOGLE_GENAI_AVAILABLE:
            logging.error(
                'google-genai package is not available. Install with: pip install google-genai'
            )
            return False
        if not self.config.api_key and not os.getenv('GOOGLE_API_KEY'):
            logging.warning('Google API key not found in config or environment')
            return False
        return True

    def _convert_tools_to_gemini_format(
        self, tools: list[dict[str, Any]] | None
    ) -> list[types.Tool] | None:
        """Convert tools to Gemini format."""
        if not tools:
            return None

        function_declarations = []
        for tool in tools:
            # Convert from common format to Gemini format
            if 'function' in tool:
                func_info = tool['function']
                function_declarations.append(
                    types.FunctionDeclaration(
                        name=func_info.get('name', ''),
                        description=func_info.get('description', ''),
                        parameters=func_info.get('parameters', {}),
                    )
                )

        if function_declarations:
            return [types.Tool(function_declarations=function_declarations)]
        return None

    def _create_generate_config(
        self,
        system_instruction: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> types.GenerateContentConfig:
        """Create Gemini generate content config."""
        config_kwargs = {}

        if system_instruction:
            config_kwargs['system_instruction'] = system_instruction

        gemini_tools = self._convert_tools_to_gemini_format(tools)
        if gemini_tools:
            config_kwargs['tools'] = gemini_tools
            # Disable automatic function calling to maintain compatibility
            config_kwargs['automatic_function_calling'] = (
                types.AutomaticFunctionCallingConfig(disable=True)
            )
            # Force function calling mode
            config_kwargs['tool_config'] = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode='ANY')
            )

        # Apply temperature if specified
        if self.config.temperature != 0.7:  # Default is 0.7
            config_kwargs['temperature'] = self.config.temperature

        return types.GenerateContentConfig(**config_kwargs)

    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate text using Google Gemini."""
        try:
            client = self._get_client()
            config = self._create_generate_config(system_instruction, tools)

            # Run the synchronous call in a thread pool to avoid blocking
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model=self.config.model, contents=prompt, config=config
                ),
            )

            # Extract content from response
            content = ''
            if response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                        content += part.text

            # Extract usage information if available
            usage = None
            if hasattr(response, 'usage_metadata'):
                usage = {
                    'prompt_tokens': getattr(
                        response.usage_metadata, 'prompt_token_count', None
                    ),
                    'completion_tokens': getattr(
                        response.usage_metadata, 'candidates_token_count', None
                    ),
                    'total_tokens': getattr(
                        response.usage_metadata, 'total_token_count', None
                    ),
                }

            return LLMResponse(
                content=content,
                usage=usage,
                finish_reason=getattr(
                    response.candidates[0], 'finish_reason', None
                )
                if response.candidates
                else None,
            )

        except Exception as e:
            logging.error(f'Error generating text with Gemini: {e}')
            raise

    async def generate_text_stream(
        self,
        prompt: str,
        system_instruction: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> AsyncGenerator[LLMResponse, None]:
        """Generate text using streaming with Google Gemini."""
        try:
            client = self._get_client()
            config = self._create_generate_config(system_instruction, tools)

            # For streaming, we need to use generate_content_stream
            loop = asyncio.get_running_loop()

            # Create a generator that yields response chunks
            async def _stream_response():
                try:
                    response_stream = await loop.run_in_executor(
                        None,
                        lambda: client.models.generate_content_stream(
                            model=self.config.model,
                            contents=prompt,
                            config=config,
                        ),
                    )

                    for chunk in response_stream:
                        if chunk.candidates and chunk.candidates[0].content:
                            for part in chunk.candidates[0].content.parts:
                                if hasattr(part, 'text') and part.text:
                                    yield LLMResponse(
                                        content=part.text,
                                        metadata={'chunk': True},
                                    )

                except Exception as e:
                    logging.error(f'Error in Gemini streaming: {e}')
                    raise

            async for response in _stream_response():
                yield response

        except Exception as e:
            logging.error(f'Error generating text stream with Gemini: {e}')
            raise


# Register the Google provider
LLMProviderFactory.register_provider('google', GoogleGeminiProvider)
