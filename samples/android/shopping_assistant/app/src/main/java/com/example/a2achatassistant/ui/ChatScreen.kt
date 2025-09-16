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
import android.util.Log
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.rounded.AutoAwesome
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.example.a2achatassistant.data.ChatMessage
import com.example.a2achatassistant.data.SenderRole
import kotlinx.coroutines.launch

private const val TAG = "ChatScreen"

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(viewModel: ChatViewModel, onSettingsClicked: () -> Unit) {
  Log.d(TAG, "ChatScreen recomposed")
  val uiState by viewModel.uiState.collectAsState()
  var inputText by remember { mutableStateOf("") }
  val listState = rememberLazyListState()
  val coroutineScope = rememberCoroutineScope()

  val context = LocalContext.current
  val activity = context as? Activity // nullable in case it’s not an Activity

  Scaffold(
    topBar = {
      TopAppBar(
        title = {
          Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(
              imageVector = Icons.Default.AutoAwesome,
              contentDescription = "App Icon",
              tint = MaterialTheme.colorScheme.primary,
            )
            Spacer(modifier = Modifier.width(8.dp))
            Column {
              Text("A2A Chat Assistant", fontWeight = FontWeight.Bold)
              Text(
                "Demonstrating Conceptual Agent Routing",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
              )
            }
          }
        },
        actions = {
          IconButton(
            onClick = {
              Log.d(TAG, "Settings icon clicked")
              onSettingsClicked()
            }
          ) {
            Icon(imageVector = Icons.Default.Settings, contentDescription = "Settings")
          }
        },
        colors =
          TopAppBarDefaults.topAppBarColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
          ),
      )
    },
    bottomBar = {
      ChatInputFooter(
        value = inputText,
        onValueChange = {
          // Log.d(TAG, "Input text changed: $it")
          inputText = it
        },
        onSend = {
          Log.d(TAG, "Send button clicked with input: $inputText")
          viewModel.sendMessage(inputText, activity)
          inputText = ""
        },
        isLoading = uiState.isLoading,
        // FIX: Pass the status text to the footer
        statusText = uiState.statusText,
      )
    },
  ) { paddingValues ->
    Column(modifier = Modifier.fillMaxSize().padding(paddingValues)) {
      LazyColumn(
        state = listState,
        modifier = Modifier.weight(1f).padding(horizontal = 8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
        contentPadding = PaddingValues(vertical = 8.dp),
      ) {
        items(uiState.messages) { message -> ChatMessageItem(message) }
        if (uiState.isLoading) {
          Log.d(TAG, "Displaying thinking indicator")
          item { ThinkingIndicator() }
        }
      }

      // Auto-scroll to the latest message
      LaunchedEffect(uiState.messages.size, uiState.isLoading) {
        Log.d(TAG, "LaunchedEffect triggered for scroll")
        coroutineScope.launch {
          listState.animateScrollToItem(listState.layoutInfo.totalItemsCount)
        }
      }
    }
  }
}

@Composable
fun ChatMessageItem(message: ChatMessage) {
  Log.d(TAG, "ChatMessageItem recomposed for message: ${message.text}")
  val alignment =
    if (message.sender == SenderRole.USER) {
      Log.d(TAG, "Message from USER, aligning to end")
      Alignment.CenterEnd
    } else {
      Log.d(TAG, "Message from other, aligning to start")
      Alignment.CenterStart
    }
  val backgroundColor =
    when (message.sender) {
      SenderRole.USER -> {
        Log.d(TAG, "Message sender USER, using primaryContainer color")
        MaterialTheme.colorScheme.primaryContainer
      }
      SenderRole.GEMINI -> {
        Log.d(TAG, "Message sender GEMINI, using secondaryContainer color")
        MaterialTheme.colorScheme.secondaryContainer
      }
      SenderRole.AGENT -> {
        Log.d(TAG, "Message sender AGENT, using tertiaryContainer color")
        MaterialTheme.colorScheme.tertiaryContainer
      }
      else -> {
        Log.d(TAG, "Message sender UNKNOWN, using transparent color")
        Color.Transparent
      }
    }
  val icon =
    when (message.sender) {
      SenderRole.USER -> {
        Log.d(TAG, "Message sender USER, using Person icon")
        Icons.Default.Person
      }
      SenderRole.GEMINI -> {
        Log.d(TAG, "Message sender GEMINI, using AutoAwesome icon")
        Icons.Rounded.AutoAwesome
      }
      SenderRole.AGENT -> {
        Log.d(TAG, "Message sender AGENT, using Build icon")
        Icons.Default.Build
      }
      else -> {
        Log.d(TAG, "Message sender UNKNOWN, no icon")
        null
      }
    }

  Box(modifier = Modifier.fillMaxWidth(), contentAlignment = alignment) {
    Row(
      verticalAlignment = Alignment.Bottom,
      horizontalArrangement = Arrangement.spacedBy(8.dp),
      modifier = Modifier.widthIn(max = 300.dp),
    ) {
      if (message.sender != SenderRole.USER) {
        icon?.let {
          Icon(
            imageVector = it,
            contentDescription = "Sender Icon",
            modifier = Modifier.size(24.dp),
            tint = MaterialTheme.colorScheme.onSurfaceVariant,
          )
        }
      }

      Column(
        modifier = Modifier.background(backgroundColor, RoundedCornerShape(16.dp)).padding(12.dp)
      ) {
        if (message.agentName != null) {
          Log.d(TAG, "Displaying agent name: ${message.agentName}")
          Text(
            text = message.agentName,
            fontWeight = FontWeight.Bold,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onTertiaryContainer,
            modifier = Modifier.padding(bottom = 4.dp),
          )
        }
        Text(
          text = message.text.replace("\\n", "\n"),
          color =
            when (message.sender) {
              SenderRole.USER -> MaterialTheme.colorScheme.onPrimaryContainer
              SenderRole.GEMINI -> MaterialTheme.colorScheme.onSecondaryContainer
              SenderRole.AGENT -> MaterialTheme.colorScheme.onTertiaryContainer
              else -> Color.Transparent
            },
        )
      }

      if (message.sender == SenderRole.USER) {
        icon?.let {
          Icon(
            imageVector = it,
            contentDescription = "Sender Icon",
            modifier = Modifier.size(24.dp),
            tint = MaterialTheme.colorScheme.onSurfaceVariant,
          )
        }
      }
    }
  }
}

@Composable
fun ThinkingIndicator() {
  // Log.d(TAG, "ThinkingIndicator recomposed")
  val infiniteTransition = rememberInfiniteTransition(label = "alpha")
  val alpha by
    infiniteTransition.animateFloat(
      initialValue = 0.4f,
      targetValue = 1f,
      animationSpec =
        infiniteRepeatable(
          animation = tween(durationMillis = 700, easing = LinearEasing),
          repeatMode = RepeatMode.Reverse,
        ),
      label = "thinking",
    )

  Row(
    verticalAlignment = Alignment.CenterVertically,
    modifier = Modifier.padding(vertical = 8.dp).alpha(alpha),
  ) {
    Icon(
      imageVector = Icons.Rounded.AutoAwesome,
      contentDescription = "Thinking",
      modifier = Modifier.size(24.dp),
      tint = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    Spacer(modifier = Modifier.width(8.dp))
    Text(
      text = "Thinking...",
      style = MaterialTheme.typography.bodyMedium,
      color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
  }
}

@Composable
fun ChatInputFooter(
  value: String,
  onValueChange: (String) -> Unit,
  onSend: () -> Unit,
  isLoading: Boolean,
  // FIX: Accept the status text as a parameter
  statusText: String,
) {
  // Log.d(TAG, "ChatInputFooter recomposed with isLoading: $isLoading")
  Surface(shadowElevation = 8.dp) {
    // FIX: Wrap in a Column to show status above the input field
    Column(modifier = Modifier.fillMaxWidth()) {
      // FIX: Conditionally display the status text
      AnimatedVisibility(visible = statusText.isNotBlank()) {
        Text(
          text = statusText,
          modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp).fillMaxWidth(),
          textAlign = TextAlign.Center,
          style = MaterialTheme.typography.labelMedium,
          color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
      }
      Row(
        modifier = Modifier.fillMaxWidth().padding(8.dp),
        verticalAlignment = Alignment.CenterVertically,
      ) {
        OutlinedTextField(
          value = value,
          onValueChange = onValueChange,
          modifier = Modifier.weight(1f),
          placeholder = { Text("Type a message...") },
          keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
          keyboardActions = KeyboardActions(onSend = { onSend() }),
          enabled = !isLoading,
        )
        Spacer(modifier = Modifier.width(8.dp))
        IconButton(
          onClick = onSend,
          enabled = value.isNotBlank() && !isLoading,
          colors =
            IconButtonDefaults.iconButtonColors(contentColor = MaterialTheme.colorScheme.primary),
        ) {
          Icon(imageVector = Icons.Default.Send, contentDescription = "Send Message")
        }
      }
    }
  }
}
