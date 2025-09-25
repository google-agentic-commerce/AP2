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

"""Entrypoint for the flight merchant agent."""

from collections.abc import Sequence

from absl import app
from roles.merchant_agent_flights.agent_executor import FlightMerchantExecutor
from common import server

AGENT_PORT = 8004  # Use a new port to avoid conflicts


def main(argv: Sequence[str]) -> None:
    agent_card = server.load_local_agent_card(__file__)
    server.run_agent_blocking(
        port=AGENT_PORT,
        agent_card=agent_card,
        executor=FlightMerchantExecutor(agent_card.capabilities.extensions),
        rpc_url="/a2a/flights_merchant",
    )


if __name__ == "__main__":
    app.run(main)
