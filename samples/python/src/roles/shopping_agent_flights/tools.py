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

"""Tools for the flight shopping agent."""
from datetime import datetime, timedelta, timezone
from .custom_mandate import FlightConstraints, StructuredIntentMandate

from ap2.types.mandate import INTENT_MANDATE_DATA_KEY
from common.a2a_extension_utils import EXTENSION_URI
from common.a2a_message_builder import A2aMessageBuilder
from common.payment_remote_a2a_client import PaymentRemoteA2aClient
from google.adk.tools.tool_context import ToolContext
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm


def create_and_sign_intent_mandate(
    destination: str,
    max_price: int,
    currency: str,
    tool_context: ToolContext,
) -> str:
    """Creates a structured IntentMandate, asks the user to sign it, and stores it."""
    console = Console()
    console.print(
        "[bold green]Shopping Agent:[/bold green] Creating structured AP2"
        " IntentMandate..."
    )

    mandate = StructuredIntentMandate(
        natural_language_description=(
            f"A flight to {destination} for no more than {max_price}"
            f" {currency}."
        ),
        user_cart_confirmation_required=False,
        requires_refundability=True,
        intent_expiry=(
            datetime.now(timezone.utc) + timedelta(days=1)
        ).isoformat(),
        constraints=FlightConstraints(
            destination=destination, max_price=max_price, currency=currency
        ),
    )

    panel = Panel(
        mandate.model_dump_json(indent=2),
        title="[yellow]Generated Structured AP2 IntentMandate[/yellow]",
        border_style="yellow",
    )
    console.print(panel)

    if Confirm.ask(
        "[bold green]Shopping Agent:[/bold green] Please review the structured"
        " mandate. Do you approve and wish to sign it?"
    ):
        tool_context.state["signed_mandate"] = mandate
        console.print("[green]✔ Mandate signed successfully.[/green]")
        return "Mandate signed. The agent is now authorized to proceed."
    else:
        console.print("[red]✖ Mandate rejected. Aborting.[/red]")
        return "User rejected the mandate."


async def execute_purchase(
    destination: str, price_gbp: int, tool_context: ToolContext
) -> str:
    """Attempts to purchase a flight by sending the request to the merchant agent."""
    console = Console()
    console.print("\n----------------------------------------------------")
    console.print(
        "[bold green]Shopping Agent:[/bold green] Attempting to book a flight"
        f" to [cyan]{destination}[/cyan] for [cyan]{price_gbp} GBP[/cyan]..."
    )

    signed_mandate = tool_context.state.get("signed_mandate")
    if not signed_mandate:
        return "ERROR: Cannot execute purchase without a signed mandate."

    flight_merchant = PaymentRemoteA2aClient(
        name="flight_merchant",
        base_url="http://localhost:8004/a2a/flights_merchant",
        required_extensions={EXTENSION_URI},
    )

    message = (
        A2aMessageBuilder()
        .add_text("Process this flight purchase request.")
        .add_data(INTENT_MANDATE_DATA_KEY, signed_mandate.model_dump())
        .add_data(
            "flight_details",
            {"destination": destination, "price_gbp": price_gbp},
        )
        .build()
    )

    task = await flight_merchant.send_a2a_message(message)

    if task.status.state == "completed":
        return f"SUCCESS: {task.status.message.parts[0].root.text}"
    else:
        return f"FAILURE: {task.status.message.parts[0].root.text}"
