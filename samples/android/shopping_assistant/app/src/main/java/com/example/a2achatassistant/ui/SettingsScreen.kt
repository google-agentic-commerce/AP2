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

import android.util.Log
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.selection.selectable
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.Done
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

private const val TAG = "SettingsScreen"

private const val MERCHANT_AGENT_URL = "http://localhost:8001/a2a/merchant_agent"

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(agentCardUrl: String, onDoneClicked: (String) -> Unit) {
  Log.d(TAG, "SettingsScreen recomposed with URL: $agentCardUrl")
  val agentOptions = listOf("Generic Merchant Agent" to MERCHANT_AGENT_URL, "Custom" to "")

  var editedUrl by remember { mutableStateOf(agentCardUrl) }
  var selectedOption by remember {
    mutableStateOf(
      agentOptions.find { it.second == agentCardUrl && it.first != "Custom" }?.first ?: "Custom"
    )
  }

  Scaffold(
    topBar = {
      TopAppBar(
        title = { Text("Settings") },
        actions = {
          IconButton(
            onClick = {
              Log.d(TAG, "Done button clicked, new URL: $editedUrl")
              onDoneClicked(editedUrl)
            }
          ) {
            Icon(imageVector = Icons.Default.Done, contentDescription = "Done")
          }
        },
      )
    }
  ) { paddingValues ->
    Column(modifier = Modifier.padding(paddingValues).padding(16.dp)) {
      agentOptions.forEach { (name, url) ->
        Row(
          Modifier.fillMaxWidth()
            .selectable(
              selected = (selectedOption == name),
              onClick = {
                Log.d(TAG, "Selected option: $name")
                selectedOption = name
                if (name != "Custom") {
                  Log.d(TAG, "Setting URL to: $url")
                  editedUrl = url
                }
              },
            )
            .padding(vertical = 8.dp),
          verticalAlignment = Alignment.CenterVertically,
        ) {
          RadioButton(
            selected = (selectedOption == name),
            onClick = null, // null recommended for accessibility with screenreaders
          )
          Text(text = name, modifier = Modifier.padding(start = 16.dp))
        }
      }

      OutlinedTextField(
        value = editedUrl,
        onValueChange = { newUrl ->
          Log.d(TAG, "URL changed to: $newUrl")
          editedUrl = newUrl
          selectedOption =
            agentOptions.find { it.second == newUrl && it.first != "Custom" }?.first ?: "Custom"
        },
        label = { Text("Agent Card URL") },
        modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
        enabled = true,
        trailingIcon = {
          if (editedUrl.isNotEmpty()) {
            IconButton(
              onClick = {
                Log.d(TAG, "Clear URL button clicked")
                editedUrl = ""
                selectedOption = "Custom"
              }
            ) {
              Icon(imageVector = Icons.Default.Clear, contentDescription = "Clear URL")
            }
          }
        },
      )
    }
  }
}
