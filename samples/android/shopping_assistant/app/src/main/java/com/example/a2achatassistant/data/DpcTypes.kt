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

// Data classes for the DPC request structure
@Serializable data class DpcRequest(val protocol: String, val request: Request)

@Serializable
data class Request(
  @SerialName("response_type") val responseType: String,
  @SerialName("response_mode") val responseMode: String,
  val nonce: String,
  @SerialName("dcql_query") val dcqlQuery: DcqlQuery,
  @SerialName("transaction_data") val transactionData: List<String>,
  @SerialName("client_metadata") val clientMetadata: ClientMetadata? = null,
)

@Serializable data class DcqlQuery(val credentials: List<CredentialQuery>)

@Serializable
data class CredentialQuery(
  val id: String,
  val format: String,
  val meta: Meta,
  val claims: List<Claim>,
)

@Serializable data class Meta(@SerialName("doctype_value") val doctypeValue: String)

@Serializable data class Claim(val path: List<String>)

@Serializable
data class ClientMetadata(
  @SerialName("vp_formats_supported") val vpFormatsSupported: VpFormatsSupported
)

@Serializable
data class VpFormatsSupported(@SerialName("mso_mdoc") val msoMdoc: MdocFormatsSupported)

@Serializable
data class MdocFormatsSupported(
  @SerialName("issuerauth_alg_values") val issuerauthAlgValues: List<Int>,
  @SerialName("deviceauth_alg_values") val deviceauthAlgValues: List<Int>,
)

// Data classes for transaction_data payload
@Serializable
data class TransactionData(
  val type: String,
  @SerialName("credential_ids") val credentialIds: List<String>,
  @SerialName("transaction_data_hashes_alg") val transactionDataHashesAlg: List<String>,
  @SerialName("merchant_name") val merchantName: String,
  val amount: String,
  @SerialName("additional_info") val additionalInfo: String, // This will be a JSON string
)

@Serializable
data class AdditionalInfo(
  val title: String,
  val tableHeader: List<String>,
  val tableRows: List<List<String>>,
  val footer: String,
)
