"""Provider-agnostic LLM agent implementation.

This module provides an updated version of the RetryingLlmAgent that uses
the provider abstraction layer instead of hardcoded model names.
"""

import dataclasses
import logging

from collections.abc import AsyncGenerator
from typing import Any, override

from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.llm_agent import LlmAgent
from google.adk.events.event import Event

from ap2 import LLMConfig, LLMProvider, LLMProviderFactory


class ProviderAgnosticLlmAgent(LlmAgent):
    """An LLM agent that uses the provider abstraction layer."""

    def __init__(
        self,
        provider_config: LLMConfig | None = None,
        provider: LLMProvider | None = None,
        max_retries: int = 1,
        **kwargs,
    ):
        """Initialize the provider-agnostic LLM agent.

        Args:
            provider_config: Configuration for the LLM provider
            provider: Pre-configured LLM provider instance
            max_retries: Maximum number of retries on failure
            **kwargs: Additional arguments passed to parent LlmAgent
        """
        super().__init__(**kwargs)
        self._max_retries = max_retries

        if provider:
            self._provider = provider
        elif provider_config:
            self._provider = LLMProviderFactory.create_provider(provider_config)
        else:
            # Default to Google Gemini for backward compatibility
            default_config = LLMConfig.from_env(provider='google')
            self._provider = LLMProviderFactory.create_provider(default_config)

        # Validate provider configuration
        if not self._provider.validate_config():
            raise ValueError(
                f'Invalid configuration for provider: {self._provider.config.provider}'
            )

    async def _generate_text_with_provider(
        self,
        prompt: str,
        system_instruction: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        use_streaming: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Generate text using the configured provider."""
        try:
            if use_streaming:
                async for response in self._provider.generate_text_stream(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    tools=tools,
                ):
                    yield response.content
            else:
                response = await self._provider.generate_text(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    tools=tools,
                )
                yield response.content

        except Exception as e:
            logging.error(
                f'Error generating text with provider {self._provider.config.provider}: {e}'
            )
            raise

    async def _retry_async(
        self,
        ctx: InvocationContext,
        retries_left: int = 0,
        use_streaming: bool = False,
    ) -> AsyncGenerator[Event, None]:
        """Retry logic with provider abstraction."""
        if retries_left <= 0:
            yield Event(
                author=ctx.agent.name,
                invocation_id=ctx.invocation_id,
                error_message=(
                    f'Maximum retries exhausted. The remote {self._provider.config.provider} '
                    'server failed to respond. Please try again later.'
                ),
            )
        else:
            try:
                # Get the prompt and other parameters from the invocation context
                # Process conversation history to build prompt
                prompt = self._build_prompt_from_history(ctx)
                system_instruction = getattr(ctx.agent, 'instruction', None)

                async for content in self._generate_text_with_provider(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    use_streaming=use_streaming,
                ):
                    yield Event(
                        author=ctx.agent.name,
                        invocation_id=ctx.invocation_id,
                        content=content,
                    )

            except Exception as e:
                yield Event(
                    author=ctx.agent.name,
                    invocation_id=ctx.invocation_id,
                    error_message=f'{self._provider.config.provider.title()} server error. Retrying...',
                    custom_metadata={'error': str(e)},
                )
                async for event in self._retry_async(
                    ctx, retries_left - 1, use_streaming
                ):
                    yield event

    def _build_prompt_from_history(self, ctx: InvocationContext) -> str:
        """Build a prompt string from the conversation history."""
        if hasattr(ctx, 'history') and ctx.history:
            # Process conversation history into a prompt
            # This is a simplified implementation - adapt based on your needs
            messages = []
            for message in ctx.history:
                if hasattr(message, 'author') and hasattr(message, 'content'):
                    role = (
                        'assistant'
                        if message.author == ctx.agent.name
                        else 'user'
                    )
                    messages.append(f'{role}: {message.content}')
            return '\n'.join(messages)
        else:
            # Fallback to old behavior if history is not available
            return getattr(ctx, 'prompt', '')

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Run the agent with provider abstraction."""
        async for event in self._retry_async(
            ctx, retries_left=self._max_retries
        ):
            yield event


class RetryingLlmAgent(ProviderAgnosticLlmAgent):
    """Backward-compatible version of RetryingLlmAgent with provider support.

    This class maintains the same interface as the original RetryingLlmAgent
    but uses the provider abstraction layer internally.
    """

    def __init__(
        self,
        model: str = 'gemini-2.5-flash',
        provider: str = 'google',
        max_retries: int = 1,
        **kwargs,
    ):
        """Initialize the retrying LLM agent.

        Args:
            model: The model name to use (for backward compatibility)
            provider: The provider name (google, openai, anthropic)
            max_retries: Maximum number of retries on failure
            **kwargs: Additional arguments passed to parent classes
        """
        # Create provider config for backward compatibility
        config_fields = {f.name for f in dataclasses.fields(LLMConfig)}
        config_kwargs = {k: v for k, v in kwargs.items() if k in config_fields}
        agent_kwargs = {
            k: v for k, v in kwargs.items() if k not in config_fields
        }
        config = LLMConfig(provider=provider, model=model, **config_kwargs)

        super().__init__(
            provider_config=config, max_retries=max_retries, **agent_kwargs
        )
