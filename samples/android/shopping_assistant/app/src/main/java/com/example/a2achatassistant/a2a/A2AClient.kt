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
package com.example.a2achatassistant.a2a

import android.util.Log
import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.engine.cio.CIO
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.plugins.logging.LogLevel
import io.ktor.client.plugins.logging.Logger
import io.ktor.client.plugins.logging.Logging
import io.ktor.client.request.get
import io.ktor.client.request.headers
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.http.ContentType
import io.ktor.http.HttpHeaders
import io.ktor.http.contentType
import io.ktor.serialization.kotlinx.json.*
import java.util.UUID
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject

private const val TAG = "A2AClient"

class A2aClient(val name: String, val baseUrl: String, val agentCard: AgentCard? = null) {
  private val json = Json {
    prettyPrint = true
    isLenient = true
    ignoreUnknownKeys = true
    classDiscriminator = "kind"
    encodeDefaults = true
  }

  private val client =
    HttpClient(CIO) {
      install(ContentNegotiation) { json(json) }
      install(Logging) {
        logger =
          object : Logger {
            override fun log(message: String) {
              Log.d(TAG, "Ktor Log: $message")
            }
          }
        level = LogLevel.ALL
      }
    }

  /** Sends a pre-built A2A Message, wrapping it in a JSON-RPC request. */
  suspend fun sendMessage(message: Message): JsonObject {
    Log.d(TAG, "[$name] Preparing to send message: ${message.messageId}")
    try {
      val request = JsonRpcRequest(params = RpcParams(message = message))

      val response: JsonObject =
        client
          .post(baseUrl) {
            contentType(ContentType.Application.Json)
            headers {
              append(HttpHeaders.Accept, "*/*")
              append("X-A2A-Extensions", "https://github.com/google-agentic-commerce/ap2/v1")
            }
            setBody(request)
          }
          .body()

      Log.d(TAG, "[$name] Response received successfully: $response")
      return response
    } catch (e: Exception) {
      Log.e(TAG, "[$name] Failed to send data", e)
      throw e
    }
  }

  companion object {
    private val httpClient = HttpClient {
      install(ContentNegotiation) { json(Json { ignoreUnknownKeys = true }) }
    }

    suspend fun setUpClient(name: String, url: String): A2aClient {
      try {
        val agentCardUrl = "$url/.well-known/agent-card.json"
        Log.d(TAG, "Fetching agent card from: $agentCardUrl")
        val card: AgentCard = httpClient.get(agentCardUrl).body()
        return A2aClient(name, url, card)
      } catch (e: Exception) {
        Log.e(TAG, "Failed to fetch agent card", e)
        throw e
      }
    }
  }

  @Serializable
  data class JsonRpcRequest(
    val id: String = UUID.randomUUID().toString(),
    val jsonrpc: String = "2.0",
    val method: String = "message/send",
    val params: RpcParams,
  )

  @Serializable
  data class RpcParams(
    val configuration: RpcConfiguration = RpcConfiguration(),
    val message: Message,
  )

  @Serializable
  data class RpcConfiguration(
    val acceptedOutputModes: List<String> = emptyList(),
    val blocking: Boolean = true,
  )
}
