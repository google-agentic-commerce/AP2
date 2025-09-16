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

"""A baseline A2A AgentExecutor utilized by multiple agents.

This provides some custom abilities over the default AgentExecutor:
1. It accepts a list of supported A2A extensions. Upon receiving a message, it
activates any requested extensions that the agent supports.
2. It leverages the FunctionCallResolver to identify the appropriate tool to
use for a given request, and invoking it to complete the task.
3. It logs key events in the Agent Payments Protocol to the watch log. See
watch_log.py for more details.
"""

import abc
import logging
import os
from typing import Any, Callable, Tuple
import uuid

from a2a.server.agent_execution.agent_executor import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import Part
from a2a.types import Task
from a2a.types import TextPart
from a2a.utils import message
from google import genai
from ap2.types.mandate import PAYMENT_MANDATE_DATA_KEY
from ap2.types.mandate import PaymentMandate
from common import message_utils
from common import system_utils
from common import watch_log
from common.a2a_extension_utils import EXTENSION_URI
from common.function_call_resolver import FunctionCallResolver
from common.validation import validate_payment_mandate_signature

DataPartContent = dict[str, Any]
Tool = Callable[[list[DataPartContent], TaskUpdater, Task | None], Any]

class BaseServerExecutor(AgentExecutor, abc.ABC):
  """A baseline A2A AgentExecutor to be utilized by agents."""

  def __init__(
      self,
      supported_extensions: list[dict[str, Any]] | None,
      tools: list[Tool],
      system_prompt: str = "You are a helpful assistant.",
  ):
    """Initialization.

    Args:
      supported_extensions: Extensions the agent declares that it supports.
      tools: Tools supported by the agent.
      system_prompt: Helps steer the model when choosing tools.
    """
    if supported_extensions is not None:
      self._supported_extension_uris = {ext.uri for ext in supported_extensions}
    else:
      self._supported_extension_uris = set()
    system_utils.check_google_api_key()
    self._client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    self._tools = tools
    self._tool_resolver = FunctionCallResolver(
        self._client, self._tools, system_prompt
    )
    super().__init__()

  async def execute(
      self, context: RequestContext, event_queue: EventQueue
  ) -> None:
    """Execute the agent's logic for a given request context.

    Args:
      context: The request context containing the message, task ID, etc.
      event_queue: The queue to publish events to.
    """
    watch_log.log_a2a_request_extensions(context)

    text_parts, data_parts = self._parse_request(context)
    watch_log.log_a2a_message_parts(text_parts, data_parts)

    self._handle_extensions(context)

    if EXTENSION_URI in context.call_context.activated_extensions:
      payment_mandate = message_utils.find_data_part(
          PAYMENT_MANDATE_DATA_KEY, data_parts
      )
      if payment_mandate is not None:
        validate_payment_mandate_signature(
            PaymentMandate.model_validate(payment_mandate)
        )
    else:
      raise ValueError(
          "Payment extension not activated."
          f" {context.call_context.activated_extensions}"
      )

    updater = TaskUpdater(
        event_queue,
        task_id=context.task_id or str(uuid.uuid4()),
        context_id=context.context_id or str(uuid.uuid4()),
    )

    logging.info(
        "Server working on (context_id, task_id): (%s, %s)",
        updater.context_id,
        updater.task_id,
    )
    await self._handle_request(
        text_parts,
        data_parts,
        updater,
        context.current_task,
    )

  async def cancel(self, context: RequestContext) -> None:
    """Request the agent to cancel an ongoing task."""
    pass

  async def _handle_request(
      self,
      text_parts: list[str],
      data_parts: list[dict[str, Any]],
      updater: TaskUpdater,
      current_task: Task | None,
  ) -> None:
    """Receives a parsed request and dispatches to the appropriate tool.

    Args:
      text_parts: A list of text parts from the request.
      data_parts: A list of data parts from the request.
      updater: The TaskUpdater instance for updating the task.
      current_task: The current Task, if available.
    """
    try:
      prompt = (text_parts[0] if text_parts else "").strip()
      tool_name = self._tool_resolver.determine_tool_to_use(prompt)
      logging.info("Using tool: %s", tool_name)

      matching_tools = list(
          filter(lambda tool: tool.__name__ == tool_name, self._tools)
      )
      if len(matching_tools) != 1:
        raise ValueError(
            f"Expected 1 tool matching {tool_name}, got {len(matching_tools)}"
        )
      callable_tool = matching_tools[0]
      await callable_tool(data_parts, updater, current_task)

    except Exception as e:  # pylint: disable=broad-exception-caught
      error_message = updater.new_agent_message(
          parts=[Part(root=TextPart(text=f"An error occurred: {e}"))]
      )
      await updater.failed(message=error_message)

  def _parse_request(
      self, context: RequestContext
  ) -> Tuple[list[str], list[dict[str, Any]]]:
    """Parses the request and returns the text and data parts.

    Args:
      context: The A2A RequestContext

    Returns:
      A tuple containing the contents of TextPart and DataPart objects.
    """
    parts = context.message.parts if context.message else []
    text_parts = message.get_text_parts(parts)
    data_parts = message.get_data_parts(parts)
    return text_parts, data_parts

  def _handle_extensions(self, context: RequestContext) -> None:
    """Activates any requested extensions that the agent supports.

    Args:
      context: The A2A RequestContext
    """
    requested_uris = context.requested_extensions
    activated_uris = requested_uris.intersection(self._supported_extension_uris)
    for uri in activated_uris:
      context.add_activated_extension(uri)
