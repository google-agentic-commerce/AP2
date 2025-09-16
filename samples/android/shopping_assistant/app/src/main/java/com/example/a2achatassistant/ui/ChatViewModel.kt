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
package com.example.a2achatassistant.ui

import android.app.Activity
import android.app.Application
import android.content.Context
import android.util.Log
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.a2achatassistant.agent.ChatRepository
import com.example.a2achatassistant.data.ChatMessage
import com.example.a2achatassistant.data.SenderRole
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

private const val TAG = "ChatViewModel"

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "settings")
private val AGENT_CARD_URL_KEY = stringPreferencesKey("agent_card_url")

data class ChatUiState(
  val messages: List<ChatMessage> = emptyList(),
  val isLoading: Boolean = false,
  val statusText: String = "",
)

class ChatViewModel(application: Application) : AndroidViewModel(application) {

  private val repository = ChatRepository(application)

  private val _uiState = MutableStateFlow(ChatUiState())
  val uiState = _uiState.asStateFlow()

  private val _agentCardUrl = MutableStateFlow("")
  val agentCardUrl = _agentCardUrl.asStateFlow()

  init {
    Log.i(TAG, "ChatViewModel initialized.")
    _uiState.update {
      it.copy(
        messages =
          listOf(
            ChatMessage(
              text =
                "Hello! I'm your shopping assistant. How can I help you today? Try asking 'I want to buy some shoes'.",
              sender = SenderRole.GEMINI,
            )
          )
      )
    }

    viewModelScope.launch {
      getApplication<Application>().dataStore.data.collect { preferences ->
        val url = preferences[AGENT_CARD_URL_KEY] ?: ""
        Log.d(TAG, "DataStore collected new URL: $url")
        _agentCardUrl.value = url
        if (url.isNotBlank()) {
          Log.d(TAG, "ViewModel launching repository initialization from URL: $url")
          // FIX: Call the new repository initialize method
          repository
            .initialize(url)
            .onFailure { error ->
              Log.w(TAG, "Repository initialization failed: ${error.message}")
              val errorMessage =
                ChatMessage(
                  text =
                    "Failed to connect to agent. Please check the URL and your network connection.",
                  sender = SenderRole.GEMINI,
                )
              _uiState.update { it.copy(messages = it.messages + errorMessage) }
            }
            .onSuccess {
              Log.i(TAG, "Repository initialization successful.")
              val successMessage =
                ChatMessage(
                  text = "Successfully connected to the agent.",
                  sender = SenderRole.GEMINI,
                )
              _uiState.update { it.copy(messages = it.messages + successMessage) }
            }
        } else {
          Log.d(TAG, "Agent card URL is blank.")
          val noteMessage =
            ChatMessage(
              text = "Note: Agent card URL is not set. Please configure it in the settings.",
              sender = SenderRole.GEMINI,
            )
          _uiState.update { it.copy(messages = it.messages + noteMessage) }
        }
      }
    }
  }

  fun setAgentCardUrl(url: String) {
    Log.d(TAG, "setAgentCardUrl called with url: $url")
    viewModelScope.launch {
      getApplication<Application>().dataStore.edit { settings ->
        settings[AGENT_CARD_URL_KEY] = url
      }
    }
  }

  fun sendMessage(userMessage: String, activity: Activity?) {
    Log.d(TAG, "sendMessage called with message: $userMessage")
    if (userMessage.isBlank()) {
      Log.d(TAG, "User message is blank, ignoring.")
      return
    }

    val userChatMessage = ChatMessage(text = userMessage, sender = SenderRole.USER)
    _uiState.update { it.copy(messages = it.messages + userChatMessage, isLoading = true) }

    viewModelScope.launch {
      // FIX: Pass the history from the repository, not the UI state
      val result =
        repository.getResponse(userMessage, activity) { newStatus ->
          _uiState.update { it.copy(statusText = newStatus) }
        }

      result
        .onSuccess { responseText ->
          Log.d(TAG, "Repository returned success: '$responseText'")
          val geminiMessage = ChatMessage(text = responseText, sender = SenderRole.GEMINI)
          _uiState.update { it.copy(messages = it.messages + geminiMessage, isLoading = false) }
        }
        .onFailure {
          Log.e(TAG, "Repository returned failure", it)
          val errorMessage =
            ChatMessage(
              text = "Sorry, an error occurred: ${it.message}",
              sender = SenderRole.GEMINI,
            )
          _uiState.update { it.copy(messages = it.messages + errorMessage, isLoading = false) }
        }
    }
  }
}
