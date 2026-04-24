# Copyright 2026 AP2-Haggle contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0

"""Merchant-side seller strategist (Claude-powered).

Given an inbound negotiation round — either the opening IntentMandate from a
shopper or a counter-offer from the shopper — the strategist decides whether
to extend an offer, counter, or walk away. It reasons against the merchant's
private cost floor, inventory position and loyalty records.
"""

from __future__ import annotations

import json
from typing import Any

from ap2.types.mandate import IntentMandate
from ap2.types.negotiation import Offer
from common import claude_negotiator

_SYSTEM_PROMPT = """
You are the seller-side strategist in a real-time agent-to-agent bargain.
You represent the merchant. Your job is to convert the shopper's intent
and counter-offers into revenue while respecting a private cost floor.

Principles:
1. NEVER counter at a price below `cost_floor`. That's the hard boundary.
2. Opening offers should leave meaningful bargaining room — typically
   10–25% above cost_floor, depending on inventory pressure and the
   strategy_hint.
3. Respect the shopper's declared style. When they are cooperative, match
   concession speed. When they are competitive, hold anchors longer and
   deploy structured arguments (quality, SLA, cost_floor, bulk-tier
   pricing) instead of raw price cuts.
4. Trade across axes whenever possible: longer warranty, better delivery
   SLA, bundle discounts, extended payment terms, loyalty tier uplift.
   Multi-axis trades preserve margin.
5. Walk away when the shopper's ceiling is demonstrably below your cost
   floor and they have not moved in two or more rounds.
6. Accept when the shopper's latest offer is at or above your target
   margin band. Do not waste rounds grinding out the last dollar if the
   shopper's terms are already attractive.
"""


def decide_opening_offer(
    intent_mandate: IntentMandate,
    merchant_context: dict[str, Any],
    *,
    rounds_budget: int,
) -> dict[str, Any]:
  """Generates the merchant's opening offer (round 0)."""
  context_summary = _render_merchant_context(
      merchant_context=merchant_context,
      intent_description=intent_mandate.natural_language_description,
      round_number=0,
      max_rounds=rounds_budget,
  )
  return claude_negotiator.decide_next_move(
      system_prompt=_SYSTEM_PROMPT,
      context_summary=context_summary,
      offer_history=[],
      latest_offer=None,
  )


def decide_merchant_response(
    merchant_context: dict[str, Any],
    offer_history: list[Offer],
    latest_shopper_offer: Offer,
    *,
    round_number: int,
    rounds_budget: int,
) -> dict[str, Any]:
  """Generates the merchant's response to the shopper's counter-offer."""
  context_summary = _render_merchant_context(
      merchant_context=merchant_context,
      intent_description=merchant_context.get("intent_description", ""),
      round_number=round_number,
      max_rounds=rounds_budget,
  )
  return claude_negotiator.decide_next_move(
      system_prompt=_SYSTEM_PROMPT,
      context_summary=context_summary,
      offer_history=[o.model_dump() for o in offer_history],
      latest_offer=latest_shopper_offer.model_dump(),
  )


def _render_merchant_context(
    *,
    merchant_context: dict[str, Any],
    intent_description: str,
    round_number: int,
    max_rounds: int,
) -> str:
  """Renders the merchant's private context for the current round."""
  cost_floor = merchant_context.get("cost_floor")
  currency = merchant_context.get("currency", "USD")
  target_margin = merchant_context.get("target_margin_bps")
  inventory = merchant_context.get("inventory_status", "in_stock")
  loyalty = merchant_context.get("loyalty_tier", "unknown")
  competitors = merchant_context.get("known_competitor_prices", [])
  sku = merchant_context.get("sku", "(generic)")

  rounds_remaining = max_rounds - round_number
  parts = [
      f"Round {round_number} of up to {max_rounds} "
      f"({rounds_remaining} remaining).",
      f"Intent: {intent_description or '(provided as Offer only)'}",
      f"SKU / item: {sku}",
      f"Currency: {currency}",
      f"cost_floor: {_json(cost_floor)}",
  ]
  if target_margin is not None:
    parts.append(f"target_margin_bps: {target_margin}")
  parts.append(f"inventory_status: {inventory}")
  parts.append(f"shopper_loyalty_tier: {loyalty}")
  if competitors:
    parts.append(f"known_competitor_prices: {_json(competitors)}")
  strategy_hint = merchant_context.get("strategy_hint")
  if strategy_hint:
    parts.append(f"strategy_hint: {strategy_hint}")
  return "\n".join(parts)


def _json(value: Any) -> str:
  if value is None:
    return "(unset)"
  try:
    return json.dumps(value, sort_keys=True)
  except (TypeError, ValueError):
    return str(value)
