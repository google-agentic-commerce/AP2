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

"""In-memory storage for CartMandates.

A CartMandate may be updated multiple times during the course of a shopping
journey. This storage system is used to persist CartMandates between
interactions between the shopper and merchant agents.
"""

from typing import Optional

from ap2.types.mandate import CartMandate


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


_store = {}
