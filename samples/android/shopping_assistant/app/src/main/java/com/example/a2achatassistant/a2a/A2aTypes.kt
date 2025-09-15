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

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

/** Represents the role of the message sender. */
@Serializable
enum class Role {
  @SerialName("agent") AGENT,
  @SerialName("user") USER,
}

/**
 * A sealed interface for the different types of content a message part can have. The
 * `classDiscriminator` in the Json configuration will automatically add a "kind" property during
 * serialization based on the @SerialName of the subclass.
 */
@Serializable sealed interface Part

@Serializable @SerialName("text") data class TextPart(val text: String) : Part

@Serializable @SerialName("data") data class DataPart(val data: JsonElement) : Part

/** The main message container for A2A communication. */
@Serializable
data class Message(
  val kind: String = "message",
  @SerialName("messageId") val messageId: String,
  @SerialName("contextId") val contextId: String? = null,
  val parts: List<Part>,
  val role: Role,
)

@Serializable
data class AgentCard(
  val name: String,
  val description: String,
  val url: String,
  val skills: List<Skill>,
)

@Serializable data class Skill(val id: String, val name: String, val description: String)
