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

"""Wrapper for the A2A client."""

import httpx
import logging
import uuid

from a2a import types as a2a_types
from a2a.client.card_resolver import A2ACardResolver
from a2a.client.client import Client
from a2a.client.client import ClientConfig
from a2a.client.client_factory import ClientFactory
from a2a.client.client_task_manager import ClientTaskManager
from a2a.extensions.common import HTTP_EXTENSION_HEADER

DEFAULT_TIMEOUT = 600.0


class PaymentRemoteA2aClient():
  """Wrapper for the A2A client.

  Always assumes the AgentCard is at base_url + {AGENT_CARD_WELL_KNOWN_PATH}.

  Provides convenience for establishing connection and for sending messages.
  """

  def __init__(
      self,
      name: str,
      base_url: str,
      required_extensions: set[str] | None = None,
  ):
    """Initializes the PaymentRemoteA2aClient.

    Args:
      name: The name of the agent.
      base_url: The base URL where the remote agent is hosted.
      required_extensions: A set of extension URIs that the client requires.
    """

    self._httpx_client = httpx.AsyncClient(
        timeout=httpx.Timeout(timeout=DEFAULT_TIMEOUT)
    )
    self._a2a_client_factory = ClientFactory(
        ClientConfig(
            httpx_client=self._httpx_client,
        )
    )
    self._name = name
    self._base_url = base_url
    self._agent_card = None
    self._client_required_extensions = required_extensions or set()

  async def get_agent_card(self) -> a2a_types.AgentCard:
    """Get agent card."""
    if self._agent_card is None:
      resolver = A2ACardResolver(
          httpx_client=self._httpx_client,
          base_url=self._base_url,
      )
      self._agent_card = await resolver.get_agent_card()
    return self._agent_card

  async def send_a2a_message(
      self, message: a2a_types.Message
  ) -> a2a_types.Task:
    """Retrieves the A2A client, sends the message, and returns the event."""
    my_a2a_client: Client = await self._get_a2a_client()

    task_manager = ClientTaskManager()

    async for event in my_a2a_client.send_message(message):
      # Tasks are returned in tuples (aka ClientEvent). The first element is the
      # Task, the second element is the UpdateEvent.
      if isinstance(event, tuple):
        event = event[0]
      await task_manager.process(event)

    task = task_manager.get_task()
    if task is None:
      raise RuntimeError(f"No response from {self._name}")
    logging.info(
        "Response received from %s for (context_id, task_id): (%s, %s)",
        self._name,
        task.context_id,
        task.id,
    )
    return task

  async def _get_a2a_client(self) -> Client:
    """Get A2A client."""
    agent_card = await self.get_agent_card()
    self._httpx_client.headers[HTTP_EXTENSION_HEADER] = ", ".join(
        self._client_required_extensions
    )
    return self._a2a_client_factory.create(agent_card)

  def _create_agent_message(
      self,
      message: str,
  ) -> a2a_types.Message:
    """Get message."""
    return a2a_types.Message(
        message_id=uuid.uuid4().hex,
        parts=[a2a_types.Part(root=a2a_types.TextPart(text=str(message)))],
        role=a2a_types.Role.agent,
    )
