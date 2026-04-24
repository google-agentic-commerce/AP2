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

"""In-memory storage for CartMandates and negotiation state.

A CartMandate may be updated multiple times during the course of a shopping
journey. This storage system is used to persist CartMandates between
interactions between the shopper and merchant agents. It also holds
negotiation-session state (offer history and per-session merchant context)
across the A2A round-trips that make up a multi-round bargain.
"""

from typing import Any
from typing import Optional

from ap2.types.mandate import CartMandate
from ap2.types.negotiation import Offer


def get_cart_mandate(cart_id: str) -> Optional[CartMandate]:
  """Get a cart mandate by cart ID."""
  return _store.get(cart_id)


def set_cart_mandate(cart_id: str, cart_mandate: CartMandate) -> None:
  """Set a cart mandate by cart ID."""
  _store[cart_id] = cart_mandate


def set_risk_data(context_id: str, risk_data: str) -> None:
  """Set risk data by context ID."""
  _store[context_id] = risk_data


def get_risk_data(context_id: str) -> Optional[str]:
  """Get risk data by context ID."""
  return _store.get(context_id)


# --- Negotiation session state ---


def set_merchant_context(context_id: str, merchant_context: dict[str, Any]) -> None:
  """Stores merchant-side private negotiation context (cost floor, etc.)."""
  _negotiation_context[context_id] = merchant_context


def get_merchant_context(context_id: str) -> Optional[dict[str, Any]]:
  """Retrieves merchant-side private negotiation context."""
  return _negotiation_context.get(context_id)


def append_offer(context_id: str, offer: Offer) -> None:
  """Appends an Offer to the negotiation's ordered history."""
  _offer_history.setdefault(context_id, []).append(offer)


def get_offer_history(context_id: str) -> list[Offer]:
  """Returns the ordered Offer history for a negotiation."""
  return list(_offer_history.get(context_id, []))


_store: dict[str, Any] = {}
_negotiation_context: dict[str, dict[str, Any]] = {}
_offer_history: dict[str, list[Offer]] = {}
