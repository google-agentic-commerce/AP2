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

"""Centralized LLM provider configuration.

Reads the LLM_PROVIDER and LLM_MODEL environment variables to determine which
LLM backend to use.  Supported providers:

* ``google``  – Google GenAI / Gemini (default)
* ``minimax`` – MiniMax via OpenAI-compatible API
"""

import enum
import os


class LLMProvider(enum.Enum):
    """Supported LLM provider backends."""

    GOOGLE = "google"
    MINIMAX = "minimax"


# Default model names per provider.
_DEFAULT_MODELS: dict[LLMProvider, str] = {
    LLMProvider.GOOGLE: "gemini-2.5-flash",
    LLMProvider.MINIMAX: "MiniMax-M2.7",
}


def get_provider() -> LLMProvider:
    """Return the configured LLM provider.

    Reads the ``LLM_PROVIDER`` environment variable (case-insensitive).
    Falls back to ``LLMProvider.GOOGLE`` when unset.
    """
    raw = os.environ.get("LLM_PROVIDER", "google").strip().lower()
    try:
        return LLMProvider(raw)
    except ValueError:
        raise ValueError(
            f"Unsupported LLM_PROVIDER '{raw}'. "
            f"Supported values: {[p.value for p in LLMProvider]}"
        )


def get_model() -> str:
    """Return the configured model name.

    Uses ``LLM_MODEL`` when set, otherwise falls back to the default model
    for the active provider.
    """
    explicit = os.environ.get("LLM_MODEL", "").strip()
    if explicit:
        return explicit
    return _DEFAULT_MODELS[get_provider()]
