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

"""A server for hosting an A2A agent using Starlette and Uvicorn.

To provide a clear demonstration of the Agent Payments Protocol A2A extension,
this server operates without the Google ADK. Instead, it directly uses an
AgentCard and AgentExecutor to launch a Uvicorn server.
"""

import json
import logging
import os

from a2a.server.agent_execution.simple_request_context_builder import SimpleRequestContextBuilder
from a2a.server.apps.jsonrpc.starlette_app import A2AStarletteApplication
from a2a.server.request_handlers.default_request_handler import DefaultRequestHandler
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.types import AgentCard
from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response
import uvicorn

from . import watch_log
from .base_server_executor import BaseServerExecutor

# Constant for the A2A extensions header
A2A_EXTENSIONS_HEADER = "X-A2A-Extensions"


def load_local_agent_card(file_path: str) -> AgentCard:
  """Loads the AgentCard from the specified file path.

  Args:
      file_path: The directory where the agent.json file is located.

  Returns:
      The loaded AgentCard instance.
  """
  card_path = os.path.join(os.path.dirname(file_path), "agent.json")
  with open(card_path, "r", encoding="utf-8") as f:
    data = json.load(f)
  return AgentCard.model_validate(data)


def run_agent_blocking(
    port: int,
    agent_card: AgentCard,
    *,
    executor: BaseServerExecutor,
    rpc_url: str,
) -> None:
  """Launches a Uvicorn server for an agent and block the current thread.

  Args:
      port: TCP port to bind to.
      agent_card: The AgentCard object describing the agent.
      executor: The AgentExecutor that processes A2A requests.
      rpc_url: The base URL path at which to mount the JSON-RPC handler.
  """

  # Add a file handler to the logger for watch.log.
  logger = logging.getLogger(__name__)
  logger.addHandler(watch_log.create_file_handler())

  # Build the Starlette app and add middlewares.
  app = _build_starlette_app(agent_card, executor=executor, rpc_url=rpc_url)
  _add_middlewares(app, logger)

  # Start the server.
  logger.info("%s listening on http://localhost:%d", agent_card.name, port)
  uvicorn.run(
      app, host="127.0.0.1", port=port, log_level="info", timeout_keep_alive=120
  )


def _create_watch_log_handler() -> logging.FileHandler:
  """Create a file handler for watch.log logger.

  watch.log is a log file meant to be watched in parallel with running a
  scenario.  It will contain all the requests and responses to/from the agent
  that are sent to/from the client, so engineers can see what is happening
  between the servers in real time.

  Returns:
      A logging.FileHandler instance configured for 'watch.log'.
  """
  file_handler = logging.FileHandler(".logs/watch.log")
  file_handler.setLevel(logging.INFO)
  file_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
  return file_handler


class _LoggingMiddleware(BaseHTTPMiddleware):
  """Intercepts and logs incoming request and response details."""

  def __init__(self, *args, logger: logging.Logger, **kwargs):
    self._logger = logger
    super().__init__(*args, **kwargs)

  async def dispatch(self, request: Request, call_next) -> Response:
    self._logger.info("\n\n\n")
    self._logger.info("---------- New Agent Request Received---------")

    # Log the request method and URL.
    self._logger.info("%s %s", request.method, request.url)

    # Log the request body if it's present.
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 0:
      request_body = await request.json()
    else:
      request_body = "<empty>"

    self._logger.info("\n")
    self._logger.info("[Request Body]")
    self._logger.info("%s", request_body)

    # If the extension header is present, log a notice.
    extension_header = request.headers.get(A2A_EXTENSIONS_HEADER)
    if extension_header:
      self._logger.info(
          "\n[Extension Header]\n%s: %s", A2A_EXTENSIONS_HEADER, extension_header
      )

    response = await call_next(request)

    # Ensure the response has a body to read.
    if response.body_iterator:
      body = b""

      # Read the entire response body.
      # All responses are UTF-8 encoded JSON, so this should always succeed.
      async for chunk in response.body_iterator:
        body += chunk

      try:
        response_body_json = body.decode("utf-8")
      except UnicodeDecodeError:
        self._logger.warning("Failed to decode response body as UTF-8.")
        response_body_json = body

      self._logger.info("\n")
      self._logger.info("[Response Body]")
      self._logger.info("%s", response_body_json)

      return Response(
          content=body,
          status_code=response.status_code,
          media_type=response.media_type,
          headers=response.headers,
      )
    else:
      self._logger.info("\n")
      self._logger.info("[Response Body]")
      self._logger.info("<empty>")
      return response


def _build_starlette_app(
    agent_card: AgentCard, *, executor, rpc_url
) -> A2AStarletteApplication:
  """Create and return a ready-to-serve Starlette ASGI application.

  Args:
      agent_card: The AgentCard object describing the agent.
      executor: The AgentExecutor that processes A2A requests.
      rpc_url: The base URL path at which to mount the JSON-RPC handler.

  Returns:
      An instance of A2AStarletteApplication.

  Raises:
      ValueError: If executor is None.
  """
  if executor is None:
    raise ValueError("executor must be supplied")

  handler = DefaultRequestHandler(
      agent_executor=executor,
      task_store=InMemoryTaskStore(),
      request_context_builder=SimpleRequestContextBuilder(),
  )

  app = A2AStarletteApplication(
      agent_card=agent_card, http_handler=handler
  ).build(
      rpc_url=rpc_url, agent_card_url=f"{rpc_url}{AGENT_CARD_WELL_KNOWN_PATH}"
  )
  return app


def _add_middlewares(app, logger: logging.Logger) -> None:
  """Add middlewares to the Starlette app."""
  app.add_middleware(
      CORSMiddleware,
      allow_origins=[
          "http://localhost:8000",
          "http://127.0.0.1:8000",
          "http://0.0.0.0:8000",
          "http://localhost:8081",
          "http://127.0.0.1:8081",
          "http://0.0.0.0:8081",
          "http://localhost:8082",
          "http://127.0.0.1:8082",
          "http://0.0.0.0:8082",
          "http://localhost:8083",
          "http://127.0.0.1:8083",
          "http://0.0.0.0:8083",
          "http://localhost:8080",
          "http://127.0.0.1:8080",
          "http://0.0.0.0:8080",
      ],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  app.add_middleware(_LoggingMiddleware, logger=logger)
  return app
