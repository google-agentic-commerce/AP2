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

import android.annotation.SuppressLint
import com.example.a2achatassistant.data.AdditionalInfo
import com.example.a2achatassistant.data.Cart
import com.example.a2achatassistant.data.CheckoutData
import com.example.a2achatassistant.data.CheckoutMandate
import com.example.a2achatassistant.data.Claim
import com.example.a2achatassistant.data.ClientMetadata
import com.example.a2achatassistant.data.CredentialMeta
import com.example.a2achatassistant.data.CredentialQuery
import com.example.a2achatassistant.data.DcqlQuery
import com.example.a2achatassistant.data.DelegateTransactionData
import com.example.a2achatassistant.data.DpcRequest
import com.example.a2achatassistant.data.MandateAmount
import com.example.a2achatassistant.data.Merchant
import com.example.a2achatassistant.data.PaymentInstrument
import com.example.a2achatassistant.data.PaymentMandate
import com.example.a2achatassistant.data.Request
import com.example.a2achatassistant.data.SdJwtFormatsSupported
import com.example.a2achatassistant.data.TransactionData
import com.example.a2achatassistant.data.VpFormatsSupported
import java.util.UUID
import kotlin.io.encoding.Base64
import kotlin.io.encoding.ExperimentalEncodingApi
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.encodeToJsonElement
import kotlinx.serialization.json.put

private val json = Json {
  ignoreUnknownKeys = true
  encodeDefaults = true
}

private const val DEMO_MERCHANT_ID = "merchant_1"
private const val DEMO_MERCHANT_NAME = "Generic Merchant"
private const val DEMO_MERCHANT_WEBSITE = "https://demo-merchant.example"
private const val DEMO_CREDENTIAL_ID = "b3f1c8a2-6d4e-4f9a-9e3d-8a7c2f1b9d34"

data class DpcRequestResult(
  val requestJson: String,
  val checkoutMandateJson: String,
  val paymentMandateJson: String,
)

@SuppressLint("DefaultLocale")
@OptIn(ExperimentalEncodingApi::class)
fun constructDPCRequest(
  checkoutData: CheckoutData,
  cart: Cart,
  merchantName: String,
): DpcRequestResult {
  val totalValue = checkoutData.amount

  val credId = "dpc_credential"
  val nonce = UUID.randomUUID().toString()

  val totalValueString = String.format("%.2f", totalValue)

  val tableRows = listOf(listOf(cart.itemLabel, "1", totalValueString, totalValueString))

  val additionalInfo =
    AdditionalInfo(
      title = "Please confirm your purchase details...",
      tableHeader = listOf("Name", "Qty", "Price", "Total"),
      tableRows = tableRows,
      footer = "Your total is $totalValueString",
    )

  val paymentDisplayTd =
    TransactionData(
      type = "payment_card",
      credentialIds = listOf(credId),
      transactionDataHashesAlg = listOf("sha-256"),
      merchantName = merchantName,
      amount = "USD ${String.format("%.2f", totalValue)}",
      additionalInfo = json.encodeToString(additionalInfo),
    )

  val agentJwk = buildJsonObject {
    put("kty", "EC")
    put("crv", "P-256")
    put("use", "sig")
    put("x", CryptoUtils.agentPublicKeyJwkX)
    put("y", CryptoUtils.agentPublicKeyJwkY)
  }
  val cnfObj = buildJsonObject { put("jwk", agentJwk) }

  val checkoutMandate =
    CheckoutMandate(
      checkoutJwt = checkoutData.checkoutJwt,
      checkoutHash = checkoutData.checkoutHash,
      cnf = cnfObj,
    )
  val paymentMandate =
    PaymentMandate(
      transactionId = checkoutData.checkoutHash,
      payee =
        Merchant(id = DEMO_MERCHANT_ID, name = DEMO_MERCHANT_NAME, website = DEMO_MERCHANT_WEBSITE),
      paymentAmount = MandateAmount(amount = checkoutData.amountCents, currency = checkoutData.currency),
      paymentInstrument = PaymentInstrument(type = "dpc", id = DEMO_CREDENTIAL_ID, description = "DPC \u00B7\u00B7\u00B7\u00B7 4444"),
      cnf = cnfObj,
    )

  val mandatesTd =
    DelegateTransactionData(
      type = "delegate",
      delegatePayload =
        listOf(json.encodeToJsonElement(checkoutMandate), json.encodeToJsonElement(paymentMandate)),
      credentialIds = listOf(credId),
      transactionDataHashesAlg = listOf("sha-256"),
    )

  val encodedPaymentDisplay =
    Base64.UrlSafe.encode(json.encodeToString(paymentDisplayTd).toByteArray(Charsets.UTF_8))
  val encodedMandates =
    Base64.UrlSafe.encode(json.encodeToString(mandatesTd).toByteArray(Charsets.UTF_8))
  val claims =
    listOf(
      Claim(path = listOf("card_last_four")),
      Claim(path = listOf("card_network_code")),
      Claim(path = listOf("credential_id")),
    )

  val credentialQuery =
    CredentialQuery(
      id = credId,
      format = "dc+sd-jwt",
      meta = CredentialMeta(vctValues = listOf("com.emvco.dpc")),
      claims = claims,
    )

  val dcqlQuery = DcqlQuery(credentials = listOf(credentialQuery))

  val clientMetadata =
    ClientMetadata(
      vpFormatsSupported =
        VpFormatsSupported(
          dcSdJwt =
            SdJwtFormatsSupported(
              sdJwtAlgValues = listOf("ES256"),
              kbJwtAlgValues = listOf("ES256"),
            )
        )
    )

  val dcRequest =
    Request(
      responseType = "vp_token",
      responseMode = "dc_api",
      nonce = nonce,
      dcqlQuery = dcqlQuery,
      transactionData = listOf(encodedPaymentDisplay, encodedMandates),
      clientMetadata = clientMetadata,
    )

  val dpcRequest = DpcRequest(protocol = "openid4vp-v1-unsigned", request = dcRequest)
  val finalJson = json.encodeToString(dpcRequest)
  return DpcRequestResult(
    requestJson = finalJson,
    checkoutMandateJson = json.encodeToString(checkoutMandate),
    paymentMandateJson = json.encodeToString(paymentMandate),
  )
}
