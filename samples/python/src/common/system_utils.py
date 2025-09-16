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

"""Helper functions related to the system."""

import os
from pathlib import Path


def check_google_api_key() -> bool:
  """Checks if the GOOGLE_API_KEY environment variable is set."""

  assert (
      "GOOGLE_API_KEY" in os.environ
  ), "The environment variable 'GOOGLE_API_KEY' is not set."

  assert os.getenv(
      "GOOGLE_API_KEY"
  ), "The environment variable 'GOOGLE_API_KEY' is empty."


DEBUG_MODE_INSTRUCTIONS = """
    This is really important! If the agent or user asks you to be verbose or if debug_mode is True, do the following:
      1. If this is the the start of a new task, explain who you are, what you are going to do, what tools you use, and what agents you delegate to.
      2. During the task, provide regular status updates on what you are doing, what you have done so far, and what you plan to do next.
      3. If you are delegating to another agent, ask the agent or tool to also be verbose.
      4. If at any point in the task you send or receive data, show the data in a clear, formatted way. Do not summarize it in english. Simple format the JSON objects.
      5. Step 4 is so important that I'm going to repeat it:
        a. If at any point in the task you create, send or receive data, show the data in a clear, formatted way. Do not summarize it in english. Simple format the JSON objects.
"""
