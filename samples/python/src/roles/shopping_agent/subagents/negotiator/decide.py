# Copyright 2026 AP2-Haggle contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0

"""Shopper-side per-round decision: accept, counter, or walk away.

Wraps the shared Claude negotiation engine with a shopper-specific system
prompt and context rendering. The returned decision is consumed by the
`negotiate_with_merchant` tool in shopping_agent/tools.py to drive the A2A
loop with the merchant.
"""

from __future__ import annotations

import json
from typing import Any

from ap2.types.negotiation import NegotiationConstraints
from ap2.types.negotiation import Offer
from common import claude_negotiator

_SYSTEM_PROMPT = """
You are the shopper-side negotiator in a real-time agent-to-agent bargain.
You represent the buyer. Your job is to examine the merchant's latest offer
against the buyer's private constraints and decide whether to accept it,
counter with a different offer, or walk away.

Principles:
1. NEVER accept an offer that violates any `required_terms`. These are hard
   filters, not trade-off axes.
2. If the offer fits inside `walk_away_terms` and is close to or better
   than `target_terms`, prefer accepting — buyers lose when they let a
   good deal slip chasing perfection.
3. If the offer is outside `walk_away_terms` and the merchant has not moved
   materially over the last two rounds, prefer walking away over burning
   remaining rounds.
4. When you counter, size the concession so that convergence is plausible
   within the remaining rounds. Bigger splits waste rounds; tiny splits
   waste the merchant's patience.
5. Deploy concrete arguments — competitor prices, loyalty history, bulk
   intent, flexible delivery, urgency — rather than pure bargaining tone.
   Arguments with structured payloads (e.g. a competitor URL + price) are
   more credible than rhetoric.
6. Respect the declared `style`: cooperative negotiators share information
   and split differences; competitive negotiators anchor harder and
   concede less; collaborative negotiators explore multi-axis trades
   (e.g. longer warranty instead of lower price).
"""


def decide_shopper_move(
    constraints: NegotiationConstraints,
    offer_history: list[Offer],
    latest_merchant_offer: Offer,
    *,
    round_number: int,
) -> dict[str, Any]:
  """Returns the shopper's decision for this round.

  Decision shape (from `claude_negotiator.decide_next_move`):
    {"action": "accept"|"counter"|"walk",
     "rationale": str,
     "terms": dict,
     "arguments": list[dict]}
  """
  context_summary = _render_shopper_context(
      constraints=constraints,
      round_number=round_number,
      max_rounds=constraints.max_rounds,
  )
  return claude_negotiator.decide_next_move(
      system_prompt=_SYSTEM_PROMPT,
      context_summary=context_summary,
      offer_history=[o.model_dump() for o in offer_history],
      latest_offer=latest_merchant_offer.model_dump(),
  )


def _render_shopper_context(
    *,
    constraints: NegotiationConstraints,
    round_number: int,
    max_rounds: int,
) -> str:
  """Renders the shopper's private context for the current round."""
  rounds_remaining = max_rounds - round_number
  parts = [
      f"You are currently in round {round_number} of up to {max_rounds} "
      f"({rounds_remaining} remaining).",
      f"Negotiation style: {constraints.style}.",
      f"Deadline: {constraints.deadline}.",
      "",
      "target_terms (ideal outcome): "
      f"{_json(constraints.target_terms)}",
      "walk_away_terms (worst acceptable): "
      f"{_json(constraints.walk_away_terms)}",
      "required_terms (hard filters, MUST be satisfied): "
      f"{_json(constraints.required_terms)}",
  ]
  if constraints.strategy_hint:
    parts.append("")
    parts.append(f"strategy_hint: {constraints.strategy_hint}")
  return "\n".join(parts)


def _json(value: Any) -> str:
  if value is None:
    return "(unset)"
  try:
    return json.dumps(value, sort_keys=True)
  except (TypeError, ValueError):
    return str(value)
