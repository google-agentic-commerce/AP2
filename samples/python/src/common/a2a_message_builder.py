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

"""A builder class for building an A2A Message object."""

from typing import Any, Self
import uuid

from a2a import types as a2a_types


class A2aMessageBuilder:
  """A builder class for building an A2A Message object."""

  def __init__(self):
    self._message = self._create_base_message()

  def add_text(self, text: str) -> Self:
    """Adds a TextPart to the Message.

    Args:
      text: The text to be added to the Message.

    Returns:
      The A2aMessageBuilder instance.
    """
    part = a2a_types.Part(root=a2a_types.TextPart(text=text))
    self._message.parts.append(part)
    return self

  def add_data(self, key: str, data: str | dict[str, Any]) -> Self:
    """Adds a new DataPart to the Message.

    If a key is provided, then the data part must be a string.  The DataPart's
    data dictionary will be set to { key: data}.

    If no key is provided, then the data part must be a dictionary.  The
    DataPart's data dictionary will be set to data.

    Args:
      key: The key to use for the data part.
      data: The data to accompany the key, if provided.  Otherwise, the data to
        be set within the DataPart object.

    Returns:
      The A2aMessageBuilder instance.
    """
    if not data:
      return self

    nested_data = data
    if key:
      nested_data = {key: data}

    part = a2a_types.Part(root=a2a_types.DataPart(data=nested_data))
    self._message.parts.append(part)
    return self

  def set_context_id(self, context_id: str) -> Self:
    """Sets the context id on the Message."""
    self._message.context_id = context_id
    return self

  def set_task_id(self, task_id: str) -> Self:
    """Sets the task id on the Message."""
    self._message.task_id = task_id
    return self

  def build(self) -> a2a_types.Message:
    """Returns the Message object that has been built."""
    return self._message

  def _create_base_message(self) -> a2a_types.Message:
    """Creates and returns a base Message object."""
    return a2a_types.Message(
        message_id=uuid.uuid4().hex,
        parts=[],
        role=a2a_types.Role.agent,
    )
