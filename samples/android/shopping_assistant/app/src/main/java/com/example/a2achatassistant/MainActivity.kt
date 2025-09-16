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
package com.example.a2achatassistant

import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.example.a2achatassistant.ui.ChatScreen
import com.example.a2achatassistant.ui.ChatViewModel
import com.example.a2achatassistant.ui.SettingsScreen
import com.example.a2achatassistant.ui.theme.A2achatassistantTheme

private const val TAG = "MainActivity"

class MainActivity : ComponentActivity() {

  private val viewModel: ChatViewModel by viewModels()

  override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    Log.d(TAG, "onCreate called")
    setContent {
      A2achatassistantTheme {
        Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
          val navController = rememberNavController()
          val agentCardUrl by viewModel.agentCardUrl.collectAsState()

          NavHost(navController = navController, startDestination = "chat") {
            composable("chat") {
              Log.d(TAG, "Navigating to ChatScreen")
              ChatScreen(
                viewModel = viewModel,
                onSettingsClicked = {
                  Log.d(TAG, "Settings icon clicked, navigating to settings")
                  navController.navigate("settings")
                },
              )
            }
            composable("settings") {
              Log.d(TAG, "Navigating to SettingsScreen")
              SettingsScreen(
                agentCardUrl = agentCardUrl,
                onDoneClicked = { newUrl ->
                  Log.d(TAG, "Done button clicked in settings, new URL: $newUrl")
                  viewModel.setAgentCardUrl(newUrl)
                  navController.popBackStack()
                },
              )
            }
          }
        }
      }
    }
  }
}
