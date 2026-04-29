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

@Serializable
data class JsonRpcResponse<T>(
  val id: String,
  val jsonrpc: String,
  val result: T? = null,
  val error: JsonRpcError? = null,
)

@Serializable data class JsonRpcError(val code: Int, val message: String)

@Serializable data class ArtifactResult(val artifacts: List<Artifact> = emptyList())

// endregion

// region Core Data Models

@Serializable
data class Artifact(@SerialName("artifactId") val artifactId: String, val parts: List<ArtifactPart>)

@Serializable data class ArtifactPart(val data: JsonElement, val kind: String)

// endregion

// region AP2 Models – mirrors ap2.models.cart.Cart

@Serializable data class CartWrapper(@SerialName("ap2.cart") val cart: Cart)

@Serializable
data class Cart(
  @SerialName("cart_id") val cartId: String,
  @SerialName("item_label") val itemLabel: String,
  val amount: Double,
  val currency: String = "USD",
)

// endregion

// region AP2 Generated Mandate Models

@Serializable
data class CheckoutMandate(
  val vct: String = "mandate.checkout.1",
  @SerialName("checkout_jwt") val checkoutJwt: String,
  @SerialName("checkout_hash") val checkoutHash: String,
  val cnf: JsonElement? = null,
)

@Serializable
data class PaymentMandate(
  val vct: String = "mandate.payment.1",
  @SerialName("transaction_id") val transactionId: String,
  val payee: Merchant,
  @SerialName("payment_amount") val paymentAmount: MandateAmount,
  @SerialName("payment_instrument") val paymentInstrument: PaymentInstrument,
  val cnf: JsonElement? = null,
)

@Serializable data class Merchant(val id: String, val name: String, val website: String)

@Serializable data class MandateAmount(val amount: Int, val currency: String)

@Serializable
data class PaymentInstrument(
  val type: String,
  @SerialName("credential_id") val credentialId: String? = null,
  val id: String? = null,
  val description: String? = null,
)

// endregion

// region Checkout Data (from merchant's create_checkout response)

@Serializable
data class CheckoutData(
  @SerialName("cart_id") val cartId: String,
  @SerialName("checkout_jwt") val checkoutJwt: String,
  @SerialName("checkout_hash") val checkoutHash: String,
  @SerialName("item_label") val itemLabel: String,
  val amount: Double,
  @SerialName("amount_cents") val amountCents: Int,
  val currency: String = "USD",
)

@Serializable data class CheckoutDataWrapper(@SerialName("ap2.checkout") val checkout: CheckoutData)

// endregion

// region DPC Types

@Serializable data class DpcOptions(@SerialName("dpc_request") val openId4VpJson: String)

// endregion

// region Conversation State

@Serializable
data class ConversationToolState(
  var dpcOptions: DpcOptions? = null,
  var productOptions: List<Cart>? = listOf(),
  var selectedCart: Cart? = null,
  var checkoutData: CheckoutData? = null,
  var shippingAddress: ContactAddress? = null,
  var shoppingContextId: String? = null,
  var dpcLog: String? = null,
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

// endregion
