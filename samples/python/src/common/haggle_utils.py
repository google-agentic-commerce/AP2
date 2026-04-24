# Copyright 2026 AP2-Haggle contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0

"""Message-level helpers for the AP2-Haggle negotiation extension.

These helpers wrap `A2aMessageBuilder` to produce the three Haggle message
profiles (open-negotiation, offer, outcome) and to extract the three Haggle
DataParts from incoming messages. Intermediate offers remain unsigned; only
the terminal CartMandate (emitted via `seal_offer_as_cart_mandate`) carries
merchant authorization.
"""

from typing import Any

from a2a import types as a2a_types

from ap2.types.mandate import CART_MANDATE_DATA_KEY
from ap2.types.mandate import CartMandate
from ap2.types.mandate import INTENT_MANDATE_DATA_KEY
from ap2.types.mandate import IntentMandate
from ap2.types.negotiation import NEGOTIATION_CONSTRAINTS_DATA_KEY
from ap2.types.negotiation import NEGOTIATION_OUTCOME_DATA_KEY
from ap2.types.negotiation import NegotiationConstraints
from ap2.types.negotiation import NegotiationOutcome
from ap2.types.negotiation import OFFER_DATA_KEY
from ap2.types.negotiation import Offer
from common import message_utils
from common.a2a_message_builder import A2aMessageBuilder

# A placeholder JWT used by samples to simulate merchant authorization on a
# sealed CartMandate. Production deployments MUST replace this with a real
# signature from the merchant's private key.
_PLACEHOLDER_MERCHANT_JWT = "eyJhbGciOiJSUzI1NiIsImtpZCI6ImFwMi1oYWdnbGUtZGVtbyJ9..."


def build_open_negotiation_message(
    intent_mandate: IntentMandate,
    constraints: NegotiationConstraints,
    *,
    shopping_agent_id: str,
    risk_data: Any | None = None,
    debug_mode: bool = False,
) -> a2a_types.Message:
  """Builds the opening A2A Message that starts a negotiation.

  The message carries the base AP2 `IntentMandate` alongside the Haggle
  `NegotiationConstraints`; the second DataPart is the signal to the merchant
  that this is a negotiation rather than a one-shot cart request.
  """
  builder = (
      A2aMessageBuilder()
      .add_text("Open a negotiation for the attached IntentMandate.")
      .add_data(INTENT_MANDATE_DATA_KEY, intent_mandate.model_dump())
      .add_data(
          NEGOTIATION_CONSTRAINTS_DATA_KEY, constraints.model_dump()
      )
      .add_data("shopping_agent_id", shopping_agent_id)
      .add_data("debug_mode", debug_mode)
  )
  if risk_data is not None:
    builder.add_data("risk_data", risk_data)
  return builder.build()


def build_offer_message(
    offer: Offer,
    *,
    context_id: str,
    task_id: str | None = None,
    shopping_agent_id: str | None = None,
    commentary: str | None = None,
) -> a2a_types.Message:
  """Builds an A2A Message carrying a single counter/opening Offer."""
  builder = A2aMessageBuilder().set_context_id(context_id)
  if task_id:
    builder.set_task_id(task_id)
  builder.add_text(
      commentary
      or f"Round {offer.round_number} offer from {offer.proposer_role}."
  )
  builder.add_data(OFFER_DATA_KEY, offer.model_dump())
  if shopping_agent_id:
    builder.add_data("shopping_agent_id", shopping_agent_id)
  return builder.build()


def build_outcome_message(
    outcome: NegotiationOutcome,
    *,
    context_id: str,
    task_id: str | None = None,
) -> a2a_types.Message:
  """Builds the terminal A2A Message for a negotiation.

  On an accepted outcome, the `final_cart_mandate` is also surfaced as a
  top-level `ap2.mandates.CartMandate` DataPart so that any baseline AP2
  client scanning for CartMandates picks it up without haggle awareness.
  """
  builder = A2aMessageBuilder().set_context_id(context_id)
  if task_id:
    builder.set_task_id(task_id)
  builder.add_text(f"Negotiation {outcome.status}: {outcome.summary}")
  builder.add_data(NEGOTIATION_OUTCOME_DATA_KEY, outcome.model_dump())
  if outcome.status == "accepted" and outcome.final_cart_mandate is not None:
    builder.add_data(
        CART_MANDATE_DATA_KEY, outcome.final_cart_mandate.model_dump()
    )
  return builder.build()


def extract_constraints(
    data_parts: list[dict[str, Any]],
) -> NegotiationConstraints | None:
  """Returns the NegotiationConstraints, or None if the DataPart is absent."""
  raw = message_utils.find_data_part(
      NEGOTIATION_CONSTRAINTS_DATA_KEY, data_parts
  )
  return NegotiationConstraints.model_validate(raw) if raw else None


def extract_offer(data_parts: list[dict[str, Any]]) -> Offer | None:
  """Returns the first Offer DataPart, or None if absent."""
  raw = message_utils.find_data_part(OFFER_DATA_KEY, data_parts)
  return Offer.model_validate(raw) if raw else None


def extract_outcome(
    data_parts: list[dict[str, Any]],
) -> NegotiationOutcome | None:
  """Returns the NegotiationOutcome DataPart, or None if absent."""
  raw = message_utils.find_data_part(NEGOTIATION_OUTCOME_DATA_KEY, data_parts)
  return NegotiationOutcome.model_validate(raw) if raw else None


def seal_offer_as_cart_mandate(
    offer: Offer,
    *,
    merchant_jwt: str = _PLACEHOLDER_MERCHANT_JWT,
) -> CartMandate:
  """Wraps an accepted Offer's CartContents as a signed CartMandate.

  This is the single point in the negotiation flow where a real merchant
  would substitute its production signing logic. Samples use a placeholder
  JWT, matching the baseline AP2 samples.
  """
  return CartMandate(
      contents=offer.cart_contents,
      merchant_authorization=merchant_jwt,
  )
