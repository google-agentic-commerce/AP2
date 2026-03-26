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

"""MiniMax LLM client using the OpenAI-compatible API.

Provides two helpers consumed by the AP2 agent infrastructure:

* :func:`minimax_resolve_function_call` – picks a tool via function-calling.
* :func:`minimax_generate_json` – generates structured JSON output.

Both talk to ``https://api.minimax.io/v1`` and require the
``MINIMAX_API_KEY`` environment variable.
"""

import json
import logging
import os
import re
from typing import Any, Callable

from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import Task
from openai import OpenAI

MINIMAX_BASE_URL = "https://api.minimax.io/v1"

DataPartContent = dict[str, Any]
Tool = Callable[[list[DataPartContent], TaskUpdater, Task | None], Any]


def _get_client() -> OpenAI:
    """Create an OpenAI client pointed at MiniMax."""
    api_key = os.environ.get("MINIMAX_API_KEY", "")
    if not api_key:
        raise ValueError(
            "MINIMAX_API_KEY environment variable is required when "
            "LLM_PROVIDER is set to 'minimax'."
        )
    return OpenAI(api_key=api_key, base_url=MINIMAX_BASE_URL)


def _strip_think_tags(text: str) -> str:
    """Remove <think>…</think> blocks that MiniMax M2 models may emit."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences (```json ... ```) from LLM output."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def minimax_resolve_function_call(
    model: str,
    tools: list[Tool],
    system_prompt: str,
    user_prompt: str,
) -> str:
    """Use MiniMax to pick the best tool for *user_prompt*.

    Converts the Python callables in *tools* into OpenAI-style
    function-calling tool definitions and forces the model to call one.

    Returns the name of the chosen tool, or ``"Unknown"`` on failure.
    """
    client = _get_client()

    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": tool.__name__,
                "description": tool.__doc__ or "",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        }
        for tool in tools
    ]

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        tools=openai_tools,
        tool_choice="required",
        temperature=0.1,
    )

    logging.debug("\nMiniMax Determine Tool Response: %s\n", response)

    choice = response.choices[0] if response.choices else None
    if choice and choice.message and choice.message.tool_calls:
        return choice.message.tool_calls[0].function.name

    return "Unknown"


def minimax_generate_json(
    model: str,
    prompt: str,
    system_prompt: str = "",
) -> Any:
    """Ask MiniMax for a JSON response and return the parsed object.

    Uses ``response_format={"type": "json_object"}`` to ensure valid JSON.
    """
    client = _get_client()

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    raw = response.choices[0].message.content or "{}"
    raw = _strip_think_tags(raw)
    raw = _strip_code_fences(raw)
    return json.loads(raw)
