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

"""AP2 - Agent Payments Protocol

This package provides a provider-agnostic interface for interacting with different
LLM services, similar to the Vercel AI SDK's provider system.
"""

# Re-export core classes for easier importing
from .providers import LLMConfig, LLMProvider, LLMProviderFactory, LLMResponse

__all__ = [
    'LLMConfig',
    'LLMProvider',
    'LLMProviderFactory',
    'LLMResponse',
]
