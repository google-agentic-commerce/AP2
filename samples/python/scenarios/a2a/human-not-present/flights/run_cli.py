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

# cspell:words PYTHONUNBUFFERED


"""A custom CLI runner for the human-not-present flight booking demo."""

import asyncio
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService, Session
from google.genai.types import Content, Part
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from roles.shopping_agent_flights.agent import flight_shopping_agent

# Configure logging after imports to satisfy linting rules
logging.basicConfig(level=logging.WARNING)
logging.getLogger("google_genai").setLevel(logging.ERROR)

# Resolve the repository root (so logs go to <repo>/.logs/)
PROJECT_ROOT = Path(__file__).resolve().parents[6]


async def run_demo(runner: Runner, session: Session) -> None:
    """Drives the conversational agent programmatically using the Runner."""
    console = Console()
    console.print(
        Panel(
            "Welcome to the AP2 Structured Mandate Demo!\nThis script drives a"
            " conversational ADK agent for a controlled CLI experience.",
            title="[bold magenta]Human-Not-Present Flight Demo[/bold magenta]",
            border_style="magenta",
        )
    )

    # Kick off the conversation with a simple greeting.
    invocation = runner.run_async(
        user_id=session.user_id,
        session_id=session.id,
        new_message=Content(role="user", parts=[Part(text="Hi there")]),
    )

    while True:
        try:
            # Collect streamed events from the agent
            events = [event async for event in invocation]

            # Aggregate any final, user-facing text
            final_text = ""
            for event in events:
                if event.is_final_response():
                    if (
                        event.content
                        and event.content.parts
                        and event.content.parts[0].text
                    ):
                        final_text += event.content.parts[0].text.strip() + " "
                if event.error_message:
                    console.print(
                        f"[bold red]AGENT ERROR: {event.error_message}[/bold red]"
                    )

            if final_text:
                console.print(
                    f"\n[bold green]{session.app_name}:[/bold green] {final_text.strip()}"
                )

            # Prompt for next user input
            user_input = Prompt.ask("\n[bold]You[/bold]")
            if user_input.lower() in ["exit", "quit"]:
                break

            # Continue the conversation
            invocation = runner.run_async(
                user_id=session.user_id,
                session_id=session.id,
                new_message=Content(role="user", parts=[Part(text=user_input)]),
            )

        except StopAsyncIteration:
            console.print("\n[bold yellow]Conversation ended.[/bold yellow]")
            break


def main() -> None:
    """Main function to start the merchant server and run the demo."""
    merchant_log_path = PROJECT_ROOT / ".logs" / "flight_merchant.log"
    merchant_log_path.parent.mkdir(parents=True, exist_ok=True)

    # Spawn using the same interpreter; force unbuffered output for live logs
    merchant_command = [sys.executable, "-m", "roles.merchant_agent_flights"]

    app_name = "flight_shopping_agent"
    user_id = "cli_user"
    session_id = "cli_session"
    session_service = InMemorySessionService()
    runner = Runner(
        agent=flight_shopping_agent,
        app_name=app_name,
        session_service=session_service,
    )

    process = None
    try:
        with open(merchant_log_path, "w") as log_file:
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            process = subprocess.Popen(
                merchant_command,
                cwd=PROJECT_ROOT,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=env,
            )

        print(
            f"--> Started Flight Merchant Agent in the background "
            f"(log: {merchant_log_path.resolve()})"
        )
        time.sleep(3)  # brief warm-up

        session = asyncio.run(
            session_service.create_session(
                app_name=app_name, user_id=user_id, session_id=session_id
            )
        )

        asyncio.run(run_demo(runner, session))

    finally:
        if process:
            print("\n--> Shutting down background merchant agent...")
            process.terminate()
            process.wait()
            print("--> Cleanup complete.")


if __name__ == "__main__":
    main()
