# Copyright 2026 AP2-Haggle contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0

"""Merchant-side negotiation workflow tool.

Registered on the MerchantAgentExecutor. Handles three kinds of inbound
A2A messages that make up a negotiation round:

1. Opening: IntentMandate + NegotiationConstraints → generate opening Offer.
2. Shopper counter-Offer (status="proposed") → accept / counter / walk.
3. Shopper accept-Offer (status="accepted") → seal as CartMandate and close.

The workflow stores per-contextId state in `storage`, so multi-round
negotiations survive across A2A request/response boundaries.
"""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone
import json
import logging
import os
from typing import Any
import uuid

from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import DataPart
from a2a.types import Part
from a2a.types import Task
from a2a.types import TextPart

from . import storage
from .sub_agents import seller_strategist_agent
from ap2.types.mandate import CART_MANDATE_DATA_KEY
from ap2.types.mandate import CartContents
from ap2.types.mandate import INTENT_MANDATE_DATA_KEY
from ap2.types.mandate import IntentMandate
from ap2.types.negotiation import NEGOTIATION_OUTCOME_DATA_KEY
from ap2.types.negotiation import OFFER_DATA_KEY
from ap2.types.negotiation import NegotiationConstraints
from ap2.types.negotiation import NegotiationOutcome
from ap2.types.negotiation import Offer
from ap2.types.payment_request import PaymentCurrencyAmount
from ap2.types.payment_request import PaymentDetailsInit
from ap2.types.payment_request import PaymentItem
from ap2.types.payment_request import PaymentMethodData
from ap2.types.payment_request import PaymentOptions
from ap2.types.payment_request import PaymentRequest
from common import haggle_utils
from common import message_utils


async def negotiate_workflow(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
) -> None:
  """Handles inbound negotiation A2A messages for this merchant.

  Dispatches on the shape of `data_parts`:
  - IntentMandate + NegotiationConstraints → opening Offer.
  - Shopper Offer (proposed) → accept/counter/walk by seller_strategist.
  - Shopper Offer (accepted) → seal as CartMandate and close.
  """
  context_id = updater.context_id
  incoming_offer = haggle_utils.extract_offer(data_parts)

  if incoming_offer is None:
    await _handle_opening(data_parts, updater, context_id)
    return

  if incoming_offer.status == "accepted":
    await _handle_shopper_acceptance(incoming_offer, updater, context_id)
    return

  if incoming_offer.proposer_role != "shopper":
    await _fail(
        updater,
        f"Unexpected proposer_role '{incoming_offer.proposer_role}' in "
        "merchant inbox — expected shopper.",
    )
    return

  await _handle_counter(incoming_offer, updater, context_id)


# --- Branch handlers ---


async def _handle_opening(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    context_id: str,
) -> None:
  """Generates and returns the merchant's round-0 opening Offer."""
  intent_mandate = message_utils.parse_canonical_object(
      INTENT_MANDATE_DATA_KEY, data_parts, IntentMandate
  )
  constraints = haggle_utils.extract_constraints(data_parts)
  if constraints is None:
    await _fail(
        updater,
        "Opening message missing NegotiationConstraints DataPart.",
    )
    return

  merchant_context = _derive_merchant_context(intent_mandate, constraints)
  merchant_context["intent_description"] = (
      intent_mandate.natural_language_description
  )
  merchant_context["max_rounds"] = constraints.max_rounds
  merchant_context["currency"] = (
      (constraints.target_terms or {}).get("currency") or "USD"
  )
  storage.set_merchant_context(context_id, merchant_context)

  decision = seller_strategist_agent.decide_opening_offer(
      intent_mandate, merchant_context, rounds_budget=constraints.max_rounds
  )
  logging.info("Opening decision: %s", decision)

  if decision.get("action") != "counter":
    # The strategist refused to open — treat as walk from the start.
    outcome = NegotiationOutcome(
        negotiation_id=context_id,
        status="abandoned",
        accepted_offer_id=None,
        final_cart_mandate=None,
        rounds_used=0,
        summary=(
            f"Merchant refused to open negotiation: "
            f"{decision.get('rationale', '(no rationale)')}"
        ),
    )
    await _emit_outcome(updater, outcome)
    return

  opening = _offer_from_decision(
      decision=decision,
      proposer_role="merchant",
      round_number=0,
      parent_offer_id=None,
      currency=merchant_context["currency"],
      item_label=_item_label_for(intent_mandate),
      prior_cart=None,
  )
  storage.append_offer(context_id, opening)

  risk_data = _collect_risk_data(context_id)
  await updater.add_artifact([
      Part(root=DataPart(data={OFFER_DATA_KEY: opening.model_dump()})),
      Part(root=DataPart(data={"risk_data": risk_data})),
  ])
  await updater.complete()


async def _handle_counter(
    shopper_offer: Offer,
    updater: TaskUpdater,
    context_id: str,
) -> None:
  """Lets the strategist accept/counter/walk on a shopper counter-offer."""
  merchant_context = storage.get_merchant_context(context_id)
  if merchant_context is None:
    await _fail(
        updater,
        "No merchant negotiation context for this contextId — the opening"
        " message was never observed.",
    )
    return

  history = storage.get_offer_history(context_id)
  storage.append_offer(context_id, shopper_offer)

  rounds_budget = merchant_context.get("max_rounds", 6)
  decision = seller_strategist_agent.decide_merchant_response(
      merchant_context,
      history,
      shopper_offer,
      round_number=shopper_offer.round_number + 1,
      rounds_budget=rounds_budget,
  )
  logging.info("Merchant round %d decision: %s",
               shopper_offer.round_number + 1, decision)

  action = decision.get("action")
  if action == "accept":
    cart_mandate = haggle_utils.seal_offer_as_cart_mandate(shopper_offer)
    storage.set_cart_mandate(shopper_offer.cart_contents.id, cart_mandate)
    outcome = NegotiationOutcome(
        negotiation_id=context_id,
        status="accepted",
        accepted_offer_id=shopper_offer.offer_id,
        final_cart_mandate=cart_mandate,
        rounds_used=shopper_offer.round_number,
        summary=decision.get("rationale")
        or "Merchant accepted the shopper's offer.",
    )
    risk_data = _collect_risk_data(context_id)
    await updater.add_artifact([
        Part(
            root=DataPart(
                data={NEGOTIATION_OUTCOME_DATA_KEY: outcome.model_dump()}
            )
        ),
        Part(
            root=DataPart(
                data={CART_MANDATE_DATA_KEY: cart_mandate.model_dump()}
            )
        ),
        Part(root=DataPart(data={"risk_data": risk_data})),
    ])
    await updater.complete()
    return

  if action == "walk":
    outcome = NegotiationOutcome(
        negotiation_id=context_id,
        status="abandoned",
        accepted_offer_id=None,
        final_cart_mandate=None,
        rounds_used=shopper_offer.round_number,
        summary=decision.get("rationale")
        or "Merchant abandoned negotiation.",
    )
    await _emit_outcome(updater, outcome)
    return

  # counter
  counter = _offer_from_decision(
      decision=decision,
      proposer_role="merchant",
      round_number=shopper_offer.round_number + 1,
      parent_offer_id=shopper_offer.offer_id,
      currency=merchant_context.get("currency", "USD"),
      item_label=merchant_context.get("item_label") or "Item",
      prior_cart=shopper_offer.cart_contents,
  )
  storage.append_offer(context_id, counter)
  await updater.add_artifact([
      Part(root=DataPart(data={OFFER_DATA_KEY: counter.model_dump()})),
  ])
  await updater.complete()


async def _handle_shopper_acceptance(
    shopper_offer: Offer,
    updater: TaskUpdater,
    context_id: str,
) -> None:
  """Seals an Offer that the shopper marked status='accepted'."""
  storage.append_offer(context_id, shopper_offer)
  cart_mandate = haggle_utils.seal_offer_as_cart_mandate(shopper_offer)
  storage.set_cart_mandate(shopper_offer.cart_contents.id, cart_mandate)
  outcome = NegotiationOutcome(
      negotiation_id=context_id,
      status="accepted",
      accepted_offer_id=shopper_offer.offer_id,
      final_cart_mandate=cart_mandate,
      rounds_used=shopper_offer.round_number,
      summary=(
          "Shopper accepted the merchant's offer; cart sealed with "
          "merchant authorization."
      ),
  )
  risk_data = _collect_risk_data(context_id)
  await updater.add_artifact([
      Part(
          root=DataPart(
              data={NEGOTIATION_OUTCOME_DATA_KEY: outcome.model_dump()}
          )
      ),
      Part(
          root=DataPart(
              data={CART_MANDATE_DATA_KEY: cart_mandate.model_dump()}
          )
      ),
      Part(root=DataPart(data={"risk_data": risk_data})),
  ])
  await updater.complete()


# --- Helpers ---


def _derive_merchant_context(
    intent_mandate: IntentMandate,
    constraints: NegotiationConstraints,
) -> dict[str, Any]:
  """Derives a private merchant context dict for the seller strategist.

  Production merchants would plug in real inventory, cost floors, and
  loyalty records here. The sample uses scenario config if present and
  falls back to simple heuristics derived from the shopper's constraints.
  """
  config = _load_scenario_config()
  cost_floor: float | None = None
  target_margin_bps = config.get("default_margin_bps", 2000)

  # Try to pick a matching inventory item by description keyword.
  description = intent_mandate.natural_language_description.lower()
  item_label = "Item"
  for sku, item in (config.get("items") or {}).items():
    keywords = [sku.lower()] + [k.lower() for k in item.get("keywords", [])]
    if any(keyword in description for keyword in keywords):
      cost_floor = float(item.get("cost_floor"))
      item_label = item.get("label", sku.title())
      break

  # Fallback: use the shopper's target_terms.price as a reference anchor.
  if cost_floor is None and constraints.target_terms:
    target_price = constraints.target_terms.get("price")
    if isinstance(target_price, (int, float)):
      # Merchant floor = 70% of shopper's target, giving room to haggle.
      cost_floor = round(float(target_price) * 0.7, 2)

  return {
      "cost_floor": cost_floor,
      "target_margin_bps": target_margin_bps,
      "inventory_status": "in_stock",
      "loyalty_tier": config.get("default_loyalty_tier", "unknown"),
      "known_competitor_prices": config.get("competitor_prices", []),
      "strategy_hint": config.get("merchant_strategy_hint"),
      "sku": item_label.lower().replace(" ", "_"),
      "item_label": item_label,
  }


def _item_label_for(intent_mandate: IntentMandate) -> str:
  """Derives a human-friendly line-item label from an intent description."""
  desc = intent_mandate.natural_language_description.strip()
  if len(desc) <= 60:
    return desc
  return desc[:57] + "…"


def _offer_from_decision(
    *,
    decision: dict[str, Any],
    proposer_role: str,
    round_number: int,
    parent_offer_id: str | None,
    currency: str,
    item_label: str,
    prior_cart: CartContents | None,
) -> Offer:
  """Materializes an Offer from a Claude decision dict."""
  terms = dict(decision.get("terms") or {})
  price = terms.get("price")
  if price is None and prior_cart is not None:
    price = prior_cart.payment_request.details.total.amount.value
  if price is None:
    raise ValueError("Decision produced no price and no prior cart to inherit.")

  terms.setdefault("currency", currency)
  terms["price"] = float(price)

  cart_contents = _build_cart_contents(
      price=float(price),
      currency=terms.get("currency", currency),
      item_label=item_label,
      prior_cart=prior_cart,
  )

  arguments = [
      {
          "type": arg.get("type", "generic"),
          "summary": arg.get("summary", ""),
          "payload": arg.get("payload"),
          "confidence": arg.get("confidence"),
      }
      for arg in (decision.get("arguments") or [])
      if arg.get("summary")
  ]

  return Offer.model_validate({
      "offer_id": f"offer_r{round_number}_{proposer_role}_{uuid.uuid4().hex[:6]}",
      "round_number": round_number,
      "proposer_role": proposer_role,
      "cart_contents": cart_contents.model_dump(),
      "terms": terms,
      "arguments": arguments,
      "expires_at": (
          datetime.now(timezone.utc) + timedelta(minutes=3)
      ).isoformat(),
      "parent_offer_id": parent_offer_id,
      "status": "proposed",
  })


def _build_cart_contents(
    *,
    price: float,
    currency: str,
    item_label: str,
    prior_cart: CartContents | None,
) -> CartContents:
  """Reuses the prior cart's structure when possible; builds fresh otherwise."""
  if prior_cart is not None:
    cloned = prior_cart.model_copy(deep=True)
    cloned.payment_request.details.total = PaymentItem(
        label="Total",
        amount=PaymentCurrencyAmount(currency=currency, value=price),
    )
    cloned.payment_request.details.display_items = [
        PaymentItem(
            label=item_label,
            amount=PaymentCurrencyAmount(currency=currency, value=price),
        )
    ]
    return cloned

  payment_request = PaymentRequest(
      method_data=[
          PaymentMethodData(
              supported_methods="CARD",
              data={"network": ["mastercard", "visa", "amex"]},
          )
      ],
      details=PaymentDetailsInit(
          id=f"order_{uuid.uuid4().hex[:8]}",
          display_items=[
              PaymentItem(
                  label=item_label,
                  amount=PaymentCurrencyAmount(
                      currency=currency, value=price
                  ),
              )
          ],
          total=PaymentItem(
              label="Total",
              amount=PaymentCurrencyAmount(currency=currency, value=price),
          ),
      ),
      options=PaymentOptions(request_shipping=True),
  )
  return CartContents(
      id=f"cart_{uuid.uuid4().hex[:8]}",
      user_cart_confirmation_required=True,
      payment_request=payment_request,
      cart_expiry=(
          datetime.now(timezone.utc) + timedelta(minutes=30)
      ).isoformat(),
      merchant_name="Haggle Demo Merchant",
  )


def _collect_risk_data(context_id: str) -> str:
  """Writes and returns a placeholder risk-data blob keyed on contextId."""
  risk_data = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...haggle_risk_data"
  storage.set_risk_data(context_id, risk_data)
  return risk_data


def _load_scenario_config() -> dict[str, Any]:
  """Reads optional scenario inventory from HAGGLE_MERCHANT_CONFIG env var."""
  path = os.environ.get("HAGGLE_MERCHANT_CONFIG")
  if not path:
    return {}
  try:
    with open(path, "r", encoding="utf-8") as fh:
      return json.load(fh)
  except OSError as exc:
    logging.warning("Could not read merchant config %s: %s", path, exc)
    return {}


async def _emit_outcome(
    updater: TaskUpdater, outcome: NegotiationOutcome
) -> None:
  await updater.add_artifact([
      Part(
          root=DataPart(
              data={NEGOTIATION_OUTCOME_DATA_KEY: outcome.model_dump()}
          )
      )
  ])
  await updater.complete()


async def _fail(updater: TaskUpdater, error_text: str) -> None:
  message = updater.new_agent_message(
      parts=[Part(root=TextPart(text=error_text))]
  )
  await updater.failed(message=message)
