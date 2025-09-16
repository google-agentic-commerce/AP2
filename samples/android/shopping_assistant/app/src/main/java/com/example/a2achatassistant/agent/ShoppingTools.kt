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
package com.example.a2achatassistant.agent

import android.app.Activity
import android.content.Context
import android.util.Log
import androidx.credentials.CredentialManager
import androidx.credentials.DigitalCredential
import androidx.credentials.ExperimentalDigitalCredentialApi
import androidx.credentials.GetCredentialRequest
import androidx.credentials.GetDigitalCredentialOption
import com.example.a2achatassistant.a2a.A2aClient
import com.example.a2achatassistant.a2a.A2aMessageBuilder
import com.example.a2achatassistant.data.ArtifactResult
import com.example.a2achatassistant.data.CartMandate
import com.example.a2achatassistant.data.ContactAddress
import com.example.a2achatassistant.data.FullCartMandateWrapper
import com.example.a2achatassistant.data.IntentMandate
import com.example.a2achatassistant.data.JsonRpcResponse
import com.example.a2achatassistant.data.ToolContext
import kotlin.time.Duration.Companion.days
import kotlinx.datetime.Clock
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.jsonObject
import org.json.JSONArray
import org.json.JSONObject

private const val TAG = "ShoppingTools"

class ShoppingTools(context: Context, private val merchantAgent: A2aClient) {

  private val credentialManager = CredentialManager.create(context)

  private val json = Json { ignoreUnknownKeys = true }

  companion object {
    suspend fun initiateShoppingTools(
      merchantAgentUrl: String,
      context: Context,
    ): Result<ShoppingTools> {
      Log.d(TAG, "Fetching agent card from: $merchantAgentUrl")

      try {
        val client = A2aClient.setUpClient("merchant_agent", merchantAgentUrl)
        Log.i(TAG, "SUCCESS: Agent Card for '${client.agentCard?.name}' loaded.")

        val merchantAgent =
          A2aClient(
            name = "merchant_agent",
            baseUrl = merchantAgentUrl,
            agentCard = client.agentCard,
          )

        val tools = ShoppingTools(context, merchantAgent)
        return Result.success(tools)
      } catch (e: Exception) {
        Log.e(TAG, "FAILED: Could not fetch or parse agent card.", e)
        return Result.failure(e)
      }
    }
  }

  suspend fun findProducts(
    naturalLanguageDescription: String,
    toolContext: ToolContext,
  ): List<CartMandate> {
    Log.d(TAG, "Searching for products matching: '$naturalLanguageDescription'")
    val intentMandate = createIntentMandate(naturalLanguageDescription)

    toolContext.state.shoppingContextId = "123"
    toolContext.state.intentMandate = intentMandate

    val message =
      A2aMessageBuilder()
        .addText("Find products that match the user's IntentMandate.")
        .addData(key = "ap2.mandates.IntentMandate", data = intentMandate)
        .setContextId("123")
        .build()
    val responseJson = merchantAgent.sendMessage(message)

    try {
      val rpcResponse = json.decodeFromJsonElement<JsonRpcResponse<ArtifactResult>>(responseJson)
      val listCartMandate = mutableListOf<CartMandate>()
      rpcResponse.result.artifacts.mapNotNull { artifact ->
        // Every artifact is a cart mandate
        val part = artifact.parts.firstOrNull { it.kind == "data" } ?: return@mapNotNull null
        // Directly deserialize into the rich Cart object
        val wrapper = json.decodeFromJsonElement<FullCartMandateWrapper>(part.data)
        listCartMandate.add(wrapper.cartMandate)
      }
      toolContext.state.productOptions = listCartMandate
      return listCartMandate
    } catch (e: Exception) {
      Log.e(TAG, "Failed to parse product search results", e)
    }
    return emptyList()
  }

  suspend fun updateCart(
    cartId: String,
    shippingAddress: ContactAddress,
    toolContext: ToolContext,
  ): CartMandate? {
    Log.d(TAG, "Updating cart '$cartId' with new shipping address")

    if (toolContext.state.shoppingContextId == null) {
      return null
    }

    val message =
      A2aMessageBuilder()
        .addText("Update the cart with the user's shipping address.")
        .setContextId(contextId = toolContext.state.shoppingContextId!!)
        .addData("cart_id", cartId)
        .addData("shipping_address", shippingAddress)
        .build()
    val responseJson = merchantAgent.sendMessage(message)

    return try {
      val rpcResponse = json.decodeFromJsonElement<JsonRpcResponse<ArtifactResult>>(responseJson)
      val artifact = rpcResponse.result.artifacts.first()
      val part = artifact.parts.first { it.kind == "data" }
      val wrapper = json.decodeFromJsonElement<FullCartMandateWrapper>(part.data)

      toolContext.state.cartMandate = wrapper.cartMandate
      toolContext.state.shippingAddress = shippingAddress
      Log.i(TAG, "Cart updated successfully")
      wrapper.cartMandate
    } catch (e: Exception) {
      Log.e(TAG, "Failed to parse updated cart", e)
      null
    }
  }

  // New DPC-based payment flow methods
  @OptIn(ExperimentalDigitalCredentialApi::class)
  suspend fun retrieveDpcOptions(toolContext: ToolContext, activity: Activity): PaymentResult {
    Log.d(TAG, "Starting DPC payment flow")

    val cart =
      toolContext.state.cartMandate ?: return PaymentResult.Failure("No cart selected for payment.")

    // 1. Construct the OpenId4VP request
    val dpcRequestJson =
      constructDPCRequest(cartMandate = cart, merchantName = cart.contents.merchantName)

    // 2. Invoke Credential Manager API and get a token
    val token =
      invokeCredentialManager(dpcRequestJson, activity)
        ?: return PaymentResult.Failure("User cancelled the payment.")
    toolContext.state.signedPaymentMandate = token // Re-use this field to hold the token

    // 3. Send the token back to the merchant for validation
    Log.i(TAG, "Sending DPC response to merchant for validation")
    val sendDpcResponseMessage =
      A2aMessageBuilder()
        .addText("Validate the Digital Payment Credentials (DPC) response")
        .addData(key = "dpc_response", data = token)
        .build()
    val finalResponseJson = merchantAgent.sendMessage(sendDpcResponseMessage)

    return try {
      val rpcResponse =
        json.decodeFromJsonElement<JsonRpcResponse<ArtifactResult>>(finalResponseJson)
      val artifact = rpcResponse.result.artifacts.first()
      val part = artifact.parts.first { it.kind == "data" }
      val paymentStatus = part.data.jsonObject["payment_status"]!!.toString()
      Log.i(TAG, "Payment validation status: $paymentStatus")
      if (paymentStatus == "\"SUCCESS\"") PaymentResult.Success
      else PaymentResult.Failure("Payment validation failed.")
    } catch (e: Exception) {
      Log.e(TAG, "Failed to parse final payment validation response", e)
      PaymentResult.Failure("An error occurred during final payment validation.")
    }
  }

  @OptIn(ExperimentalDigitalCredentialApi::class)
  private suspend fun invokeCredentialManager(dpcRequestJson: String, activity: Activity): String? {
    Log.d(TAG, "Invoking Credential Manager")
    val jsonFromMerchant = JSONObject(dpcRequestJson)

    val protocol = jsonFromMerchant.getString("protocol")
    val data = jsonFromMerchant.getJSONObject("request")

    val request =
      JSONObject().apply {
        put("protocol", protocol)
        put("data", data)
      }

    val requests = JSONObject().apply { put("requests", JSONArray().apply { put(request) }) }

    val reqStr = requests.toString()
    Log.d(TAG, "Invoking DPC with request: $reqStr")

    val digitalCredentialOption = GetDigitalCredentialOption(reqStr)
    return try {
      val credential =
        credentialManager.getCredential(
          activity,
          GetCredentialRequest(listOf(digitalCredentialOption)),
        )
      val dpcCredential = credential.credential as DigitalCredential
      Log.i(TAG, "Credential Manager returned a token.")
      dpcCredential.credentialJson
    } catch (e: Exception) {
      Log.e(TAG, "Credential Manager failed or was cancelled", e)
      null
    }
  }

  private fun createIntentMandate(naturalLanguageDescription: String): IntentMandate {
    val expiry = (Clock.System.now() + 1.days).toString()
    return IntentMandate(
      userPromptRequired = true,
      naturalLanguageDescription = naturalLanguageDescription,
      intentExpiry = expiry,
    )
  }
}

sealed class PaymentResult {
  object Success : PaymentResult()

  data class OtpRequired(val message: String) : PaymentResult()

  data class Failure(val message: String) : PaymentResult()
}
