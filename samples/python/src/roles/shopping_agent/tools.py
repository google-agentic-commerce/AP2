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

"""Tools used by the Shopping Agent.

Each agent uses individual tools to handle distinct tasks throughout the
shopping and purchasing process, such as updating a cart or initiating payment.
"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone
import logging
import os
import uuid

from a2a.types import Artifact
from google.adk.tools.tool_context import ToolContext

from .remote_agents import credentials_provider_client
from .remote_agents import haggle_merchant_client
from .remote_agents import merchant_agent_client
from .subagents.negotiator import decide as negotiator_decide
from ap2.types.contact_picker import ContactAddress
from ap2.types.mandate import CART_MANDATE_DATA_KEY
from ap2.types.mandate import CartMandate
from ap2.types.mandate import INTENT_MANDATE_DATA_KEY
from ap2.types.mandate import IntentMandate
from ap2.types.mandate import PAYMENT_MANDATE_DATA_KEY
from ap2.types.mandate import PaymentMandate
from ap2.types.mandate import PaymentMandateContents
from ap2.types.negotiation import NEGOTIATION_OUTCOME_DATA_KEY
from ap2.types.negotiation import NegotiationConstraints
from ap2.types.negotiation import NegotiationOutcome
from ap2.types.negotiation import OFFER_DATA_KEY
from ap2.types.negotiation import Offer
from ap2.types.payment_receipt import PAYMENT_RECEIPT_DATA_KEY
from ap2.types.payment_receipt import PaymentReceipt
from ap2.types.payment_request import PaymentResponse
from common import artifact_utils
from common import haggle_utils
from common.a2a_message_builder import A2aMessageBuilder


async def update_cart(
    shipping_address: ContactAddress,
    tool_context: ToolContext,
    debug_mode: bool = False,
) -> str:
  """Notifies the merchant agent of a shipping address selection for a cart.

  Args:
    shipping_address: The user's selected shipping address.
    tool_context: The ADK supplied tool context.
    debug_mode: Whether the agent is in debug mode.

  Returns:
    The updated CartMandate.
  """
  chosen_cart_id = tool_context.state["chosen_cart_id"]
  if not chosen_cart_id:
    raise RuntimeError("No chosen cart mandate found in tool context state.")

  message = (
      A2aMessageBuilder()
      .set_context_id(tool_context.state["shopping_context_id"])
      .add_text("Update the cart with the user's shipping address.")
      .add_data("cart_id", chosen_cart_id)
      .add_data("shipping_address", shipping_address)
      .add_data("shopping_agent_id", "trusted_shopping_agent")
      .add_data("debug_mode", debug_mode)
      .build()
  )
  task = await merchant_agent_client.send_a2a_message(message)

  updated_cart_mandate = artifact_utils.only(
      _parse_cart_mandates(task.artifacts)
  )

  tool_context.state["cart_mandate"] = updated_cart_mandate
  tool_context.state["shipping_address"] = shipping_address

  return updated_cart_mandate


async def initiate_payment(tool_context: ToolContext, debug_mode: bool = False):
  """Initiates a payment using the payment mandate from state.

  Args:
    tool_context: The ADK supplied tool context.
    debug_mode: Whether the agent is in debug mode.

  Returns:
    The status of the payment initiation.
  """
  payment_mandate = tool_context.state["signed_payment_mandate"]
  if not payment_mandate:
    raise RuntimeError("No signed payment mandate found in tool context state.")
  risk_data = tool_context.state["risk_data"]
  if not risk_data:
    raise RuntimeError("No risk data found in tool context state.")

  outgoing_message_builder = (
      A2aMessageBuilder()
      .set_context_id(tool_context.state["shopping_context_id"])
      .add_text("Initiate a payment")
      .add_data(PAYMENT_MANDATE_DATA_KEY, payment_mandate)
      .add_data("risk_data", risk_data)
      .add_data("shopping_agent_id", "trusted_shopping_agent")
      .add_data("debug_mode", debug_mode)
      .build()
  )
  task = await merchant_agent_client.send_a2a_message(outgoing_message_builder)
  store_receipt_if_present(task, tool_context)
  tool_context.state["initiate_payment_task_id"] = task.id
  return task.status


async def initiate_payment_with_otp(
    challenge_response: str, tool_context: ToolContext, debug_mode: bool = False
):
  """Initiates a payment using the payment mandate from state and a

    challenge response. In our sample, the challenge response is a one-time
    password (OTP) sent to the user.

  Args:
    challenge_response: The challenge response.
    tool_context: The ADK supplied tool context.
    debug_mode: Whether the agent is in debug mode.

  Returns:
    The status of the payment initiation.
  """
  payment_mandate = tool_context.state["signed_payment_mandate"]
  if not payment_mandate:
    raise RuntimeError("No signed payment mandate found in tool context state.")
  risk_data = tool_context.state["risk_data"]
  if not risk_data:
    raise RuntimeError("No risk data found in tool context state.")

  outgoing_message_builder = (
      A2aMessageBuilder()
      .set_context_id(tool_context.state["shopping_context_id"])
      .set_task_id(tool_context.state["initiate_payment_task_id"])
      .add_text("Initiate a payment. Include the challenge response.")
      .add_data(PAYMENT_MANDATE_DATA_KEY, payment_mandate)
      .add_data("shopping_agent_id", "trusted_shopping_agent")
      .add_data("challenge_response", challenge_response)
      .add_data("risk_data", risk_data)
      .add_data("debug_mode", debug_mode)
      .build()
  )

  task = await merchant_agent_client.send_a2a_message(outgoing_message_builder)
  store_receipt_if_present(task, tool_context)
  return task.status


def store_receipt_if_present(task, tool_context: ToolContext) -> None:
  """Stores the payment receipt in state."""
  payment_receipts = artifact_utils.find_canonical_objects(
      task.artifacts, PAYMENT_RECEIPT_DATA_KEY, PaymentReceipt
  )
  if payment_receipts:
    payment_receipt = artifact_utils.only(payment_receipts)
    tool_context.state["payment_receipt"] = payment_receipt


def create_payment_mandate(
    payment_method_alias: str,
    user_email: str,
    tool_context: ToolContext,
) -> str:
  """Creates a payment mandate and stores it in state.

  Args:
    payment_method_alias: The payment method alias.
    user_email: The user's email address.
    tool_context: The ADK supplied tool context.

  Returns:
    The payment mandate.
  """
  cart_mandate = tool_context.state["cart_mandate"]

  payment_request = cart_mandate.contents.payment_request
  shipping_address = tool_context.state["shipping_address"]

  payment_method = os.environ.get("PAYMENT_METHOD", "CARD")
  if payment_method == "x402":
    method_name = "https://www.x402.org/"
    details = tool_context.state["payment_credential_token"]
  else:
    method_name = "CARD"
    details = {
        "token": tool_context.state["payment_credential_token"],
    }

  payment_response = PaymentResponse(
      request_id=payment_request.details.id,
      method_name=method_name,
      details=details,
      shipping_address=shipping_address,
      payer_email=user_email,
  )

  payment_mandate = PaymentMandate(
      payment_mandate_contents=PaymentMandateContents(
          payment_mandate_id=uuid.uuid4().hex,
          timestamp=datetime.now(timezone.utc).isoformat(),
          payment_details_id=payment_request.details.id,
          payment_details_total=payment_request.details.total,
          payment_response=payment_response,
          merchant_agent=cart_mandate.contents.merchant_name,
      ),
  )

  tool_context.state["payment_mandate"] = payment_mandate
  return payment_mandate


def sign_mandates_on_user_device(tool_context: ToolContext) -> str:
  """Simulates signing the transaction details on a user's secure device.

  This function represents the step where the final transaction details,
  including hashes of the cart and payment mandates, would be sent to a
  secure hardware element on the user's device (e.g., Secure Enclave) to be
  cryptographically signed with the user's private key.

  Note: This is a placeholder implementation. It does not perform any actual
  cryptographic operations. It simulates the creation of a signature by
  concatenating the mandate hashes.

  Args:
      tool_context: The context object used for state management. It is expected
        to contain the `payment_mandate` and `cart_mandate`.

  Returns:
      A string representing the simulated user authorization signature (JWT).
  """
  payment_mandate: PaymentMandate = tool_context.state["payment_mandate"]
  cart_mandate: CartMandate = tool_context.state["cart_mandate"]
  cart_mandate_hash = _generate_cart_mandate_hash(cart_mandate)
  payment_mandate_hash = _generate_payment_mandate_hash(
      payment_mandate.payment_mandate_contents
  )
  # A JWT containing the user's digital signature to authorize the transaction.
  # The payload uses hashes to bind the signature to the specific cart and
  # payment details, and includes a nonce to prevent replay attacks.
  payment_mandate.user_authorization = (
      cart_mandate_hash + "_" + payment_mandate_hash
  )
  tool_context.state["signed_payment_mandate"] = payment_mandate
  return payment_mandate.user_authorization


async def send_signed_payment_mandate_to_credentials_provider(
    tool_context: ToolContext,
    debug_mode: bool = False,
) -> str:
  """Sends the signed payment mandate to the credentials provider.

  Args:
    tool_context: The ADK supplied tool context.
    debug_mode: Whether the agent is in debug mode.
  """
  payment_mandate = tool_context.state["signed_payment_mandate"]
  if not payment_mandate:
    raise RuntimeError("No signed payment mandate found in tool context state.")
  risk_data = tool_context.state["risk_data"]
  if not risk_data:
    raise RuntimeError("No risk data found in tool context state.")
  message = (
      A2aMessageBuilder()
      .set_context_id(tool_context.state["shopping_context_id"])
      .add_text("This is the signed payment mandate")
      .add_data(PAYMENT_MANDATE_DATA_KEY, payment_mandate)
      .add_data("risk_data", risk_data)
      .add_data("debug_mode", debug_mode)
      .build()
  )
  return await credentials_provider_client.send_a2a_message(message)


def _generate_cart_mandate_hash(cart_mandate: CartMandate) -> str:
  """Generates a cryptographic hash of the CartMandate.

  This hash serves as a tamper-proof reference to the specific merchant-signed
  cart offer that the user has approved.

  Note: This is a placeholder implementation for development. A real
  implementation must use a secure hashing algorithm (e.g., SHA-256) on the
  canonical representation of the CartMandate object.

  Args:
      cart_mandate: The complete CartMandate object, including the merchant's
        authorization.

  Returns:
      A string representing the hash of the cart mandate.
  """
  return "fake_cart_mandate_hash_" + cart_mandate.contents.id


def _generate_payment_mandate_hash(
    payment_mandate_contents: PaymentMandateContents,
) -> str:
  """Generates a cryptographic hash of the PaymentMandateContents.

  This hash creates a tamper-proof reference to the specific payment details
  the user is about to authorize.

  Note: This is a placeholder implementation for development. A real
  implementation must use a secure hashing algorithm (e.g., SHA-256) on the
  canonical representation of the PaymentMandateContents object.

  Args:
      payment_mandate_contents: The payment mandate contents to hash.

  Returns:
      A string representing the hash of the payment mandate contents.
  """
  return (
      "fake_payment_mandate_hash_" + payment_mandate_contents.payment_mandate_id
  )


def _parse_cart_mandates(artifacts: list[Artifact]) -> list[CartMandate]:
  """Parses a list of artifacts into a list of CartMandate objects."""
  return artifact_utils.find_canonical_objects(
      artifacts, CART_MANDATE_DATA_KEY, CartMandate
  )


async def negotiate_purchase(
    target_price: float,
    max_price: float,
    currency: str,
    required_terms_json: str,
    preferred_warranty_months: int,
    preferred_delivery_days: int,
    max_rounds: int,
    strategy_hint: str,
    style: str,
    tool_context: ToolContext,
    debug_mode: bool = False,
) -> dict:
  """Runs a multi-round negotiation with the merchant agent.

  Uses an IntentMandate already staged in state (by the `shopper` subagent)
  and opens an AP2-Haggle negotiation with the merchant. The tool drives
  the round loop locally: each round it asks the Claude-backed negotiator
  subagent how to respond to the merchant's latest offer, then sends an
  A2A message back to the merchant. On acceptance it stores the merchant-
  signed CartMandate in state under `cart_mandate`, matching the shape the
  downstream payment tools expect.

  Args:
    target_price: Preferred total price in `currency`.
    max_price: Walk-away ceiling — the negotiator will abandon rather than
      accept a price above this.
    currency: Three-letter ISO 4217 code (e.g. "USD").
    required_terms_json: JSON dict string with hard requirements that
      every offer MUST satisfy (e.g. {"refundable": true}). Pass "{}" if
      none.
    preferred_warranty_months: Preferred minimum warranty window; goes
      into `target_terms`.
    preferred_delivery_days: Preferred maximum delivery window; goes into
      `target_terms`.
    max_rounds: Hard cap on the number of rounds. Typical: 4-8.
    strategy_hint: Free-form guidance for the shopper's negotiator LLM.
    style: One of "cooperative" | "competitive" | "collaborative".
    tool_context: The ADK tool context; `intent_mandate` must already be
      present in state.
    debug_mode: Whether the agents are in verbose debug mode.

  Returns:
    A dict with `status` plus (when accepted) the final cart summary and
    a list of per-round transcript entries for the root agent to surface
    to the user.
  """
  import json as _json

  intent_mandate: IntentMandate = tool_context.state.get("intent_mandate")
  if intent_mandate is None:
    raise RuntimeError(
        "negotiate_purchase: no IntentMandate in state. Run the shopper"
        " subagent first."
    )

  try:
    required_terms = _json.loads(required_terms_json or "{}")
    if not isinstance(required_terms, dict):
      required_terms = {}
  except ValueError:
    required_terms = {}

  constraints = NegotiationConstraints(
      max_rounds=max_rounds,
      deadline=(
          datetime.now(timezone.utc) + timedelta(minutes=15)
      ).isoformat(),
      target_terms={
          "price": float(target_price),
          "currency": currency,
          "warranty_months": preferred_warranty_months,
          "delivery_days": preferred_delivery_days,
      },
      walk_away_terms={
          "price": float(max_price),
          "currency": currency,
      },
      required_terms=required_terms or None,
      strategy_hint=strategy_hint or None,
      style=style if style in ("cooperative", "competitive", "collaborative") else "cooperative",
  )
  tool_context.state["negotiation_constraints"] = constraints

  risk_data = _collect_risk_data(tool_context)
  opening = haggle_utils.build_open_negotiation_message(
      intent_mandate=intent_mandate,
      constraints=constraints,
      shopping_agent_id="trusted_shopping_agent",
      risk_data=risk_data,
      debug_mode=debug_mode,
  )

  transcript: list[dict] = []
  task = await haggle_merchant_client.send_a2a_message(opening)
  tool_context.state["shopping_context_id"] = task.context_id

  merchant_offer = _first_offer(task.artifacts)
  if merchant_offer is None:
    outcome = _first_outcome(task.artifacts)
    return _finalize_failed(outcome, transcript, reason="no_opening_offer")
  transcript.append(_transcript_entry(merchant_offer))

  for round_index in range(1, constraints.max_rounds + 1):
    history = _state_offer_history(tool_context, merchant_offer)
    decision = negotiator_decide.decide_shopper_move(
        constraints=constraints,
        offer_history=history[:-1],
        latest_merchant_offer=merchant_offer,
        round_number=round_index,
    )
    logging.info("Shopper round %d decision: %s", round_index, decision)
    action = decision.get("action")

    if action == "accept":
      accept_offer = merchant_offer.model_copy(
          update={"status": "accepted"}
      )
      accept_msg = haggle_utils.build_offer_message(
          offer=accept_offer,
          context_id=task.context_id,
          task_id=task.id,
          shopping_agent_id="trusted_shopping_agent",
          commentary="Shopper accepts the merchant's offer.",
      )
      task = await haggle_merchant_client.send_a2a_message(accept_msg)
      return _finalize_accepted(
          tool_context,
          task,
          transcript,
          rationale=decision.get("rationale", ""),
      )

    if action == "walk":
      outcome = NegotiationOutcome(
          negotiation_id=task.context_id,
          status="abandoned",
          accepted_offer_id=None,
          final_cart_mandate=None,
          rounds_used=merchant_offer.round_number,
          summary=decision.get("rationale")
          or "Shopper abandoned negotiation.",
      )
      walk_msg = haggle_utils.build_outcome_message(
          outcome, context_id=task.context_id, task_id=task.id
      )
      await haggle_merchant_client.send_a2a_message(walk_msg)
      return _finalize_failed(outcome, transcript, reason="walk_away")

    # counter: build a shopper counter offer, send, loop
    counter_offer = _build_shopper_counter(
        decision=decision,
        prior_merchant_offer=merchant_offer,
        constraints=constraints,
        round_number=round_index,
    )
    transcript.append(_transcript_entry(counter_offer))
    counter_msg = haggle_utils.build_offer_message(
        offer=counter_offer,
        context_id=task.context_id,
        task_id=task.id,
        shopping_agent_id="trusted_shopping_agent",
        commentary=decision.get("rationale", ""),
    )
    task = await haggle_merchant_client.send_a2a_message(counter_msg)

    accepted_cart = _first_cart_mandate(task.artifacts)
    if accepted_cart is not None:
      return _finalize_accepted(
          tool_context,
          task,
          transcript,
          rationale=f"Merchant accepted shopper counter (round {round_index}).",
      )

    next_merchant_offer = _first_offer(task.artifacts)
    outcome = _first_outcome(task.artifacts)
    if next_merchant_offer is None and outcome is not None:
      return _finalize_failed(outcome, transcript, reason=outcome.status)
    if next_merchant_offer is None:
      return _finalize_failed(None, transcript, reason="protocol_error")

    merchant_offer = next_merchant_offer
    transcript.append(_transcript_entry(merchant_offer))

  # Loop fell through: rounds exhausted.
  outcome = NegotiationOutcome(
      negotiation_id=task.context_id,
      status="rejected",
      accepted_offer_id=None,
      final_cart_mandate=None,
      rounds_used=constraints.max_rounds,
      summary="max_rounds reached without convergence.",
  )
  return _finalize_failed(outcome, transcript, reason="max_rounds")


# --- Helpers for the negotiation tool ---


def _first_offer(artifacts: list[Artifact]) -> Offer | None:
  offers = artifact_utils.find_canonical_objects(
      artifacts, OFFER_DATA_KEY, Offer
  )
  return offers[0] if offers else None


def _first_outcome(artifacts: list[Artifact]) -> NegotiationOutcome | None:
  outcomes = artifact_utils.find_canonical_objects(
      artifacts, NEGOTIATION_OUTCOME_DATA_KEY, NegotiationOutcome
  )
  return outcomes[0] if outcomes else None


def _first_cart_mandate(artifacts: list[Artifact]) -> CartMandate | None:
  carts = _parse_cart_mandates(artifacts)
  return carts[0] if carts else None


def _state_offer_history(
    tool_context: ToolContext, latest_merchant: Offer
) -> list[Offer]:
  history: list[Offer] = list(
      tool_context.state.get("haggle_offer_history") or []
  )
  history.append(latest_merchant)
  tool_context.state["haggle_offer_history"] = history
  return history


def _build_shopper_counter(
    *,
    decision: dict,
    prior_merchant_offer: Offer,
    constraints: NegotiationConstraints,
    round_number: int,
) -> Offer:
  """Materializes a shopper counter-offer from a Claude decision."""
  terms = dict(decision.get("terms") or {})
  price = terms.get("price")
  if price is None:
    # Fallback: split the difference between target and the merchant's ask.
    merchant_price = prior_merchant_offer.terms.get("price")
    target = (constraints.target_terms or {}).get("price")
    if merchant_price is not None and target is not None:
      price = (float(merchant_price) + float(target)) / 2
    elif merchant_price is not None:
      price = float(merchant_price) * 0.95
    else:
      raise RuntimeError(
          "Shopper counter decision has no price and no way to infer one."
      )
  terms["price"] = float(price)
  terms.setdefault(
      "currency",
      (constraints.target_terms or {}).get("currency") or "USD",
  )

  # Mirror the merchant's cart_contents so the CartContents represents the
  # same item, with our proposed price substituted into the total.
  import copy as _copy
  from ap2.types.payment_request import PaymentCurrencyAmount
  from ap2.types.payment_request import PaymentItem

  cart = _copy.deepcopy(prior_merchant_offer.cart_contents)
  cart.payment_request.details.total = PaymentItem(
      label="Total",
      amount=PaymentCurrencyAmount(currency=terms["currency"], value=terms["price"]),
  )
  if cart.payment_request.details.display_items:
    # Replace the primary line item price to match the counter.
    first = cart.payment_request.details.display_items[0]
    cart.payment_request.details.display_items[0] = PaymentItem(
        label=first.label,
        amount=PaymentCurrencyAmount(
            currency=terms["currency"], value=terms["price"]
        ),
        pending=first.pending,
    )

  arguments = [
      {
          "type": a.get("type", "generic"),
          "summary": a.get("summary", ""),
          "payload": a.get("payload"),
          "confidence": a.get("confidence"),
      }
      for a in (decision.get("arguments") or [])
      if a.get("summary")
  ]

  return Offer.model_validate({
      "offer_id": f"offer_r{round_number}_shopper_{uuid.uuid4().hex[:6]}",
      "round_number": round_number,
      "proposer_role": "shopper",
      "cart_contents": cart.model_dump(),
      "terms": terms,
      "arguments": arguments,
      "expires_at": (
          datetime.now(timezone.utc) + timedelta(minutes=3)
      ).isoformat(),
      "parent_offer_id": prior_merchant_offer.offer_id,
      "status": "proposed",
  })


def _finalize_accepted(
    tool_context: ToolContext,
    task,
    transcript: list[dict],
    rationale: str,
) -> dict:
  cart = _first_cart_mandate(task.artifacts)
  outcome = _first_outcome(task.artifacts)
  if cart is None:
    return _finalize_failed(outcome, transcript, reason="no_signed_cart")

  tool_context.state["cart_mandate"] = cart
  tool_context.state["chosen_cart_id"] = cart.contents.id
  return {
      "status": "accepted",
      "rationale": rationale,
      "final_price": cart.contents.payment_request.details.total.amount.value,
      "currency": cart.contents.payment_request.details.total.amount.currency,
      "cart_id": cart.contents.id,
      "rounds": len(transcript),
      "outcome_summary": outcome.summary if outcome else None,
      "transcript": transcript,
  }


def _finalize_failed(
    outcome: NegotiationOutcome | None,
    transcript: list[dict],
    *,
    reason: str,
) -> dict:
  return {
      "status": outcome.status if outcome else "failed",
      "reason": reason,
      "rounds": len(transcript),
      "outcome_summary": outcome.summary if outcome else None,
      "transcript": transcript,
  }


def _transcript_entry(offer: Offer) -> dict:
  return {
      "round": offer.round_number,
      "proposer": offer.proposer_role,
      "terms": offer.terms,
      "arguments": [
          {"type": a.type, "summary": a.summary} for a in offer.arguments
      ],
  }


def _collect_risk_data(tool_context: ToolContext) -> str:
  risk_data = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...fake_risk_data"
  tool_context.state["risk_data"] = risk_data
  return risk_data
