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

"""Utility methods related to creating the watch.log file.

The watch.log file is a log file meant to be watched in parallel with running a
scenario.  It will contain all the requests and responses to/from the agent
that are sent to/from the client, so engineers can see what is happening
between the servers in real time.
"""

import logging
from typing import Any

from a2a.server.agent_execution.context import RequestContext

from ap2.types.mandate import CART_MANDATE_DATA_KEY
from ap2.types.mandate import INTENT_MANDATE_DATA_KEY
from ap2.types.mandate import PAYMENT_MANDATE_DATA_KEY

_logger = logging.getLogger(__name__)


def create_file_handler() -> logging.FileHandler:
  """Creates a file handler to the logger for watch.log.

  Returns:
      A logging.FileHandler instance configured for 'watch.log'.
  """
  file_handler = logging.FileHandler(".logs/watch.log")
  file_handler.setLevel(logging.INFO)
  file_handler.setFormatter(logging.Formatter("%(message)s"))
  return file_handler


def log_a2a_message_parts(
    text_parts: list[str], data_parts: list[dict[str, Any]]
):
  _load_logger()

  """Logs the A2A message parts to the watch.log file."""
  _log_request_instuctions(text_parts)
  _log_mandates(data_parts)
  _log_extra_data(data_parts)


def log_a2a_request_extensions(context: RequestContext) -> None:
  """Logs the A2A extensions activated to the watch.log file."""

  if not context.call_context.activated_extensions:
    return

  _logger.info("\n")
  _logger.info("[A2A Extensions Activated in the Request]")

  for extension in context.call_context.requested_extensions:
    _logger.info(extension)


def _load_logger():
  if not _logger.handlers:
    _logger.addHandler(create_file_handler())


def _log_request_instuctions(text_parts: list[str]) -> None:
  """Logs the request instructions from the text parts."""
  _logger.info("\n")
  _logger.info("[Request Instructions]")
  _logger.info(text_parts)


def _log_mandates(data_parts: list[dict[str, Any]]) -> None:
  """Extracts and logs mandates from the data parts."""

  for data_part in data_parts:
    for key, value in data_part.items():
      if key == CART_MANDATE_DATA_KEY:
        _logger.info("\n")
        _logger.info("[A Cart Mandate was in the request Data]")
        _logger.info(value)
      elif key == INTENT_MANDATE_DATA_KEY:
        _logger.info("\n")
        _logger.info("[An Intent Mandate was in the request Data]")
        _logger.info(value)
      elif key == PAYMENT_MANDATE_DATA_KEY:
        _logger.info("\n")
        _logger.info("[A Payment Mandate was in the request Data]")
        _logger.info(value)


def _log_extra_data(data_parts: list[dict[str, Any]]) -> None:
  """Extracts and logs extra data from the data parts."""
  for data_part in data_parts:
    for key, value in data_part.items():
      if (
          key == CART_MANDATE_DATA_KEY
          or key == INTENT_MANDATE_DATA_KEY
          or key == PAYMENT_MANDATE_DATA_KEY
      ):
        continue

      _logger.info("\n")
      _logger.info("[Data Part: %s] ", key)
      _logger.info(value)
