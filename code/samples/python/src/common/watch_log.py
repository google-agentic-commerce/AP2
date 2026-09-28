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

The watch.log file records request structure for tracing a scenario. A2A
text and data values can carry payment credentials, mandates, or risk data,
so only part and field counts are logged.
"""

import logging

from typing import Any

from a2a.server.agent_execution.context import RequestContext


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
  """Log structural A2A diagnostics without any part values."""
  _load_logger()
  _logger.info(
      "[A2A Request] text_parts=%d data_parts=%d",
      len(text_parts),
      len(data_parts),
  )
  for index, data_part in enumerate(data_parts):
    # Keys from the wire are untrusted too: a malicious key can itself be a
    # secret. Only their count is safe to log for unknown data shapes.
    _logger.info("[Data Part %d] fields=%d", index, len(data_part))


def log_a2a_request_extensions(context: RequestContext) -> None:
  """Logs the A2A extensions activated to the watch.log file."""
  if not context.call_context.activated_extensions:
    return

  _logger.info("\n")
  _logger.info("[A2A Extensions Activated in the Request]")

  _logger.info(
      "Requested extensions: %d",
      len(context.call_context.requested_extensions),
  )


def _load_logger():
  if not _logger.handlers:
    _logger.addHandler(create_file_handler())
