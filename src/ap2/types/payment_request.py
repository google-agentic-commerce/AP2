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

"""Objects from the W3C Payment Request API.

The Agent Payments Protocol utilizes several objects from this API.

There is no published python package for this API, so we define them here.

Specification:
https://www.w3.org/TR/payment-request/
"""

from typing import Any, Dict, Optional

from ap2.types.contact_picker import ContactAddress
from pydantic import BaseModel
from pydantic import Field

PAYMENT_METHOD_DATA_DATA_KEY = "payment_request.PaymentMethodData"


class PaymentCurrencyAmount(BaseModel):
  """A PaymentCurrencyAmount is used to supply monetary amounts.

  Specification:
  https://www.w3.org/TR/payment-request/#dom-paymentcurrencyamount
  """

  currency: str = Field(
      ..., description="The three-letter ISO 4217 currency code."
  )
  value: float = Field(..., description="The monetary value.")


class PaymentItem(BaseModel):
  """An item for purchase and the value asked for it.

  Specification:
  https://www.w3.org/TR/payment-request/#dom-paymentitem
  """

  label: str = Field(
      ..., description="A human-readable description of the item."
  )
  amount: PaymentCurrencyAmount = Field(
      ..., description="The monetary amount of the item."
  )
  pending: Optional[bool] = Field(
      None, description="If true, indicates the amount is not final."
  )
  refund_period: int = Field(
      30, description="The refund duration for this item, in days."
  )


class PaymentShippingOption(BaseModel):
  """Describes a shipping option.

  Specification:
  https://www.w3.org/TR/payment-request/#dom-paymentshippingoption
  """

  id: str = Field(
      ..., description="A uniqueidentifier for the shipping option."
  )
  label: str = Field(
      ..., description="A human-readable description of the shipping option."
  )
  amount: PaymentCurrencyAmount = Field(
      ..., description="The cost of this shipping option."
  )
  selected: Optional[bool] = Field(
      False, description="If true, indicates this as the default option."
  )


class PaymentOptions(BaseModel):
  """Information about the eligible payment options for the payment request.

  Specification:
  https://www.w3.org/TR/payment-request/#dom-paymentoptions
  """

  request_payer_name: Optional[bool] = Field(
      False, description="Indicates if the payer's name should be collected."
  )
  request_payer_email: Optional[bool] = Field(
      False, description="Indicates if the payer's email should be collected."
  )
  request_payer_phone: Optional[bool] = Field(
      False,
      description="Indicates if the payer's phone number should be collected.",
  )
  request_shipping: Optional[bool] = Field(
      True,
      description=(
          "Indicates if the payer's shipping address should be collected."
      ),
  )
  shipping_type: Optional[str] = Field(
      None, description="Can be `shipping`, `delivery`, or `pickup`."
  )


class PaymentMethodData(BaseModel):
  """Indicates a payment method and associated data specific to the method.

  For example:
  - A card may have a processing fee if it is used.
  - A loyalty card may offer a discount on the purchase.

  Specification:
  https://www.w3.org/TR/payment-request/#dom-paymentmethoddata
  """

  supported_methods: str = Field(
      ..., description="A string identifying the payment method."
  )
  data: Optional[Dict[str, Any]] = Field(
      default_factory=dict, description="Payment method specific details."
  )


class PaymentDetailsModifier(BaseModel):
  """Provides details that modify the payment details based on a payment method.

  Specification:
  https://www.w3.org/TR/payment-request/#dom-paymentdetailsmodifier
  """

  supported_methods: str = Field(
      ...,
      description="The payment method ID that this modifier applies to.",
  )
  total: Optional[PaymentItem] = Field(
      None,
      description="A PaymentItem value that overrides the original item total.",
  )
  additional_display_items: Optional[list[PaymentItem]] = Field(
      None,
      description="Additional PaymentItems applicable for this payment method.",
  )
  data: Optional[Any] = Field(
      None, description="Payment method specific data for the modifier."
  )


class PaymentDetailsInit(BaseModel):
  """Contains the details of the payment being requested.

  Specification:
  https://www.w3.org/TR/payment-request/#dom-paymentdetailsinit
  """

  id: str = Field(
      ..., description="A unique identifier for the payment request."
  )
  display_items: list[PaymentItem] = Field(
      ..., description="A list of payment items to be displayed to the user."
  )
  shipping_options: Optional[list[PaymentShippingOption]] = Field(
      None,
      description="A list of available shipping options.",
  )
  modifiers: Optional[list[PaymentDetailsModifier]] = Field(
      None,
      description="A list of price modifiers for particular payment methods.",
  )
  total: PaymentItem = Field(..., description="The total payment amount.")


class PaymentRequest(BaseModel):
  """A request for payment.

  Specification:
  https://www.w3.org/TR/payment-request/#paymentrequest-interface
  """

  method_data: list[PaymentMethodData] = Field(
      ..., description="A list of supported payment methods."
  )
  details: PaymentDetailsInit = Field(
      ..., description="The financial details of the transaction."
  )
  options: Optional[PaymentOptions] = None

  shipping_address: Optional[ContactAddress] = Field(
      None, description="The user's provided shipping address."
  )


class PaymentResponse(BaseModel):
  """Indicates a user has chosen a payment method & approved a payment request.

  Specification:
  https://www.w3.org/TR/payment-request/#paymentresponse-interface
  """

  request_id: str = Field(
      ..., description="The unique ID from the original PaymentRequest."
  )
  method_name: str = Field(
      ..., description="The payment method chosen by the user."
  )
  details: Optional[Dict[str, Any]] = Field(
      None,
      description=(
          "A dictionary generated by a payment method that a merchant can use"
          "to process a transaction. The contents will depend upon the payment"
          "method."
      ),
  )
  shipping_address: Optional[ContactAddress] = None
  shipping_option: Optional[PaymentShippingOption] = None
  payer_name: Optional[str] = None
  payer_email: Optional[str] = None
  payer_phone: Optional[str] = None
