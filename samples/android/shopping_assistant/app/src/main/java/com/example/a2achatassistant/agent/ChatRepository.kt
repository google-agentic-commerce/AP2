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
import com.example.a2achatassistant.data.CartMandate
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
        1.  After a product is selected, ask the user for their shipping address. They can either provide it manually or you can
            offer to fetch it from their account by calling the `get_shipping_address` tool.
        2.  If they choose to use their saved address, confirm the address with them before proceeding.
        3.  Once the shipping address is confirmed, use the `update_cart` tool to add the address to the order.
        4.  Display a final order summary, including the item, price, tax, shipping, and total, and ask if the 
        user wants to finalize it or if they want to continue shopping, in which case the whole flow will repeat.


        **Part 3: Payment**
        1.  Once the user has finalized shopping and want to purchase, call the 'retrieve_dpc_options' tool to get an openId4VP JSON from the merchant. 
        The same tool will get a response an openIdVp request from the merchant and then invoke credential manager API with that JSON.  This API
        displays a summary of what the user is about to buy and also displays user's available payment option on a 
        separate system UI - the user will select one option and that will close the UI that will return a 
        final JSON token. Once the payment token is retrieved, it is sent back to the merchant for validation from within 
        the same 'retrieve_dpc_options' tool. When the validation is received from the merchant the whole flow succeeds still
        within the same tool and now finally the tool returns successfully.
        
        **Part 4: Finalizing the Flow**
        1.  Once the 'retrieve_dpc_options' returns successfully, merchant has confirmed the payment.
        2.  Once the payment is successful, display a formatted payment receipt for the user.
        6.  End the conversation by saying "I am done for now".
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
              name = "update_cart",
              description = "Updates the cart with the user's shipping address.",
            ),
            defineFunction(
              name = "retrieve_dpc_options",
              description =
                "Handles the entire payment flow, from getting options to final validation.",
            ),
            defineFunction(
              name = "initiate_payment_with_otp",
              description = "Retries payment with an OTP.",
              parameters =
                listOf(Schema.Companion.str("otp", "The one-time password from the user.")),
              requiredParameters = listOf("otp"),
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
    ShoppingTools.Companion.initiateShoppingTools(url, context)
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
  ): Result<String> {

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
          onStatusUpdate("") // Clear status
          return Result.success(response.text ?: "Done.")
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
        val cartMandateList = tools.findProducts(description, toolContext)
        if (cartMandateList.isEmpty()) {
          jsonResult.put("status", "error")
          jsonResult.put(
            "response_text",
            "Sorry, I couldn't find any products matching that description.",
          )
          return jsonResult
        }
        toolContext.state.productOptions = cartMandateList
        jsonResult.put("status", "success")
        val productListString =
          cartMandateList.joinToString(separator = "\n") {
            "- ${it.contents.paymentRequest.details.displayItems[0].label} for ${it.contents.paymentRequest.details.total}"
          }
        jsonResult.put("response_text", "I found a few options for you:\n$productListString")
      }
      "select_product" -> {
        val itemName = args["itemName"] as? String ?: ""
        Log.d(TAG, "Finding product: $itemName")
        val selectedProduct = getItemFromCartMandate(itemName, toolContext.state.productOptions)
        if (selectedProduct == null) {
          jsonResult.put("status", "error")
          jsonResult.put("response_text", "Could not find item $itemName")
          return jsonResult
        }
        toolContext.state.cartMandate = selectedProduct
        jsonResult.put("status", "success")
        jsonResult.put(
          "response_text",
          "Selected ${selectedProduct.contents.paymentRequest.details.displayItems[0].label}",
        )
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
      "update_cart" -> {
        val cart = toolContext.state.cartMandate!!
        val address = toolContext.state.shippingAddress!!
        val cartMandate = tools.updateCart(cart.contents.id, address, toolContext)
        if (cartMandate == null) {
          jsonResult.put("status", "error")
          jsonResult.put("response_text", "Could not update cart")
          return jsonResult
        }
        toolContext.state.cartMandate = cartMandate
        jsonResult.put("status", "success")
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

  private fun getItemFromCartMandate(
    itemName: String,
    cartMandateList: List<CartMandate>?,
  ): CartMandate? {
    // cartMandate?.contents?.paymentRequest?.details?.displayItems?.find { it.label == itemName }
    return cartMandateList?.find {
      it.contents.paymentRequest.details.displayItems[0].label == itemName
    }
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
