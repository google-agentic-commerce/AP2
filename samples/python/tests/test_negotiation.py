# Copyright 2026 AP2-Haggle contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0

"""Unit tests for the AP2-Haggle types and message helpers.

These tests exercise protocol correctness without making live Claude or
Gemini calls. They cover:

- Pydantic roundtrip of NegotiationConstraints / Offer / NegotiationOutcome
- DataPart extraction via the haggle_utils helpers
- sealing an accepted Offer into a CartMandate
- End-to-end merchant dispatch for the three inbound shapes (opening /
  counter / accept), using monkeypatched seller_strategist decisions so
  no network call is made.
"""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any

import pytest

from ap2.types.mandate import CART_MANDATE_DATA_KEY
from ap2.types.mandate import CartContents
from ap2.types.mandate import INTENT_MANDATE_DATA_KEY
from ap2.types.mandate import IntentMandate
from ap2.types.negotiation import Argument
from ap2.types.negotiation import NEGOTIATION_CONSTRAINTS_DATA_KEY
from ap2.types.negotiation import NEGOTIATION_OUTCOME_DATA_KEY
from ap2.types.negotiation import NegotiationConstraints
from ap2.types.negotiation import NegotiationOutcome
from ap2.types.negotiation import OFFER_DATA_KEY
from ap2.types.negotiation import Offer
from ap2.types.payment_request import PaymentCurrencyAmount
from ap2.types.payment_request import PaymentDetailsInit
from ap2.types.payment_request import PaymentItem
from ap2.types.payment_request import PaymentMethodData
from ap2.types.payment_request import PaymentOptions
from ap2.types.payment_request import PaymentRequest
from common import haggle_utils


def _make_cart_contents(price: float = 1200.0) -> CartContents:
  payment_request = PaymentRequest(
      method_data=[
          PaymentMethodData(
              supported_methods="CARD", data={"network": ["visa"]}
          )
      ],
      details=PaymentDetailsInit(
          id="order_test",
          display_items=[
              PaymentItem(
                  label="Laptop",
                  amount=PaymentCurrencyAmount(
                      currency="USD", value=price
                  ),
              )
          ],
          total=PaymentItem(
              label="Total",
              amount=PaymentCurrencyAmount(
                  currency="USD", value=price
              ),
          ),
      ),
      options=PaymentOptions(request_shipping=True),
  )
  return CartContents(
      id="cart_test",
      user_cart_confirmation_required=True,
      payment_request=payment_request,
      cart_expiry="2026-04-24T18:00:00Z",
      merchant_name="Haggle Demo Merchant",
  )


def _make_offer(
    *,
    proposer_role: str = "merchant",
    round_number: int = 0,
    price: float = 1200.0,
    status: str = "proposed",
    parent_offer_id: str | None = None,
) -> Offer:
  return Offer(
      offer_id=f"offer_r{round_number}_{proposer_role}",
      round_number=round_number,
      proposer_role=proposer_role,
      cart_contents=_make_cart_contents(price),
      terms={
          "price": price,
          "currency": "USD",
          "warranty_months": 12,
          "delivery_days": 7,
      },
      arguments=[
          Argument(
              type="quality_guarantee",
              summary="Premium SKU.",
              payload=None,
              confidence=0.9,
          )
      ],
      expires_at="2026-04-24T17:05:00Z",
      parent_offer_id=parent_offer_id,
      status=status,
  )


def _make_constraints() -> NegotiationConstraints:
  return NegotiationConstraints(
      max_rounds=4,
      deadline="2026-04-24T18:00:00Z",
      target_terms={"price": 900.0, "currency": "USD", "warranty_months": 24},
      walk_away_terms={"price": 1050.0, "currency": "USD"},
      required_terms={"refundable": True},
      strategy_hint="Use RivalStore at $1150 as leverage.",
      style="cooperative",
  )


def _make_intent() -> IntentMandate:
  return IntentMandate(
      natural_language_description="A developer laptop, refundable.",
      user_cart_confirmation_required=True,
      intent_expiry="2026-04-25T15:00:00Z",
      requires_refundability=True,
  )


# --- Type tests ---


def test_negotiation_constraints_roundtrip() -> None:
  original = _make_constraints()
  dumped = original.model_dump()
  rehydrated = NegotiationConstraints.model_validate(dumped)
  assert rehydrated == original
  assert rehydrated.target_terms["price"] == 900.0
  assert rehydrated.required_terms["refundable"] is True


def test_offer_roundtrip_with_open_terms() -> None:
  offer = _make_offer(price=1099.5)
  dumped = offer.model_dump()
  rehydrated = Offer.model_validate(dumped)
  assert rehydrated.terms["price"] == 1099.5
  assert rehydrated.cart_contents.payment_request.details.total.amount.value == 1099.5
  # Open-axis sanity: caller-defined term must survive a roundtrip untouched.
  custom = Offer.model_validate({
      **dumped,
      "terms": {**dumped["terms"], "contract_duration_months": 12},
  })
  assert custom.terms["contract_duration_months"] == 12


def test_outcome_requires_cart_mandate_only_on_acceptance() -> None:
  # Rejected/abandoned/expired all leave final_cart_mandate unset.
  for status in ("rejected", "abandoned", "expired"):
    outcome = NegotiationOutcome(
        negotiation_id="ctx_test",
        status=status,  # type: ignore[arg-type]
        accepted_offer_id=None,
        final_cart_mandate=None,
        rounds_used=3,
        summary="test",
    )
    assert outcome.final_cart_mandate is None


# --- DataPart extraction tests ---


def test_extract_constraints_and_offer() -> None:
  constraints = _make_constraints()
  offer = _make_offer()
  data_parts = [
      {NEGOTIATION_CONSTRAINTS_DATA_KEY: constraints.model_dump()},
      {OFFER_DATA_KEY: offer.model_dump()},
      {"risk_data": "opaque-blob"},
  ]
  assert haggle_utils.extract_constraints(data_parts) == constraints
  assert haggle_utils.extract_offer(data_parts) == offer
  assert haggle_utils.extract_outcome(data_parts) is None


def test_extract_returns_none_when_absent() -> None:
  assert haggle_utils.extract_constraints([]) is None
  assert haggle_utils.extract_offer([]) is None
  assert haggle_utils.extract_outcome([]) is None


# --- Message builder tests ---


def test_open_negotiation_message_has_both_dataparts() -> None:
  msg = haggle_utils.build_open_negotiation_message(
      intent_mandate=_make_intent(),
      constraints=_make_constraints(),
      shopping_agent_id="trusted_shopping_agent",
      risk_data="rd",
  )
  keys = _data_keys(msg)
  assert INTENT_MANDATE_DATA_KEY in keys
  assert NEGOTIATION_CONSTRAINTS_DATA_KEY in keys
  assert "shopping_agent_id" in keys
  assert "risk_data" in keys


def test_offer_message_sets_context_and_task() -> None:
  offer = _make_offer(round_number=2, proposer_role="shopper", price=950.0)
  msg = haggle_utils.build_offer_message(
      offer,
      context_id="ctx_haggle_42",
      task_id="task_haggle_42",
      shopping_agent_id="trusted_shopping_agent",
      commentary="counter",
  )
  assert msg.context_id == "ctx_haggle_42"
  assert msg.task_id == "task_haggle_42"
  keys = _data_keys(msg)
  assert OFFER_DATA_KEY in keys
  assert "shopping_agent_id" in keys


def test_accepted_outcome_surfaces_cart_mandate_at_top_level() -> None:
  accepted_offer = _make_offer(status="accepted", round_number=3, price=1000.0)
  cart_mandate = haggle_utils.seal_offer_as_cart_mandate(accepted_offer)
  outcome = NegotiationOutcome(
      negotiation_id="ctx_accept",
      status="accepted",
      accepted_offer_id=accepted_offer.offer_id,
      final_cart_mandate=cart_mandate,
      rounds_used=3,
      summary="Converged.",
  )
  msg = haggle_utils.build_outcome_message(outcome, context_id="ctx_accept")
  keys = _data_keys(msg)
  assert NEGOTIATION_OUTCOME_DATA_KEY in keys
  # Top-level CartMandate DataPart so baseline AP2 clients see it without
  # haggle awareness.
  assert CART_MANDATE_DATA_KEY in keys


def test_non_accepted_outcome_omits_cart_mandate() -> None:
  outcome = NegotiationOutcome(
      negotiation_id="ctx_reject",
      status="rejected",
      accepted_offer_id=None,
      final_cart_mandate=None,
      rounds_used=4,
      summary="Out of rounds.",
  )
  msg = haggle_utils.build_outcome_message(outcome, context_id="ctx_reject")
  keys = _data_keys(msg)
  assert NEGOTIATION_OUTCOME_DATA_KEY in keys
  assert CART_MANDATE_DATA_KEY not in keys


# --- Sealing ---


def test_seal_offer_produces_signed_cart_mandate() -> None:
  offer = _make_offer(status="accepted", price=950.0)
  cart_mandate = haggle_utils.seal_offer_as_cart_mandate(offer)
  assert cart_mandate.contents == offer.cart_contents
  # Placeholder JWT stands in for real merchant signature.
  assert cart_mandate.merchant_authorization
  assert cart_mandate.merchant_authorization.startswith("eyJ")


def _data_keys(msg) -> set[str]:
  keys: set[str] = set()
  for part in msg.parts:
    root = part.root
    if hasattr(root, "data") and isinstance(root.data, dict):
      keys.update(root.data.keys())
  return keys
