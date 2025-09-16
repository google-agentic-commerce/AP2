/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
 * in compliance with the License. You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software distributed under the License
 * is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
 * or implied. See the License for the specific language governing permissions and limitations under
 * the License.
 */
package com.example.a2achatassistant.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

// region Generic Response Wrappers

@Serializable data class JsonRpcResponse<T>(val id: String, val jsonrpc: String, val result: T)

@Serializable data class ArtifactResult(val artifacts: List<Artifact>)

// endregion

// region Core Data Models

@Serializable
data class Artifact(
  @SerialName("artifactId") val artifactId: String,
  val parts: List<ArtifactPart>,
)

@Serializable data class ArtifactPart(val data: JsonElement, val kind: String)

@Serializable
data class FullCartMandateWrapper(
  @SerialName("ap2.mandates.CartMandate") val cartMandate: CartMandate
)

@Serializable
data class CartMandate(
  val contents: CartContents,
  // FIX: Make this nullable to match the server response
  @SerialName("merchant_authorization") val merchantAuthorization: String?,
)

@Serializable
data class CartContents(
  val id: String,
  @SerialName("user_cart_confirmation_required") val user_cart_confirmation_required: Boolean,
  @SerialName("payment_request") val paymentRequest: PaymentRequestDetails,
  @SerialName("cart_expiry") val cartExpiry: String,
  @SerialName("merchant_name") val merchantName: String,
)

@Serializable
data class PaymentRequestDetails(
  @SerialName("method_data") val methodData: List<PaymentMethodDetails>,
  val details: PaymentDetails,
  val options: PaymentOptions,
  @SerialName("shipping_address") val shippingAddress: ShippingAddress? = null,
)

@Serializable
data class ShippingAddress(
  val city: String?,
  val country: String?,
  @SerialName("address_line") val addressLine: List<String>?,
  @SerialName("postal_code") val postalCode: String?,
  val recipient: String? = null,
  val organization: String? = null,
  val phone: String? = null,
  val region: String? = null,
  @SerialName("sorting_code") val sortingCode: String? = null,
  @SerialName("dependent_locality") val dependentLocality: String? = null,
)

@Serializable
data class PaymentMethodDetails(
  @SerialName("supported_methods") val supportedMethods: String,
  val data: PaymentMethodDataDetails?,
)

@Serializable
data class PaymentMethodDataDetails(
  @SerialName("payment_processor_url") val paymentProcessorUrl: String? = null,
  val network: List<String>,
  @SerialName("cardholder_name") val cardholderName: String? = null,
)

@Serializable
data class PaymentDetails(
  val id: String,
  @SerialName("display_items") val displayItems: List<DisplayItem>,
  @SerialName("shipping_options") val shippingOptions: List<ShippingOption>? = null,
  val modifiers: JsonElement? = null,
  val total: DisplayItem,
)

@Serializable
data class DisplayItem(
  val label: String,
  val amount: Amount,
  val pending: JsonElement? = null,
  @SerialName("refund_period") val refundPeriod: Int? = null,
)

@Serializable data class Amount(val currency: String, val value: Double)

@Serializable
data class ShippingOption(
  val id: String,
  val label: String,
  val amount: Amount,
  val selected: Boolean,
)

@Serializable
data class PaymentOptions(
  @SerialName("request_payer_name") val requestPayerName: Boolean,
  @SerialName("request_payer_email") val requestPayerEmail: Boolean,
  @SerialName("request_payer_phone") val requestPayerPhone: Boolean,
  @SerialName("request_shipping") val requestShipping: Boolean,
  @SerialName("shipping_type") val shippingType: JsonElement? = null,
)

@Serializable data class PaymentMandate(val paymentMandateId: String)

@Serializable
data class IntentMandate(
  @SerialName("user_prompt_required") val userPromptRequired: Boolean = true,
  @SerialName("natural_language_description") val naturalLanguageDescription: String,
  @SerialName("merchants") val merchants: List<String>? = null,
  @SerialName("skus") val skus: List<String>? = null,
  @SerialName("intent_expiry") val intentExpiry: String,
)

@Serializable data class DpcOptions(@SerialName("dpc_request") val openId4VpJson: String)

@Serializable data class DpcRequestOptions(@SerialName("cart_id") val cartId: String)

@Serializable
data class ConversationToolState(
  // New DPC flow state
  var dpcOptions: DpcOptions? = null,

  // Original flow state
  var productOptions: List<CartMandate>? = listOf(),
  var cartMandate: CartMandate? = null,
  var shippingAddress: ContactAddress? = null,
  var paymentMethodAlias: String? = null,
  var paymentMandate: PaymentMandate? = null,
  var signedPaymentMandate: String? = null,
  var shoppingContextId: String? = null,
  var intentMandate: IntentMandate? = null,
)

class ToolContext {
  val state = ConversationToolState()
}

@Serializable
data class ContactAddress(
  val streetAddress: String,
  val city: String,
  val state: String,
  val zipCode: String,
)
