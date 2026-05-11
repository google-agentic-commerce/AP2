"""Shopping Agent: Sub-agent hierarchy.

The hierarchy consists of consent_agent → monitoring_agent → purchase_agent.
Root agent is consent_agent; it transfers to monitoring_agent after mandate
approval. monitoring_agent transfers to purchase_agent when price constraint is
met.

Each sub-agent gets its own McpToolset instance (separate stdio connection)
per ADK best practice — sharing a single instance across agents causes
connection conflicts (see google/adk-python#712).
"""

import json
import logging
import os
import sys

from pathlib import Path
from typing import Any

from google.adk.agents import Agent
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.adk.tools.tool_context import ToolContext
from mcp import StdioServerParameters

from shopping_agent.mandate_tools import (
  assemble_and_sign_mandates_tool,
  check_constraints_against_mandate,
  create_checkout_presentation,
  create_payment_presentation,
  verify_checkout_receipt,
)


_AGENT_DIR = Path(__file__).resolve().parent
_AP2_ROOT = _AGENT_DIR.parent.parent
_LOG_DIR = Path(os.environ.get("LOGS_DIR", _AP2_ROOT / ".logs"))
_LOG_FILE = _LOG_DIR / "shopping-agent.log"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

_shopping_logger = logging.getLogger("shopping_agent")
_shopping_logger.setLevel(logging.DEBUG)
if not _shopping_logger.handlers:
  _fh = logging.FileHandler(_LOG_FILE, mode="w", encoding="utf-8")
  _fh.setFormatter(
      logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
  )
  _shopping_logger.addHandler(_fh)

_FLOW = os.environ.get("FLOW", "x402")

_MERCHANT_SERVER = _AP2_ROOT / "merchant_agent_mcp" / "server.py"
if _FLOW == "x402":
  _CREDENTIAL_SERVER = _AP2_ROOT / "x402_credentials_provider_mcp" / "server.py"
  _MERCHANT_PAYMENT_PROCESSOR_SERVER = _AP2_ROOT / "x402_psp_mcp" / "server.py"
else:
  _CREDENTIAL_SERVER = _AP2_ROOT / "credentials_provider_mcp" / "server.py"
  _MERCHANT_PAYMENT_PROCESSOR_SERVER = (
      _AP2_ROOT / "merchant_payment_processor_mcp" / "server.py"
  )
_PROMPTS_DIR = _AGENT_DIR / "prompts"


def _make_mcp_toolset(server_path: Path, tool_filter=None) -> McpToolset:
  """Create an MCP toolset that runs a server via ``uv``.

  Each agent needs its own McpToolset instance — sharing one across
  agents causes stdio connection conflicts (google/adk-python#712).

  Args:
      server_path: The path to the MCP server script.
      tool_filter: Optional filter to select specific tools.

  Returns:
      An McpToolset instance configured to run the specified server.
  """
  env = os.environ.copy()
  if "LOGS_DIR" not in env:
    env["LOGS_DIR"] = str(_AP2_ROOT / ".logs")
  if "TEMP_DB_DIR" not in env:
    env["TEMP_DB_DIR"] = str(_AP2_ROOT / ".temp-db")

  return McpToolset(
      connection_params=StdioConnectionParams(
          server_params=StdioServerParameters(
              command=sys.executable,
              args=[server_path.name],
              cwd=str(server_path.parent),
              env=env,
          ),
          timeout=60.0,
      ),
      tool_filter=tool_filter,
  )


def _error_escalation_callback(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    tool_response: dict[str, Any],
) -> dict[str, str] | None:
  """Intercept MCP tool errors and reformat them so the LLM reliably emits.

  a structured error artifact instead of mangling or ignoring the error.

  Args:
      tool: The tool that was executed.
      args: The arguments passed to the tool.
      tool_context: The context of the tool execution.
      tool_response: The response from the tool.

  Returns:
      A dictionary containing error details and an action message if an error
      is present in `tool_response`, otherwise None.
  """
  if isinstance(tool_response, dict) and "error" in tool_response:
    code = tool_response["error"]
    msg = tool_response.get("message", str(tool_response))
    tool_name = getattr(tool, "name", str(tool))
    _shopping_logger.warning(
        "Tool %s returned error: %s – %s",
        tool_name,
        code,
        msg,
    )
    error_json = json.dumps(
        {"type": "error", "error": code, "message": msg},
        ensure_ascii=True,
    )
    return {
        "error": code,
        "message": msg,
        "action_required": (
            "STOP all processing. Emit EXACTLY this JSON as your"
            f" complete response, nothing else: {error_json}"
        ),
    }
  return None


def reset_temp_db() -> dict[str, str]:
  """Cleans up mandate files in the .temp-db directory.

  Use this tool when you want to start or restart the flow with a clean state.
  It preserves server keys.
  """
  try:
    temp_db_dir = Path(os.environ.get("TEMP_DB_DIR", _AP2_ROOT / ".temp-db"))
    if temp_db_dir.exists():
      prefixes = ["chk_", "open_chk_", "pay_", "open_pay_"]
      count = 0
      for item in temp_db_dir.iterdir():
        if item.is_file():
          if any(item.name.startswith(prefix) for prefix in prefixes):
            item.unlink()
            count += 1
      return {
          "status": "ok",
          "message": f"Removed {count} mandate files from {temp_db_dir}",
      }
    return {"status": "ok", "message": f"No temp DB found at {temp_db_dir}"}
  except Exception as e:
    return {"error": "reset_failed", "message": str(e)}


_CONSENT_INSTRUCTION = (_PROMPTS_DIR / "consent_agent.md").read_text()
_MONITORING_INSTRUCTION = (_PROMPTS_DIR / "monitoring_agent.md").read_text()
_PURCHASE_INSTRUCTION = (_PROMPTS_DIR / "purchase_agent.md").read_text()

_model = os.environ.get("AGENT_MODEL", "gemini-3.1-flash-lite-preview")

purchase_agent = Agent(
    name="purchase_agent",
    model=_model,
    description=(
        "Executes the autonomous purchase flow when price and availability"
        " satisfy the open mandates: assemble_cart, create_checkout, closed"
        " mandates, issue_payment_credential, complete_checkout,"
        " settle_with_psp."
    ),
    instruction=_PURCHASE_INSTRUCTION,
    output_key="purchase_result",
    tools=[
        check_constraints_against_mandate,
        create_checkout_presentation,
        create_payment_presentation,
        verify_checkout_receipt,
        _make_mcp_toolset(_MERCHANT_SERVER),
        _make_mcp_toolset(_CREDENTIAL_SERVER),
        _make_mcp_toolset(
            _MERCHANT_PAYMENT_PROCESSOR_SERVER,
            tool_filter=lambda tool, ctx=None: tool.name != "initiate_payment",
        ),
    ],
    after_tool_callback=_error_escalation_callback,
)

monitoring_agent = Agent(
    name="monitoring_agent",
    model=_model,
    description=(
        "Holds open mandates and monitors item price and availability via"
        " check_product. Transfers to purchase_agent when price is within the"
        " mandate and the merchant reports the item as available."
    ),
    instruction=_MONITORING_INSTRUCTION,
    output_key="monitoring_result",
    tools=[
        check_constraints_against_mandate,
        _make_mcp_toolset(_MERCHANT_SERVER),
    ],
    sub_agents=[purchase_agent],
    after_tool_callback=_error_escalation_callback,
)

consent_agent = Agent(
    name="consent_agent",
    model=_model,
    description=(
        "Handles drop/budget dialogue, product search, item selection, and"
        " open-mandate signing. Transfers to monitoring_agent after"
        " mandate_approved or on 'Check price now'."
    ),
    instruction=_CONSENT_INSTRUCTION,
    output_key="consent_result",
    tools=[
        reset_temp_db,
        assemble_and_sign_mandates_tool,
        _make_mcp_toolset(_MERCHANT_SERVER),
    ],
    sub_agents=[monitoring_agent],
    after_tool_callback=_error_escalation_callback,
)

root_agent = consent_agent
