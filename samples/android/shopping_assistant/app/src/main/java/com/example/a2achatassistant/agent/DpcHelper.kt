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

import android.util.Log
import com.example.a2achatassistant.data.AdditionalInfo
import com.example.a2achatassistant.data.CartMandate
import com.example.a2achatassistant.data.Claim
import com.example.a2achatassistant.data.ClientMetadata
import com.example.a2achatassistant.data.CredentialQuery
import com.example.a2achatassistant.data.DcqlQuery
import com.example.a2achatassistant.data.DpcRequest
import com.example.a2achatassistant.data.MdocFormatsSupported
import com.example.a2achatassistant.data.Meta
import com.example.a2achatassistant.data.Request
import com.example.a2achatassistant.data.TransactionData
import com.example.a2achatassistant.data.VpFormatsSupported
import java.util.UUID
import kotlin.io.encoding.Base64
import kotlin.io.encoding.ExperimentalEncodingApi
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

private val json = Json { ignoreUnknownKeys = true }

@OptIn(ExperimentalEncodingApi::class)
fun constructDPCRequest(cartMandate: CartMandate, merchantName: String): String {
  val totalValue = cartMandate.contents.paymentRequest.details.total.amount.value

  val credId = "cred1"
  val mdocIdentifier = "mso_mdoc"
  // This nonce should ideally be generated securely for each transaction.
  val nonce = UUID.randomUUID().toString()

  val totalValueString = String.format("%.2f", totalValue)

  val tableRows =
    cartMandate.contents.paymentRequest.details.displayItems.map { item ->
      listOf(item.label, "1", item.amount.value.toString(), item.amount.value.toString())
    }

  for (row in tableRows) {
    Log.d("reemademo", "Row: $row")
  }

  val footerText = "Your total is $totalValueString"

  val additionalInfo =
    AdditionalInfo(
      title = "Please confirm your purchase details...",
      tableHeader = listOf("Name", "Qty", "Price", "Total"),
      tableRows = tableRows,
      footer = footerText,
    )

  // Build transaction_data payload.
  val transactionData =
    TransactionData(
      type = "payment_card",
      credentialIds = listOf(credId),
      transactionDataHashesAlg = listOf("sha-256"),
      merchantName = merchantName,
      amount = "US ${String.format("%.2f", totalValue)}",
      additionalInfo = json.encodeToString(additionalInfo), // Serialize the inner object
    )

  // Build the DCQL query to request specific credential claims.
  val claims =
    listOf(
      Claim(path = listOf("com.emvco.payment_card.1", "card_number")),
      Claim(path = listOf("com.emvco.payment_card.1", "holder_name")),
    )

  val credentialQuery =
    CredentialQuery(
      id = credId,
      format = mdocIdentifier,
      meta = Meta(doctypeValue = "com.emvco.payment_card"),
      claims = claims,
    )

  val dcqlQuery = DcqlQuery(credentials = listOf(credentialQuery))

  // Build client_metadata to specify supported formats.
  val mdocFormatsSupported =
    MdocFormatsSupported(
      issuerauthAlgValues = listOf(-7), // ES256
      deviceauthAlgValues = listOf(-7),
    )
  val clientMetadata =
    ClientMetadata(vpFormatsSupported = VpFormatsSupported(msoMdoc = mdocFormatsSupported))

  // Base64URL-encode the transaction_data JSON string.
  val transactionDataJsonString = json.encodeToString(transactionData)
  val encodedTransactionData =
    Base64.UrlSafe.encode(transactionDataJsonString.toByteArray(Charsets.UTF_8))

  // Build the final request object.
  val dcRequest =
    Request(
      responseType = "vp_token",
      responseMode = "dc_api",
      nonce = nonce,
      dcqlQuery = dcqlQuery,
      transactionData = listOf(encodedTransactionData),
      clientMetadata = clientMetadata,
    )

  val dpcRequest = DpcRequest(protocol = "openid4vp-v1-unsigned", request = dcRequest)

  // Serialize the final object to a string and return.
  return json.encodeToString(dpcRequest)
}
