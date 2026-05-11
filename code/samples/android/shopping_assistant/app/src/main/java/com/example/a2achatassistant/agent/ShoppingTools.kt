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
import com.example.a2achatassistant.data.Cart
import com.example.a2achatassistant.data.CartWrapper
import com.example.a2achatassistant.data.CheckoutData
import com.example.a2achatassistant.data.CheckoutDataWrapper
import com.example.a2achatassistant.data.JsonRpcResponse
import com.example.a2achatassistant.data.Merchant
import com.example.a2achatassistant.data.ToolContext
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.json.JSONArray
import org.json.JSONObject
import org.multipaz.util.fromBase64Url
import org.multipaz.util.toBase64Url

@Serializable data class DpcResponse(val protocol: String? = null, val data: DpcData? = null)

@Serializable data class DpcData(@SerialName("vp_token") val vpToken: VpToken? = null)

@Serializable
data class VpToken(@SerialName("dpc_credential") val dpcCredential: List<String>? = null)

private const val TAG = "ShoppingTools"
private const val CP_URL = "http://localhost:8002/a2a/credentials_provider"

private val DEMO_MERCHANT =
  Merchant(id = "merchant_1", name = "Generic Merchant", website = "https://demo-merchant.example")

class ShoppingTools(
  context: Context,
  private val merchantAgent: A2aClient,
  private val cpAgent: A2aClient?,
) {

  private val credentialManager = CredentialManager.create(context)

  private val json = Json { ignoreUnknownKeys = true }

  companion object {
    suspend fun initiateShoppingTools(
      merchantAgentUrl: String,
      cpAgentUrl: String = CP_URL,
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

        var cpAgent: A2aClient? = null
        try {
          Log.d(TAG, "Fetching CP agent card from: $cpAgentUrl")
          val cpClient = A2aClient.setUpClient("cp_agent", cpAgentUrl)
          cpAgent =
            A2aClient(name = "cp_agent", baseUrl = cpAgentUrl, agentCard = cpClient.agentCard)
        } catch (e: Exception) {
          Log.w(TAG, "Warning: Could not fetch CP agent card, payment flow might fail.", e)
        }

        val tools = ShoppingTools(context, merchantAgent, cpAgent)
        return Result.success(tools)
      } catch (e: Exception) {
        Log.e(TAG, "FAILED: Could not fetch or parse merchant agent card.", e)
        return Result.failure(e)
      }
    }
  }

  suspend fun findProducts(shoppingIntent: String, toolContext: ToolContext): List<Cart> {
    Log.d(TAG, "Searching for products matching: '$shoppingIntent'")

    toolContext.state.shoppingContextId = "123"

    val message =
      A2aMessageBuilder()
        .addText("Find products that match the user's request.")
        .addData(key = "catalog_search", data = shoppingIntent)
        .setContextId("123")
        .build()
    val responseJson = merchantAgent.sendMessage(message)

    try {
      val rpcResponse = json.decodeFromJsonElement<JsonRpcResponse<ArtifactResult>>(responseJson)

      if (rpcResponse.error != null) {
        Log.e(TAG, "Merchant agent returned an error: ${rpcResponse.error.message}")
        return emptyList()
      }

      val result = rpcResponse.result ?: return emptyList()

      val carts = mutableListOf<Cart>()
      result.artifacts.mapNotNull { artifact ->
        val part = artifact.parts.firstOrNull { it.kind == "data" } ?: return@mapNotNull null
        try {
          val wrapper = json.decodeFromJsonElement<CartWrapper>(part.data)
          carts.add(wrapper.cart)
        } catch (_: Exception) {
          // Skip non-cart artifacts (e.g. risk_data)
        }
      }
      toolContext.state.productOptions = carts
      return carts
    } catch (e: Exception) {
      Log.e(TAG, "Failed to parse product search results", e)
    }
    return emptyList()
  }

  fun selectProduct(itemName: String, toolContext: ToolContext): Cart? {
    return toolContext.state.productOptions
      ?.find { it.itemLabel == itemName }
      ?.also { toolContext.state.selectedCart = it }
  }

  suspend fun createCheckout(toolContext: ToolContext): CheckoutData? {
    val cart =
      toolContext.state.selectedCart
        ?: run {
          Log.e(TAG, "No cart selected")
          return null
        }
    val contextId =
      toolContext.state.shoppingContextId
        ?: run {
          Log.e(TAG, "No shopping context ID")
          return null
        }

    Log.d(TAG, "Creating checkout for cart: ${cart.cartId}")
    val message =
      A2aMessageBuilder()
        .addText("Create a checkout for the selected cart.")
        .addData("cart_id", cart.cartId)
        .setContextId(contextId)
        .build()
    val responseJson = merchantAgent.sendMessage(message)

    return try {
      val rpcResponse = json.decodeFromJsonElement<JsonRpcResponse<ArtifactResult>>(responseJson)
      var checkoutData: CheckoutData? = null

      val result = rpcResponse.result
      if (result != null) {
        for (artifact in result.artifacts) {
          for (part in artifact.parts) {
            if (part.kind != "data") continue
            try {
              val wrapper = json.decodeFromJsonElement<CheckoutDataWrapper>(part.data)
              checkoutData = wrapper.checkout
            } catch (_: Exception) {
              // Not a checkout artifact
            }
          }
        }
      }
      if (checkoutData != null) {
        toolContext.state.checkoutData = checkoutData
        Log.i(TAG, "Checkout created: hash=${checkoutData.checkoutHash}")
      } else {
        Log.e(TAG, "Merchant did not return checkout data")
      }
      checkoutData
    } catch (e: Exception) {
      Log.e(TAG, "Failed to parse checkout response", e)
      null
    }
  }

  @OptIn(ExperimentalDigitalCredentialApi::class, kotlin.time.ExperimentalTime::class)
  suspend fun retrieveDpcOptions(toolContext: ToolContext, activity: Activity): PaymentResult {
    Log.d(TAG, "Starting DPC payment flow")

    val checkout =
      toolContext.state.checkoutData
        ?: return PaymentResult.Failure("No checkout data. Call create_checkout first.")

    val cart =
      toolContext.state.selectedCart
        ?: return PaymentResult.Failure("No cart selected for payment.")

    // 1. Construct the OpenId4VP request. Mandate payloads are included as
    //    transaction_data items. CMWallet embeds them into the DPC response
    //    as a KB-SD-JWT with selective mandate disclosures.
    val dpcResult = constructDPCRequest(checkout, cart, DEMO_MERCHANT.name)

    // 2. Invoke Credential Manager API
    val dpcResponseJson =
      invokeCredentialManager(dpcResult.requestJson, activity)
        ?: return PaymentResult.Failure("User cancelled the payment.")

    // 3. Parse DPC response and send mandates to merchant / CP.
    //    VP token from CMWallet:
    //      dpc_jwt~dpc_discs~~KB-SD-JWT~checkout_disc~payment_disc~
    //
    //    Presentation per verifier (selective disclosure on token 1):
    //      dpc_jwt~dpc_discs~~KB-SD-JWT~relevant_disc~agent_KB-JWT
    Log.i(TAG, "Parsing DPC response to extract mandates. Raw JSON: $dpcResponseJson")

    val response = json.decodeFromString<DpcResponse>(dpcResponseJson)
    val vpTokenStr =
      response.data?.vpToken?.dpcCredential?.firstOrNull()
        ?: return PaymentResult.Failure("Invalid DPC response format: missing dpc_credential")

    val validParts = vpTokenStr.split("~").filter { it.isNotBlank() }
    val jwtParts = validParts.filter { it.count { char -> char == '.' } == 2 }
    val disclosures = validParts.filter { !it.contains(".") }

    if (jwtParts.size < 2) {
      return PaymentResult.Failure("Expected at least Issuer and KB JWTs, got ${jwtParts.size}")
    }

    // Safely extract KB JWT payload using Multipaz Base64 extensions
    val kbJwt = jwtParts.last()
    val kbJwtParts = kbJwt.split(".")
    if (kbJwtParts.size != 3) {
      return PaymentResult.Failure("Invalid KB-JWT format")
    }
    val kbPayloadJsonStr = kbJwtParts[1].fromBase64Url().decodeToString()
    Log.i(TAG, "Extracted KB Payload: $kbPayloadJsonStr")

    val kbJwtIdx = validParts.indexOf(kbJwt)
    val dpcPrefixParts = validParts.subList(0, kbJwtIdx)
    val baseDpcString = dpcPrefixParts.joinToString("~", postfix = "~")

    val checkoutDisc =
      CryptoUtils.findMandateDisclosure(disclosures, CryptoUtils.CHECKOUT_MANDATE_VCT)
        ?: return PaymentResult.Failure("Missing checkout mandate disclosure")

    val paymentDisc =
      CryptoUtils.findMandateDisclosure(disclosures, CryptoUtils.PAYMENT_MANDATE_VCT)
        ?: return PaymentResult.Failure("Missing payment mandate disclosure")

    val checkoutToken1Prefix = "$kbJwt~$checkoutDisc~"
    val fullCheckoutPresentation =
      baseDpcString.trimEnd('~') + "~~" + checkoutToken1Prefix

    val paymentToken1Prefix = "$kbJwt~$paymentDisc~"
    val fullPaymentPresentation =
      baseDpcString.trimEnd('~') + "~~" + paymentToken1Prefix

    val tdDecoded =
      runCatching {
          val requestObj = JSONObject(dpcResult.requestJson).getJSONObject("request")
          val tdArray = requestObj.getJSONArray("transaction_data")
          val sb = StringBuilder()
          for (i in 0 until tdArray.length()) {
            val tdEnc = tdArray.getString(i)
            val tdJson = tdEnc.fromBase64Url().decodeToString()
            sb.appendLine("Item $i:")
            sb.appendLine(JSONObject(tdJson).toString(2))
          }
          sb.toString()
        }
        .getOrDefault("(parse error)")

    val dpcLogObj =
      JSONObject().apply {
        put("Transaction Data (decoded)", tdDecoded)
        put("Raw dSD-JWT Chain", vpTokenStr)
        put("Checkout Mandate → Merchant", dpcResult.checkoutMandateJson)
        put("Payment Mandate → Cred Provider", dpcResult.paymentMandateJson)
        put("Merchant Presentation (truncated)", fullCheckoutPresentation.take(400) + "…")
        put("CP Presentation (truncated)", fullPaymentPresentation.take(400) + "…")
      }
    toolContext.state.dpcLog = dpcLogObj.toString()

    Log.i(TAG, "Sending Payment Presentation to CP")
    val paymentMessage =
      A2aMessageBuilder()
        .addText("Verify Signed Payment Mandate")
        .addData(key = "ap2.mandates.PaymentMandateSdJwt", data = fullPaymentPresentation)
    cpAgent?.sendMessage(paymentMessage.build())
      ?: return PaymentResult.Failure("CP Agent is not connected")

    Log.i(TAG, "Sending Checkout Presentation to merchant")
    val checkoutMessage =
      A2aMessageBuilder()
        .addText("Finish the DPC flow with the checkout_mandate to complete the purchase.")
        .addData(key = "checkout_mandate", data = fullCheckoutPresentation)
    val checkoutResponseJson = merchantAgent.sendMessage(checkoutMessage.build())

    return try {
      val rpcResponse =
        json.decodeFromJsonElement<JsonRpcResponse<ArtifactResult>>(checkoutResponseJson)
      val result =
        rpcResponse.result ?: return PaymentResult.Failure("Missing result in final response")

      if (result.artifacts.isEmpty()) {
        Log.w(TAG, "Merchant agent did not return artifacts. Response: $checkoutResponseJson")
        return PaymentResult.Failure("Merchant agent did not return payment status.")
      }

      val artifact = result.artifacts.first()
      val part = artifact.parts.first { it.kind == "data" }
      val paymentStatus = part.data.jsonObject["payment_status"]!!.jsonPrimitive.content
      Log.i(TAG, "Payment validation status: $paymentStatus")
      if (paymentStatus == "SUCCESS") PaymentResult.Success
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
}

sealed class PaymentResult {
  data object Success : PaymentResult()

  data class OtpRequired(val message: String) : PaymentResult()

  data class Failure(val message: String) : PaymentResult()
}
