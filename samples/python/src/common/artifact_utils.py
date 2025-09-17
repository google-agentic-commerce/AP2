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

"""Helper functions for working with A2A Artifact objects."""

from typing import Any, TypeVar

from a2a.types import Artifact
from a2a.utils import message as message_utils
from pydantic import BaseModel

T = TypeVar("T")


def find_canonical_objects(
    artifacts: list[Artifact], data_key: str, model: BaseModel
) -> list[BaseModel]:
  """Finds all canonical objects of the given type in the artifacts.

  Args:
    artifacts: a list of the artifacts to be searched.
    data_key: The key of the DataPart to search for.
    model: The model of the canonical object to search for.

  Returns:
    A list of canonical objects of the given type in the artifacts.
  """
  canonical_objects = []
  for artifact in artifacts:
    for part in artifact.parts:
      if hasattr(part.root, "data") and data_key in part.root.data:
        canonical_objects.append(model.model_validate(part.root.data[data_key]))
  return canonical_objects


def get_first_data_part(artifacts: list[Artifact]) -> dict[str, Any]:
  """Returns the first DataPart encountered in all the given artifacts.

  Args:
    artifacts: The artifacts to be searched for a DataPart.

  Returns:
    The data contents within the first found DataPart.
  """
  data_parts = [
      message_utils.get_data_parts(artifact.parts) for artifact in artifacts
  ]
  for data_part in data_parts:
    for item in data_part:
      return item
  return {}


def only(list_: list[T]) -> T:
  """Returns the only element in a list.

  Args:
    list_: The list expected to contain exactly one element.

  Raises:
    ValueError: if the list is empty or has more than one element.
  """
  if not list_:
    raise ValueError("List is empty.")
  if len(list_) > 1:
    raise ValueError("List has more than one element.")
  return list_[0]
