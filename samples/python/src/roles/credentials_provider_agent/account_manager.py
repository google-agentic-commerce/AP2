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

"""An in-memory manager of a user's 'account details'.

Each 'account' contains a user's payment methods and shipping address.
For demonstration purposes, several accounts are pre-populated with sample data.
"""

from typing import Any


_account_db = {
    "bugsbunny@gmail.com": {
        "shipping_address": {
            "recipient": "Bugs Bunny",
            "organization": "Sample Organization",
            "address_line": ["123 Main St"],
            "city": "Sample City",
            "region": "ST",
            "postal_code": "00000",
            "country": "US",
            "phone_number": "+1-000-000-0000",
        },
        "payment_methods": {
            "card1": {
                "type": "CARD",
                "alias": "American Express ending in 4444",
                "network": [{"name": "amex", "formats": ["DPAN"]}],
                "cryptogram": "fake_cryptogram_abc123",
                "token": "1111000000000000",
                "card_holder_name": "John Doe",
                "card_expiration": "12/2025",
                "card_billing_address": {
                    "country": "US",
                    "postal_code": "00000",
                },
            },
            "card2": {
                "type": "CARD",
                "alias": "American Express ending in 8888",
                "network": [{"name": "amex", "formats": ["DPAN"]}],
                "cryptogram": "fake_cryptogram_ghi789",
                "token": "2222000000000000",
                "card_holder_name": "Bugs Bunny",
                "card_expiration": "10/2027",
                "card_billing_address": {
                    "country": "US",
                    "postal_code": "00000",
                },
            },
            "bank_account1": {
                "type": "BANK_ACCOUNT",
                "account_number": "111",
                "alias": "Primary bank account",
            },
            "digital_wallet1": {
                "type": "DIGITAL_WALLET",
                "brand": "PayPal",
                "account_identifier": "foo@bar.com",
                "alias": "Bugs's PayPal account",
            },
        },
    },
    "daffyduck@gmail.com": {
        "payment_methods": {
            "bank_account1": {
                "type": "BANK_ACCOUNT",
                "brand": "Bank of Money",
                "account_number": "789",
                "alias": "Main checking account",
            }
        },
    },
    "elmerfudd@gmail.com": {
        "payment_methods": {
            "digital_wallet1": {
                "type": "DIGITAL_WALLET",
                "brand": "PayPal",
                "account_identifier": "elmerfudd@gmail.com",
                "alias": "Fudd's PayPal",
            }
        }
    },
}


_token = {}


def create_token(email_address: str, payment_method_alias: str) -> str:
  """Creates and stores a token for an account.

  Args:
    email_address: The email address of the account.
    payment_method_alias: The alias of the payment method.

  Returns:
    The token for the payment method.
  """
  token = f"fake_payment_credential_token_{len(_token)}"

  _token[token] = {
      "email_address": email_address,
      "payment_method_alias": payment_method_alias,
      "payment_mandate_id": None,
  }

  return token


def update_token(token: str, payment_mandate_id: str) -> None:
  """Updates the token with the payment mandate id.

  Args:
    token: The token to update.
    payment_mandate_id: The payment mandate id to associate with the token.
  """
  if token not in _token:
    raise ValueError(f"Token {token} not found")
  if _token[token].get("payment_mandate_id"):
    # Do not overwrite the payment mandate id if it is already set.
    return
  _token[token]["payment_mandate_id"] = payment_mandate_id

def verify_token(token: str, payment_mandate_id: str) -> dict[str, Any]:
  """Look up an account by token.

  Args:
    token: The token for look up.
    payment_mandate_id: The payment mandate id associated with the token.

  Returns:
    The account for the given token, or status:invalid_token if the token is not
    valid.
  """
  account_lookup = _token.get(token, {})
  if not account_lookup:
    raise ValueError("Invalid token")
  if account_lookup.get("payment_mandate_id") != payment_mandate_id:
    raise ValueError("Invalid token")
  email_address = account_lookup.get("email_address")
  alias = account_lookup.get("payment_method_alias")
  return get_payment_method_by_alias(email_address, alias)


def get_account_payment_methods(email_address: str) -> list[dict[str, Any]]:
  """Returns a list of the payment methods for the given account email address.

  Args:
    email_address: The account's email address.

  Returns:
    A list of the user's payment_methods.
  """

  return list(
      _account_db.get(email_address, {}).get("payment_methods", {}).values()
  )


def get_account_shipping_address(email_address: str) -> dict[str, Any]:
  """Gets the shipping address associated for the given account email address.

  Args:
    email_address: The account's email address.

  Returns:
    The account's shipping address.
  """

  return _account_db.get(email_address, {}).get("shipping_address", {})


def get_payment_method_by_alias(
    email_address: str, alias: str
) -> dict[str, Any] | None:
  """Returns the payment method for a given account and alias.

  Args:
    email_address: The account's email address.
    alias: The alias of the payment method to retrieve.

  Returns:
    The payment method for the given account and alias, or status:not_found.
  """

  payment_methods = list(
      filter(
          lambda payment_method: payment_method.get("alias").casefold()
          == alias.casefold(),
          get_account_payment_methods(email_address),
      )
  )
  if not payment_methods:
    return None
  return payment_methods[0]
