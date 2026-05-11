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

import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import org.multipaz.crypto.Algorithm
import org.multipaz.crypto.Crypto
import org.multipaz.crypto.EcCurve
import org.multipaz.crypto.EcPrivateKey
import org.multipaz.crypto.EcPublicKeyDoubleCoordinate
import org.multipaz.util.fromBase64Url
import org.multipaz.util.toBase64Url

/** Utility functions for cryptography and SD-JWT handling. */
object CryptoUtils {
  const val CHECKOUT_MANDATE_VCT = "mandate.checkout.1"
  const val PAYMENT_MANDATE_VCT = "mandate.payment.1"

  // Later we will use android keystore API to generate the key pair.
  val agentPrivateKey: EcPrivateKey by lazy {
    runBlocking { Crypto.createEcPrivateKey(EcCurve.P256) }
  }

  val agentPublicKeyJwkX: String by lazy {
    val pub = agentPrivateKey.publicKey as EcPublicKeyDoubleCoordinate
    pub.x.toBase64Url()
  }

  val agentPublicKeyJwkY: String by lazy {
    val pub = agentPrivateKey.publicKey as EcPublicKeyDoubleCoordinate
    pub.y.toBase64Url()
  }

  fun findMandateDisclosure(disclosures: List<String>, expectedVct: String): String? {
    for (disclosure in disclosures) {
      try {
        val decoded = disclosure.fromBase64Url().decodeToString()
        val array = JSONArray(decoded)

        if (array.length() >= 2) {
          val valueIndex = if (array.length() == 2) 1 else 2
          val jsonObject =
            when (val value = array.get(valueIndex)) {
              is String -> runCatching { JSONObject(value) }.getOrNull()
              is JSONObject -> value
              else -> null
            }

          if (jsonObject?.optString("vct") == expectedVct) {
            return disclosure
          }
        }
      } catch (_: Exception) {
        // Ignore non-mandate or malformed disclosures
      }
    }
    return null
  }

  fun createJWTES256(headerJson: String, payloadJson: String, privateKey: EcPrivateKey): String {
    val headerB64 = headerJson.encodeToByteArray().toBase64Url()
    val payloadB64 = payloadJson.encodeToByteArray().toBase64Url()
    val dataToSign = "$headerB64.$payloadB64".encodeToByteArray()
    val sig = runBlocking { Crypto.sign(privateKey, Algorithm.ES256, dataToSign) }
    val rawSignature = sig.r + sig.s
    return "$headerB64.$payloadB64.${rawSignature.toBase64Url()}"
  }

  fun ByteArray.toBase64UrlNoPadding(): String {
    return toBase64Url()
  }
}
