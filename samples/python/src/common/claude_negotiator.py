# Copyright 2026 AP2-Haggle contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0

"""Claude-powered per-round negotiation engine, shared by both sides.

The shopper's `negotiator` subagent and the merchant's `seller_strategist`
subagent both call `decide_next_move()` with side-specific context. The
engine uses Claude tool-use with a fixed JSON schema that mirrors
`ap2.types.negotiation.Offer`, which gives schema-valid structured output
without having to parse free-text JSON.
"""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone
import json
import logging
import os
from typing import Any
from typing import Literal

import anthropic

Decision = Literal["accept", "counter", "walk"]

_DEFAULT_MODEL = os.environ.get("HAGGLE_CLAUDE_MODEL", "claude-sonnet-4-6")
_DEFAULT_MAX_TOKENS = 2048

# Claude tool schema — a single "propose_move" tool that returns an action
# plus, when the action is "counter", a structured next offer. The shape
# mirrors `ap2.types.negotiation.Offer` closely enough that the caller can
# hydrate Pydantic types without additional parsing.
_PROPOSE_MOVE_TOOL = {
    "name": "propose_move",
    "description": (
        "Decide how to respond to the latest offer in the negotiation. "
        "Choose exactly one action: accept the current offer on the table, "
        "counter with a new offer, or walk away."
    ),
    "input_schema": {
        "type": "object",
        "required": ["action", "rationale"],
        "properties": {
            "action": {
                "type": "string",
                "enum": ["accept", "counter", "walk"],
                "description": (
                    "The move this agent is making in this round. "
                    "`accept` locks in the latest received offer. "
                    "`counter` supplies a new offer with different terms. "
                    "`walk` abandons the negotiation."
                ),
            },
            "rationale": {
                "type": "string",
                "description": (
                    "Short natural-language explanation of the reasoning "
                    "behind this move — used in the NegotiationOutcome summary."
                ),
            },
            "terms": {
                "type": "object",
                "description": (
                    "Required when action == 'counter'. The proposed "
                    "negotiable terms: price (number), currency (string), "
                    "and any other axis (delivery_days, warranty_months, "
                    "payment_terms_net_days, etc.). Open key set."
                ),
                "additionalProperties": True,
            },
            "arguments": {
                "type": "array",
                "description": (
                    "Optional structured persuasion payloads accompanying a "
                    "counter or accept. Each has a type tag, a summary, and "
                    "optional structured payload."
                ),
                "items": {
                    "type": "object",
                    "required": ["type", "summary"],
                    "properties": {
                        "type": {"type": "string"},
                        "summary": {"type": "string"},
                        "payload": {
                            "type": "object",
                            "additionalProperties": True,
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                    },
                },
            },
        },
    },
}


def decide_next_move(
    *,
    system_prompt: str,
    context_summary: str,
    offer_history: list[dict[str, Any]],
    latest_offer: dict[str, Any] | None,
    model: str = _DEFAULT_MODEL,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
) -> dict[str, Any]:
  """Runs one round of negotiation reasoning via Claude tool-use.

  Args:
    system_prompt: Side-specific system prompt (shopper vs. merchant).
      Should describe the role, the private constraints/floors, and any
      strategy guidance.
    context_summary: A freshly rendered summary of the current round's
      private context — e.g. the shopper's constraints dict, or the
      merchant's cost floor + inventory position.
    offer_history: Ordered list of prior offers in this negotiation, as
      dicts (from `Offer.model_dump()`). May be empty.
    latest_offer: The most recent incoming offer the side must respond to.
      `None` when the merchant is generating an opening offer.
    model: Anthropic model name.
    max_tokens: Hard cap on response length.

  Returns:
    A dict with keys:
      action: "accept" | "counter" | "walk"
      rationale: str
      terms: dict (present when action in {"counter", "accept"})
      arguments: list[dict] (may be empty)

    On tool-call failure or invalid output, returns an "walk" decision with
    the error as rationale so the caller can cleanly abandon.
  """
  client = anthropic.Anthropic()

  user_content = _render_user_turn(
      context_summary=context_summary,
      offer_history=offer_history,
      latest_offer=latest_offer,
  )

  try:
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        tools=[_PROPOSE_MOVE_TOOL],
        tool_choice={"type": "tool", "name": "propose_move"},
        messages=[{"role": "user", "content": user_content}],
    )
  except anthropic.APIError as exc:
    logging.exception("Claude negotiation call failed")
    return {
        "action": "walk",
        "rationale": f"Claude API error: {exc}",
        "terms": {},
        "arguments": [],
    }

  for block in response.content:
    if block.type == "tool_use" and block.name == "propose_move":
      decision = dict(block.input)
      decision.setdefault("terms", {})
      decision.setdefault("arguments", [])
      decision.setdefault("rationale", "")
      return decision

  logging.warning(
      "Claude returned no tool_use block; response=%s", response.content
  )
  return {
      "action": "walk",
      "rationale": "Model did not emit a propose_move tool call.",
      "terms": {},
      "arguments": [],
  }


def _render_user_turn(
    *,
    context_summary: str,
    offer_history: list[dict[str, Any]],
    latest_offer: dict[str, Any] | None,
) -> str:
  """Renders the per-round user turn Claude sees."""
  lines: list[str] = []
  lines.append("## Current private context")
  lines.append(context_summary.strip())
  lines.append("")

  lines.append("## Offer history (oldest first)")
  if not offer_history:
    lines.append("(none — this is the opening move)")
  else:
    for idx, offer in enumerate(offer_history):
      lines.append(f"### Round {offer.get('round_number', idx)} "
                   f"— {offer.get('proposer_role', '?')}")
      lines.append(f"terms: {_json(offer.get('terms', {}))}")
      args = offer.get("arguments", [])
      if args:
        lines.append("arguments:")
        for arg in args:
          lines.append(
              f"  - [{arg.get('type')}] {arg.get('summary')}"
          )
      lines.append("")

  lines.append("## Latest offer to respond to")
  if latest_offer is None:
    lines.append(
        "(none — you are producing the opening offer. Pick `counter`.)"
    )
  else:
    lines.append(
        f"proposer: {latest_offer.get('proposer_role')} "
        f"(round {latest_offer.get('round_number')})"
    )
    lines.append(f"terms: {_json(latest_offer.get('terms', {}))}")
    if latest_offer.get("arguments"):
      lines.append("arguments they deployed:")
      for arg in latest_offer["arguments"]:
        lines.append(f"  - [{arg.get('type')}] {arg.get('summary')}")

  lines.append("")
  lines.append(
      "Decide your move by calling the `propose_move` tool. Pick `accept` "
      "only if the latest offer meets your goals. Pick `walk` only if "
      "further rounds are hopeless. Otherwise `counter` with concrete new "
      "terms and at least one argument."
  )
  return "\n".join(lines)


def _json(value: Any) -> str:
  """Compact JSON rendering for inclusion in the model's user turn."""
  try:
    return json.dumps(value, sort_keys=True, separators=(",", ": "))
  except (TypeError, ValueError):
    return str(value)


def default_offer_expiry_iso(seconds: int = 90) -> str:
  """Returns a short-lived ISO 8601 expiry for a fresh Offer."""
  return (
      datetime.now(timezone.utc) + timedelta(seconds=seconds)
  ).isoformat()
