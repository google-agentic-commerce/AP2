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

"""This module provides a FunctionCallResolver class.

The FunctionCallResolver uses a LLM to determine which tool to
use based on the instructions provided.
"""

import logging
from typing import Any, Callable

from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import Task
from google import genai
from google.genai import types


DataPartContent = dict[str, Any]
Tool = Callable[[list[DataPartContent], TaskUpdater, Task | None], Any]


class FunctionCallResolver:
  """Resolves resolves a natural language prompt to the name of a tool."""

  def __init__(
      self,
      llm_client: genai.Client,
      tools: list[Tool],
      instructions: str = "You are a helpful assistant.",
  ):
    """Initialization.

    Args:
      llm_client: The LLM client.
      tools: The list of tools that a request can be resolved to.
      instructions: The instructions to guide the LLM.
    """
    self._client = llm_client
    function_declarations = [
        types.FunctionDeclaration(
            name=tool.__name__, description=tool.__doc__
        )
        for tool in tools
    ]
    self._config = types.GenerateContentConfig(
        system_instruction=instructions,
        tools=[types.Tool(function_declarations=function_declarations)],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True
        ),
        # Force the model to call 'any' function, instead of chatting.
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode="ANY")
        ),
    )

  def determine_tool_to_use(self, prompt: str) -> str:
    """Determines which tool to use based on a user's prompt.

    Uses a LLM to analyze the user's prompt and decide which of the available
    tools (functions) is the most appropriate to handle the request.

    Args:
        prompt: The user's request as a string.

    Returns:
        The name of the tool function that the model has determined should be
        called. If no suitable tool is found, it returns "Unknown".
    """

    response = self._client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=self._config,
    )

    logging.debug("\nDetermine Tool Response: %s\n", response)

    if (
        response.candidates
        and response.candidates[0].content
        and response.candidates[0].content.parts
    ):
      for part in response.candidates[0].content.parts:
        if part.function_call:
          return part.function_call.name

    return "Unknown"
