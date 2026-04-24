# Copyright 2025 Google LLC
# Copyright 2026 AP2-Haggle contributors
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

"""Definitions for the AP2-Haggle negotiation extension.

These types carry multi-round, multi-axis bargaining between a shopping agent
and a merchant agent on top of the base AP2 protocol. They are non-binding:
the only signed artifact in a negotiation is the final `CartMandate` that the
merchant produces when both sides converge on an Offer.

Extensibility is intentional. `terms`, `target_terms`, `walk_away_terms`,
`required_terms` and `Argument.payload` are all open dicts, so implementations
can negotiate over any dimension — price, quantity, delivery SLA, warranty,
bundle composition, contract length, payment-net days, loyalty-based
discounts, competitor comparisons, and so on — without a schema break.
"""

from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Literal
from typing import Optional

from ap2.types.mandate import CartContents
from ap2.types.mandate import CartMandate
from pydantic import BaseModel
from pydantic import Field

NEGOTIATION_CONSTRAINTS_DATA_KEY = "ap2.haggle.NegotiationConstraints"
OFFER_DATA_KEY = "ap2.haggle.Offer"
NEGOTIATION_OUTCOME_DATA_KEY = "ap2.haggle.NegotiationOutcome"

NegotiationStyle = Literal["cooperative", "competitive", "collaborative"]
ProposerRole = Literal["merchant", "shopper"]
OfferStatus = Literal["proposed", "accepted", "rejected", "withdrawn"]
OutcomeStatus = Literal["accepted", "rejected", "expired", "abandoned"]


class NegotiationConstraints(BaseModel):
  """Buyer-side policy governing an acceptable deal.

  A `NegotiationConstraints` object MAY be attached to an IntentMandate A2A
  Message as an additional DataPart with key `ap2.haggle.NegotiationConstraints`.
  Presence of this DataPart signals to the merchant that the shopping agent is
  willing to negotiate rather than receive a one-shot CartMandate.

  All "terms" fields are open dicts so that implementations can negotiate over
  arbitrary dimensions. Well-known keys include (but are not limited to):
  `price`, `currency`, `quantity`, `delivery_days`, `warranty_months`,
  `payment_terms_net_days`, `contract_duration_months`, `bundle_skus`,
  `loyalty_discount_bps`.
  """

  max_rounds: int = Field(
      ...,
      description=(
          "Hard cap on the number of offer/counter-offer rounds. When reached"
          " without convergence, the negotiation terminates with status"
          ' "rejected".'
      ),
      example=6,
  )
  deadline: str = Field(
      ...,
      description=(
          "Absolute deadline after which the negotiation terminates with"
          ' status "expired". ISO 8601 format.'
      ),
      example="2026-04-24T18:00:00Z",
  )
  target_terms: Optional[dict[str, Any]] = Field(
      None,
      description=(
          "The ideal outcome the buyer is aiming for. Used by the negotiator"
          " as an anchor when generating counter-offers. Open key set."
      ),
      example={"price": 850.0, "currency": "USD", "warranty_months": 24},
  )
  walk_away_terms: Optional[dict[str, Any]] = Field(
      None,
      description=(
          "The worst still-acceptable outcome. If a proposal violates these,"
          " the negotiator SHOULD emit a walk-away rather than counter."
          " Implementations choose comparison semantics (e.g. price <= max,"
          " warranty_months >= min)."
      ),
      example={"price": 1000.0, "warranty_months": 18, "delivery_days": 7},
  )
  required_terms: Optional[dict[str, Any]] = Field(
      None,
      description=(
          "Non-negotiable requirements. An offer that does not satisfy every"
          " key here MUST NOT be accepted. Distinct from walk_away_terms in"
          " that these are hard filters, not trade-off boundaries."
      ),
      example={"currency": "USD", "refundable": True},
  )
  strategy_hint: Optional[str] = Field(
      None,
      description=(
          "Free-text guidance the shopping agent passes to its negotiator"
          " LLM — e.g. opening offer, preferred concessions, urgency cues."
      ),
      example=(
          "Start at $850 and work up in $25 increments. Emphasize that we're"
          " a returning customer and compare with competitor X's $950 listing."
      ),
  )
  style: NegotiationStyle = Field(
      "cooperative",
      description=(
          "Overall bargaining posture. Informs the LLM how aggressively to"
          " push and how much concession to extend."
      ),
  )


class Argument(BaseModel):
  """A structured unit of persuasion exchanged during negotiation.

  `type` is an open string, not a closed enum, so implementations can add new
  persuasion categories without a protocol break. Examples in current use:
  "market_comparison", "loyalty_discount", "bulk_discount", "urgency",
  "competitor_offer", "quality_guarantee", "recurring_customer",
  "sla_upgrade", "bundle_discount", "cost_floor", "contract_term_extension",
  "net_payment_terms", "reference_customer".
  """

  type: str = Field(
      ...,
      description=(
          "Open string tag identifying the persuasion category. Receivers"
          " SHOULD treat unknown types as informational and fall back to the"
          " `summary` field."
      ),
      example="competitor_offer",
  )
  summary: str = Field(
      ...,
      description=(
          "Human-readable justification. Receivers without a structured"
          " handler for `type` MUST still be able to surface this to a human."
      ),
      example="Competitor store lists the same model for $950 with free shipping.",
  )
  payload: Optional[dict[str, Any]] = Field(
      None,
      description=(
          "Type-specific structured data. For example, `competitor_offer` may"
          " carry {url, price, currency}; `loyalty_discount` may carry"
          " {years_active, tier}."
      ),
      example={"url": "https://competitor.example/sku/42", "price": 950.0},
  )
  confidence: Optional[float] = Field(
      None,
      description=(
          "Optional signal 0..1 from the proposing LLM indicating how strong"
          " it believes the argument to be. Receivers MAY use this as a tie"
          " breaker; protocol conformance does not depend on it."
      ),
      ge=0.0,
      le=1.0,
      example=0.8,
  )


class Offer(BaseModel):
  """A non-binding proposal within an active negotiation.

  Either side may propose. Intermediate Offers are NOT cryptographically
  signed — they carry a plain `CartContents`, not a `CartMandate`. Only when
  an Offer is accepted does the merchant re-wrap its contents into a signed
  `CartMandate`, which then flows into the standard AP2 payment path.

  The `contextId` of the enclosing A2A Message acts as the negotiation
  thread id; `round_number` orders Offers within that thread.
  """

  offer_id: str = Field(
      ...,
      description="Unique identifier for this Offer within the negotiation.",
      example="offer_r0_merchant_a1",
  )
  round_number: int = Field(
      ...,
      description=(
          "Zero-based round index. Round 0 is the merchant's opening offer;"
          " each subsequent counter increments the round."
      ),
      ge=0,
      example=0,
  )
  proposer_role: ProposerRole = Field(
      ...,
      description='Which side produced this Offer — "merchant" or "shopper".',
  )
  cart_contents: CartContents = Field(
      ...,
      description=(
          "The proposed cart. Reused from AP2 core to keep the payment path"
          " unchanged once the Offer is accepted. Note that `CartContents`"
          " alone is unsigned; only the terminal `CartMandate` is signed."
      ),
  )
  terms: dict[str, Any] = Field(
      default_factory=dict,
      description=(
          "Structured, machine-readable summary of the proposal's negotiable"
          " axes. Open key set. Typical keys: price, currency, quantity,"
          " delivery_days, warranty_months, payment_terms_net_days,"
          " loyalty_discount_bps, bundle_skus, contract_duration_months."
          " Values here SHOULD be consistent with `cart_contents.payment_request`"
          " so that either representation can be the source of truth."
      ),
      example={
          "price": 1050.0,
          "currency": "USD",
          "warranty_months": 24,
          "delivery_days": 5,
      },
  )
  arguments: list[Argument] = Field(
      default_factory=list,
      description=(
          "Persuasion payload — why the proposer believes the other side"
          " should accept this offer."
      ),
  )
  expires_at: str = Field(
      ...,
      description=(
          "Short-lived expiry for this Offer, ISO 8601. Typically seconds"
          " to minutes. A counter received after expiry SHOULD be treated"
          " as a new opening proposal."
      ),
      example="2026-04-24T17:05:00Z",
  )
  parent_offer_id: Optional[str] = Field(
      None,
      description=(
          "The `offer_id` this Offer counters. Null for opening offers."
      ),
      example="offer_r0_merchant_a1",
  )
  status: OfferStatus = Field(
      "proposed",
      description=(
          'Lifecycle state. "proposed" is the default; the terminal states'
          ' "accepted", "rejected" and "withdrawn" are set by the receiving'
          " side or the proposer to mark closure."
      ),
  )
  timestamp: str = Field(
      default_factory=lambda: datetime.now(timezone.utc).isoformat(),
      description="When this Offer was produced, ISO 8601.",
  )


class NegotiationOutcome(BaseModel):
  """Terminal state of a negotiation thread.

  Emitted by whichever side detects the terminal condition. When status is
  "accepted", `final_cart_mandate` MUST be populated with the merchant-signed
  artifact so downstream payment flow can proceed without re-negotiating.
  """

  negotiation_id: str = Field(
      ...,
      description=(
          "Thread identifier — MUST equal the A2A `contextId` of the"
          " negotiation messages."
      ),
      example="ctx_neg_shoes_4711",
  )
  status: OutcomeStatus = Field(
      ...,
      description=(
          'Terminal status. "accepted" — convergence; "rejected" —'
          " max_rounds exhausted without convergence; \"expired\" — deadline"
          ' passed; "abandoned" — one side explicitly walked away.'
      ),
  )
  accepted_offer_id: Optional[str] = Field(
      None,
      description=(
          "The `offer_id` that both sides converged on. Present iff"
          ' status == "accepted".'
      ),
  )
  final_cart_mandate: Optional[CartMandate] = Field(
      None,
      description=(
          "Merchant-signed CartMandate representing the agreed deal. Present"
          ' iff status == "accepted". Downstream payment flow uses this'
          " unchanged — no payment-processor awareness of the negotiation"
          " is required."
      ),
  )
  rounds_used: int = Field(
      ...,
      description="Number of rounds actually consumed (0-based count).",
      ge=0,
      example=3,
  )
  summary: str = Field(
      ...,
      description=(
          "Short narrative of how the negotiation went — useful for logs,"
          " user-facing debriefs, and post-hoc analysis. Generated by the"
          " proposing agent's LLM."
      ),
      example=(
          "Converged on $1050 / 24mo warranty / 5-day delivery after 3"
          " rounds. Merchant anchored at $1200; competitor comparison and"
          " bulk argument secured 2-year warranty."
      ),
  )
