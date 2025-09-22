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

"""A custom CLI runner for the human-not-present flight booking demo."""
import asyncio
import logging
import subprocess
import sys
import time
from pathlib import Path

# Add the project's `src` directory to the Python path.
project_root = Path(__file__).resolve().parents[5]
src_path = project_root / "samples" / "python" / "src"
sys.path.insert(0, str(src_path))

from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService, Session
from google.genai.types import Content, Part

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from roles.shopping_agent_flights.agent import flight_shopping_agent

logging.basicConfig(level=logging.WARNING)


async def run_demo(runner: Runner, session: Session):
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

    # The agent's instruction prompt will generate the first greeting.
    # We start the conversation by sending an initial empty message.
    invocation = runner.run_async(
        user_id=session.user_id,
        session_id=session.id,
        new_message=Content(role="user", parts=[Part(text="Hi there")]),
    )

    # This loop will now handle the entire conversation flow.
    while True:
        try:
            # Get the next set of events from the agent
            events = [event async for event in invocation]

            # Process and display final responses from the events
            final_text = ""
            for event in events:
                # Use the correct API to check if this is a user-facing message
                if event.is_final_response():
                    # Safely access the text content
                    if event.content and event.content.parts and event.content.parts[0].text:
                        final_text += event.content.parts[0].text.strip() + " "
                if event.error_message:
                    console.print(f"[bold red]AGENT ERROR: {event.error_message}[/bold red]")

            if final_text:
                console.print(f"\n[bold green]{session.app_name}:[/bold green] {final_text.strip()}")

            # After displaying the agent's response, prompt for the next user input
            user_input = Prompt.ask("\n[bold]You[/bold]")
            if user_input.lower() in ["exit", "quit"]:
                break

            # Start the next invocation with the new user message
            invocation = runner.run_async(
                user_id=session.user_id,
                session_id=session.id,
                new_message=Content(role="user", parts=[Part(text=user_input)]),
            )

        except StopAsyncIteration:
            console.print("\n[bold yellow]Conversation ended.[/bold yellow]")
            break


def main():
    """Main function to start the server and run the demo."""
    merchant_log_path = project_root / ".logs" / "flight_merchant.log"
    merchant_log_path.parent.mkdir(exist_ok=True)

    merchant_command = [
        "uv", "run", "--package", "ap2-samples",
        "python", "-m", "roles.merchant_agent_flights",
    ]

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
            process = subprocess.Popen(
                merchant_command,
                cwd=project_root,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
        print(
            "--> Started Flight Merchant Agent in the background (log:"
            " .logs/flight_merchant.log)"
        )
        time.sleep(3)

        session = asyncio.run(session_service.create_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        ))

        asyncio.run(run_demo(runner, session))
    finally:
        if process:
            print("\n--> Shutting down background merchant agent...")
            process.terminate()
            process.wait()
            print("--> Cleanup complete.")


if __name__ == "__main__":
    main()
