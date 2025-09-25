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

"""A2A Agent Executor for the flight merchant agent."""

from typing import Any

from . import tools
from common.base_server_executor import BaseServerExecutor


class FlightMerchantExecutor(BaseServerExecutor):
    """AgentExecutor for the flight merchant agent."""

    _system_prompt = """
    You are a merchant agent responsible for selling flights.
    Your only job is to receive purchase requests and validate them.
    Always use the 'process_purchase_request' tool.
    """

    def __init__(self, supported_extensions: list[dict[str, Any]] = None):
        agent_tools = [
            tools.process_purchase_request,
        ]
        super().__init__(supported_extensions, agent_tools, self._system_prompt)
