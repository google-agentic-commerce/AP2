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

import android.app.Activity
import android.content.Context
import android.util.Log
import com.example.a2achatassistant.BuildConfig
import com.example.a2achatassistant.data.ContactAddress
import com.example.a2achatassistant.data.ToolContext
import com.google.ai.client.generativeai.GenerativeModel
import com.google.ai.client.generativeai.type.Content
import com.google.ai.client.generativeai.type.FunctionResponsePart
import com.google.ai.client.generativeai.type.Schema
import com.google.ai.client.generativeai.type.TextPart
import com.google.ai.client.generativeai.type.Tool
import com.google.ai.client.generativeai.type.defineFunction
import kotlinx.coroutines.flow.MutableStateFlow
import org.json.JSONObject

private const val TAG = "ChatRepository"

data class ChatResponse(val text: String, val collapsedData: String? = null)

class ChatRepository(private val context: Context) {

  private val toolContext = ToolContext()
  private var shoppingTools: ShoppingTools? = null

  private val _history = MutableStateFlow<List<Content>>(emptyList())

  private val rootAgentInstruction =
    """
        You are a friendly and helpful shopping assistant. Your goal is to make the user's shopping
        experience as smooth as possible.

        Here's how you'll guide the user through the process:

        **Part 1: Finding and Selecting the Perfect Item**
        1.  Start by asking the user what they're looking for. Be conversational and friendly.
        2.  Once you have a good description, use the `find_products` tool to search for matching items.
        3.  Present the search results to the user in a clear, easy-to-read format. For each item,
            show the name, price, and any other relevant details.
        4.  Ask the user which item they would like to purchase.
        5.  Once the user makes a choice, call the `select_product` tool with the `itemName` of their choice.

        **Part 2: Shipping**
        1.  After a product is selected, ask the user for their shipping address. They can either
            provide it manually or you can offer to fetch it from their account by calling the
            `get_shipping_address` tool.
        2.  If they choose to use their saved address, confirm the address with them before proceeding.

        **Part 3: Checkout**
        1.  Once the shipping address is confirmed, call `create_checkout` to get a checkout JWT
            from the merchant. This creates a binding commitment for the cart.
        2.  Display a final order summary and ask if the user wants to finalize.

        **Part 4: Payment**
        1.  Once the user confirms, call `retrieve_dpc_options` to complete the payment flow.
            This tool invokes the Credential Manager API which displays payment options on a
            system UI. The user selects a payment method and authenticates with biometrics.
            The wallet app signs the mandate SD-JWTs with the device key and returns the
            DPC token. Everything is then sent to the merchant for validation.

        **Part 5: Finalizing the Flow**
        1.  Once `retrieve_dpc_options` returns successfully, the merchant has confirmed the payment.
        2.  Display a formatted payment receipt for the user.
        3.  End the conversation by saying "I am done for now".
    """

  private val generativeModel by lazy {
    val tools =
      Tool(
        functionDeclarations =
          listOf(
            defineFunction(
              name = "find_products",
              description = "Finds products based on a user's description.",
              parameters =
                listOf(Schema.Companion.str("description", "The user's product search query.")),
              requiredParameters = listOf("description"),
            ),
            defineFunction(
              name = "select_product",
              description = "Selects a product from the list of options.",
              parameters =
                listOf(Schema.Companion.str("itemName", "The item name of the product to select.")),
              requiredParameters = listOf("itemName"),
            ),
            defineFunction(
              name = "get_shipping_address",
              description = "Gets the shipping address from a credential provider.",
              parameters = listOf(Schema.Companion.str("email", "The user's email address.")),
              requiredParameters = listOf("email"),
            ),
            defineFunction(
              name = "create_checkout",
              description =
                "Creates a merchant-signed checkout JWT for the selected cart. " +
                  "Must be called after select_product.",
            ),
            defineFunction(
              name = "retrieve_dpc_options",
              description =
                "Handles the entire DPC payment flow: invokes Credential Manager which " +
                  "signs mandate SD-JWTs with the device key and returns the DPC token. " +
                  "Sends everything to the merchant for validation.",
            ),
          )
      )
    GenerativeModel(
      modelName = "gemini-2.5-flash",
      apiKey = BuildConfig.GEMINI_API_KEY,
      systemInstruction = Content("system", listOf(TextPart(rootAgentInstruction))),
      tools = listOf(tools),
    )
  }

  suspend fun initialize(url: String): Result<Unit> {
    Log.d(TAG, "Initializing repository with agent URL: $url")
    ShoppingTools.Companion.initiateShoppingTools(merchantAgentUrl = url, context = context)
      .map {
        shoppingTools = it
        Log.i(TAG, "Repository initialized shopping tools")
        return Result.success(Unit)
      }
      .onFailure { Log.e(TAG, "Repository initialization failed", it) }
    return Result.failure(Exception("Repository initialization failed."))
  }

  suspend fun getResponse(
    userMessage: String,
    activity: Activity?,
    onStatusUpdate: (String) -> Unit,
  ): Result<ChatResponse> {

    onStatusUpdate("Thinking...")
    val chat = generativeModel.startChat(_history.value)

    try {
      var response = chat.sendMessage(userMessage)
      _history.value = chat.history

      while (true) {
        val functionCall = response.functionCalls.firstOrNull()
        if (functionCall != null) {
          onStatusUpdate("Executing: ${functionCall.name}...")
          Log.d(TAG, "Executing tool: ${functionCall.name} with args: ${functionCall.args}")
          val toolResponse = executeTool(functionCall.name, functionCall.args, activity)
          Log.d(TAG, "Tool response: $toolResponse")

          onStatusUpdate("Thinking...")
          response =
            chat.sendMessage(
              Content("function", listOf(FunctionResponsePart(functionCall.name, toolResponse)))
            )
          _history.value = chat.history
        } else {
          onStatusUpdate("")
          val collapsedData = toolContext.state.dpcLog
          toolContext.state.dpcLog = null
          return Result.success(ChatResponse(response.text ?: "Done.", collapsedData))
        }
      }
    } catch (e: Exception) {
      val stackTrace = e.stackTraceToString()
      Log.e(TAG, "An error occurred in getResponse: ${e.message}\n$stackTrace")
      onStatusUpdate("An error occurred.")
      return Result.failure(e)
    }
  }

  private suspend fun executeTool(
    name: String,
    args: Map<String, Any?>,
    activity: Activity?,
  ): JSONObject {
    val jsonResult = JSONObject()
    val tools = shoppingTools

    if (tools == null) {
      Log.d(TAG, "No shopping tools available")
      jsonResult.put("status", "error")
      jsonResult.put(
        "message",
        "Not connected to the merchant_agent. Please make sure you " +
          "have the right url, and re-connect from Settings",
      )
      return jsonResult
    }

    when (name) {
      "find_products" -> {
        val description = args["description"] as? String ?: ""
        val carts = tools.findProducts(description, toolContext)
        if (carts.isEmpty()) {
          jsonResult.put("status", "error")
          jsonResult.put(
            "response_text",
            "Sorry, I couldn't find any products matching that description.",
          )
          return jsonResult
        }
        jsonResult.put("status", "success")
        val productListString =
          carts.joinToString(separator = "\n") {
            "- ${it.itemLabel} for ${it.amount} ${it.currency}"
          }
        jsonResult.put("response_text", "I found a few options for you:\n$productListString")
      }
      "select_product" -> {
        val itemName = args["itemName"] as? String ?: ""
        Log.d(TAG, "Finding product: $itemName")
        val selectedProduct = tools.selectProduct(itemName, toolContext)
        if (selectedProduct == null) {
          jsonResult.put("status", "error")
          jsonResult.put("response_text", "Could not find item $itemName")
          return jsonResult
        }
        jsonResult.put("status", "success")
        jsonResult.put("response_text", "Selected ${selectedProduct.itemLabel}")
      }
      "get_shipping_address" -> {
        val address = ContactAddress("456 Oak Ave", "Otherville", "NY", "54321")
        toolContext.state.shippingAddress = address
        jsonResult.put("status", "success")
        jsonResult.put("streetAddress", address.streetAddress)
        jsonResult.put("city", address.city)
        jsonResult.put("state", address.state)
        jsonResult.put("zipCode", address.zipCode)
      }
      "create_checkout" -> {
        val checkoutData = tools.createCheckout(toolContext)
        if (checkoutData == null) {
          jsonResult.put("status", "error")
          jsonResult.put("response_text", "Could not create checkout")
          return jsonResult
        }
        jsonResult.put("status", "success")
        jsonResult.put(
          "response_text",
          "Checkout created for ${checkoutData.itemLabel}: " +
            "${checkoutData.amount} ${checkoutData.currency}",
        )
      }
      "retrieve_dpc_options" -> {
        val result = tools.retrieveDpcOptions(toolContext, activity!!)
        handlePaymentResult(result, jsonResult)
      }
      else -> {
        Log.e(TAG, "Unknown tool: $name")
        jsonResult.put("status", "error")
        jsonResult.put("message", "Unknown tool: $name")
      }
    }
    return jsonResult
  }

  private fun handlePaymentResult(result: PaymentResult, builder: JSONObject) {
    when (result) {
      is PaymentResult.Success -> {
        builder.put("status", "success")
        builder.put("message", "Payment successful!")
      }

      is PaymentResult.OtpRequired -> {
        builder.put("status", "otp_required")
        builder.put("message", result.message)
      }

      is PaymentResult.Failure -> {
        builder.put("status", "error")
        builder.put("message", result.message)
      }
    }
  }
}
