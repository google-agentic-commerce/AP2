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

"""Clients used by the shopping agent to communicate with remote agents.

Clients request activation of the Agent Payments Protocol extension by including
the X-A2A-Extensions header in each HTTP request.

This registry serves as the initial allowlist of remote agents that the shopping
agent trusts.
"""

from common.a2a_extension_utils import EXTENSION_URI
from common.payment_remote_a2a_client import PaymentRemoteA2aClient


credentials_provider_client = PaymentRemoteA2aClient(
    name="credentials_provider",
    base_url="http://localhost:8002/a2a/credentials_provider",
    required_extensions={
        EXTENSION_URI,
    },
)


merchant_agent_client = PaymentRemoteA2aClient(
    name="merchant_agent",
    base_url="http://localhost:8001/a2a/merchant_agent",
    required_extensions={
        EXTENSION_URI,
    },
)
