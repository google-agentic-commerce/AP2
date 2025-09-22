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

"""Tools for the flight merchant agent."""
from typing import Any

from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import Part, Task, TextPart
from ap2.types.mandate import INTENT_MANDATE_DATA_KEY
from common import message_utils
from rich.console import Console
from rich.panel import Panel



from roles.shopping_agent_flights.custom_mandate import StructuredIntentMandate


async def process_purchase_request(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
) -> None:
    """Processes a flight purchase by validating against structured mandate fields."""
    console = Console()
    console.print(
        "[bold blue]Flight Merchant:[/bold blue] Received purchase request..."
    )

    try:
        # --- CHANGE: Validate against our custom structured model ---
        mandate_data = message_utils.find_data_part(
            INTENT_MANDATE_DATA_KEY, data_parts
        )
        if not mandate_data:
            raise ValueError("IntentMandate not found in request.")
        structured_mandate = StructuredIntentMandate.model_validate(
            mandate_data
        )

        flight_details = message_utils.find_data_part(
            "flight_details", data_parts
        )
        if not flight_details:
            raise ValueError("Missing flight_details in request.")

        console.print(
            "[bold blue]Flight Merchant:[/bold blue] Verifying purchase"
            " against [yellow]structured[/yellow] IntentMandate fields..."
        )

        # 1. Validate destination
        mandate_destination = structured_mandate.constraints.destination
        if flight_details["destination"].lower() != mandate_destination.lower():
            msg = (
                "Purchase Blocked: Destination Mismatch. Agent tried to book a"
                f" flight to '{flight_details['destination']}', but the signed"
                " mandate only authorizes"
                f" '{mandate_destination}'."
            )
            panel = Panel(
                f"Attempted Destination: [red]{flight_details['destination']}[/red]\n"
                "Mandate Constraint: "
                f"[green]{mandate_destination}[/green]\n\n"
                "[bold]Result: VIOLATION DETECTED[/bold]",
                title="[red]Purchase Blocked by Merchant[/red]",
                border_style="red",
            )
            console.print(panel)
            await _fail_task(updater, msg)
            return

        # 2. Validate price
        mandate_max_price = structured_mandate.constraints.max_price
        if flight_details["price_gbp"] > mandate_max_price:
            msg = (
                "Purchase Blocked: Price Exceeds Limit. Agent tried to book for"
                f" {flight_details['price_gbp']} GBP, but the signed mandate"
                " only authorizes up to"
                f" {mandate_max_price} GBP."
            )
            panel = Panel(
                f"Attempted Price: [red]{flight_details['price_gbp']} GBP[/red]\n"
                "Mandate Constraint: "
                f"[green]<= {mandate_max_price} GBP[/green]\n\n"
                "[bold]Result: VIOLATION DETECTED[/bold]",
                title="[red]Purchase Blocked by Merchant[/red]",
                border_style="red",
            )
            console.print(panel)
            await _fail_task(updater, msg)
            return

        # If all checks pass
        success_msg = "Verification successful. Purchase approved!"
        panel = Panel(
            "All purchase details are consistent with the user's signed"
            " structured IntentMandate.",
            title="[green]✔ Purchase Approved by Merchant[/green]",
            border_style="green",
        )
        console.print(panel)
        success_message = updater.new_agent_message(
            parts=[Part(root=TextPart(text=success_msg))]
        )
        await updater.complete(message=success_message)

    except Exception as e:
        console.print(f"[bold red]ERROR:[/bold red] {e}")
        await _fail_task(updater, str(e))


async def _fail_task(updater: TaskUpdater, error_text: str) -> None:
    """Helper function to fail a task with a given error message."""
    error_message = updater.new_agent_message(
        parts=[Part(root=TextPart(text=error_text))]
    )
    await updater.failed(message=error_message)
