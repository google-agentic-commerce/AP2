"""LLM Provider abstraction layer for AP2.

This module provides a provider-agnostic interface for interacting with different
LLM services, similar to the Vercel AI SDK's provider system.
"""

import json
import os

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class LLMConfig:
    """Configuration for LLM provider settings."""

    provider: str
    model: str
    api_key: str | None = None
    base_url: str | None = None
    max_retries: int = 3
    timeout: int = 60
    temperature: float = 0.7
    max_tokens: int | None = None
    additional_params: dict[str, Any] | None = None

    @classmethod
    def from_env(cls, provider: str = 'google') -> 'LLMConfig':
        """Create LLMConfig from environment variables."""
        # Provider-specific default models
        default_models = {
            'google': 'gemini-2.5-flash',
            'openai': 'gpt-4',
            'anthropic': 'claude-3-5-sonnet-20241022',
        }

        api_key = os.getenv(f'{provider.upper()}_API_KEY')
        base_url = os.getenv(f'{provider.upper()}_BASE_URL')
        model = os.getenv(f'{provider.upper()}_MODEL', default_models.get(provider, 'gpt-4'))

        return cls(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            max_retries=int(os.getenv(f'{provider.upper()}_MAX_RETRIES', '3')),
            timeout=int(os.getenv(f'{provider.upper()}_TIMEOUT', '60')),
            temperature=float(
                os.getenv(f'{provider.upper()}_TEMPERATURE', '0.7')
            ),
            max_tokens=int(val) if (val := os.getenv(f"{provider.upper()}_MAX_TOKENS")) else None,
        )

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> 'LLMConfig':
        """Create LLMConfig from a dictionary."""
        return cls(**config_dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert LLMConfig to dictionary."""
        return {
            'provider': self.provider,
            'model': self.model,
            'api_key': self.api_key,
            'base_url': self.base_url,
            'max_retries': self.max_retries,
            'timeout': self.timeout,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'additional_params': self.additional_params,
        }


@dataclass
class LLMResponse:
    """Response from an LLM provider."""

    content: str
    usage: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    finish_reason: str | None = None

    def __str__(self) -> str:
        return self.content


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate text using the LLM provider."""

    @abstractmethod
    async def generate_text_stream(
        self,
        prompt: str,
        system_instruction: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> AsyncGenerator[LLMResponse, None]:
        """Generate text using streaming."""

    @abstractmethod
    def get_model_name(self) -> str:
        """Get the model name for this provider."""

    @abstractmethod
    def validate_config(self) -> bool:
        """Validate the provider configuration."""


class LLMProviderFactory:
    """Factory for creating LLM providers."""

    _providers = {}

    @classmethod
    def register_provider(
        cls, provider_name: str, provider_class: type
    ) -> None:
        """Register a provider class."""
        cls._providers[provider_name] = provider_class

    @classmethod
    def create_provider(cls, config: LLMConfig) -> LLMProvider:
        """Create a provider instance from config."""
        provider_class = cls._providers.get(config.provider)
        if not provider_class:
            raise ValueError(f'Unknown provider: {config.provider}')

        return provider_class(config)

    @classmethod
    def get_available_providers(cls) -> list[str]:
        """Get list of available provider names."""
        return list(cls._providers.keys())


def load_config_from_file(config_path: str) -> LLMConfig:
    """Load LLM configuration from a JSON file."""
    with open(config_path) as f:
        config_dict = json.load(f)
    return LLMConfig.from_dict(config_dict)


def save_config_to_file(config: LLMConfig, config_path: str) -> None:
    """Save LLM configuration to a JSON file."""
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, 'w') as f:
        json.dump(config.to_dict(), f, indent=2)
