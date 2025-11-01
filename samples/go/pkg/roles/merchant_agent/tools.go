// Copyright 2025 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package merchant_agent

import (
	"context"
	"encoding/json"
	"fmt"
	"os"

	"github.com/google-agentic-commerce/ap2/samples/go/pkg/ap2/types"
	"github.com/google-agentic-commerce/ap2/samples/go/pkg/common"
	"github.com/google/generative-ai-go/genai"
	"google.golang.org/api/option"
)

const (
	ExtensionURI     = "https://github.com/google-agentic-commerce/ap2/v1"
	FakeJWT          = "eyJhbGciOiJSUzI1NiIsImtpZIwMjQwOTA..."
	ProcessorURLCard = "http://localhost:8003/a2a/merchant_payment_processor_agent"
)

func FindItems(dataParts []map[string]interface{}, updater *common.TaskUpdater) error {
	storage := GetStorage()

	// Try to parse the IntentMandate first
	var intentMandate types.IntentMandate
	var query string

	if err := common.ParseDataPart(types.IntentMandateDataKey, dataParts, &intentMandate); err == nil {
		// Use the natural language description from IntentMandate
		query = intentMandate.NaturalLanguageDescription
	} else if val, ok := common.FindDataPart("shopping_intent", dataParts); ok {
		// Fallback to shopping_intent if no IntentMandate
		query = fmt.Sprintf("%v", val)
	} else {
		query = ""
	}

	// Only use LLM-based product generation (like Python implementation)
	err := generateProductsWithLLM(query, updater, storage)
	if err != nil {
		updater.Failed(fmt.Sprintf("Failed to generate products: %v", err))
		return fmt.Errorf("LLM generation failed: %w", err)
	}

	updater.Complete()
	return nil
}

// generateProductsWithLLM generates products using Gemini LLM with structured output
func generateProductsWithLLM(query string, updater *common.TaskUpdater, storage *Storage) error {
	apiKey := os.Getenv("GOOGLE_API_KEY")
	if apiKey == "" {
		return fmt.Errorf("GOOGLE_API_KEY environment variable is required but not set")
	}

	ctx := context.Background()
	client, err := genai.NewClient(ctx, option.WithAPIKey(apiKey))
	if err != nil {
		return fmt.Errorf("failed to create genai client: %w", err)
	}
	defer client.Close()

	model := client.GenerativeModel("gemini-2.5-flash")

	// Configure model for structured JSON output
	model.ResponseMIMEType = "application/json"

	// Define the schema for structured output using Go struct tags
	type Amount struct {
		Currency string  `json:"currency"`
		Value    float64 `json:"value"`
	}

	type PaymentItem struct {
		Label        string  `json:"label"`
		Amount       Amount  `json:"amount"`
		RefundPeriod int     `json:"refund_period"`
	}

	// Set the response schema for an array of PaymentItems
	model.ResponseSchema = &genai.Schema{
		Type: genai.TypeArray,
		Items: &genai.Schema{
			Type: genai.TypeObject,
			Properties: map[string]*genai.Schema{
				"label": {
					Type:        genai.TypeString,
					Description: "Product name without branding",
				},
				"amount": {
					Type: genai.TypeObject,
					Properties: map[string]*genai.Schema{
						"currency": {
							Type: genai.TypeString,
							Enum: []string{"USD"},
						},
						"value": {
							Type:        genai.TypeNumber,
							Description: "Price in USD",
						},
					},
					Required: []string{"currency", "value"},
				},
				"refund_period": {
					Type:        genai.TypeInteger,
					Description: "Refund period in days",
				},
			},
			Required: []string{"label", "amount", "refund_period"},
		},
	}

	prompt := fmt.Sprintf(`Based on the user's request for '%s', your task is to generate 3
	complete, unique and realistic PaymentItem JSON objects.

	You MUST exclude all branding from the PaymentItem label field.
	Each item should have:
	- A descriptive product name
	- A realistic price in USD
	- A refund period of 30 days

	Generate exactly 3 items that best match the user's request.`, query)

	resp, err := model.GenerateContent(ctx, genai.Text(prompt))
	if err != nil {
		return fmt.Errorf("LLM generation failed: %w", err)
	}

	if len(resp.Candidates) == 0 {
		return fmt.Errorf("no LLM response candidates")
	}

	// Extract the generated JSON
	var generatedJSON string
	for _, part := range resp.Candidates[0].Content.Parts {
		if text, ok := part.(genai.Text); ok {
			generatedJSON = string(text)
			break
		}
	}

	// Parse the structured JSON response
	var generatedItems []PaymentItem
	if err := json.Unmarshal([]byte(generatedJSON), &generatedItems); err != nil {
		return fmt.Errorf("failed to parse LLM response: %w", err)
	}

	// Create a cart mandate for each generated item
	for i, item := range generatedItems {
		product := Product{
			SKU:         fmt.Sprintf("GEN-%d", i+1),
			Name:        item.Label,
			Description: fmt.Sprintf("Generated product for: %s", query),
			Price:       item.Amount.Value,
			Category:    "Generated",
		}

		singleProductCart := storage.CreateCartMandate([]Product{product})
		updater.AddArtifact([]common.Part{
			{
				Kind: "data",
				Data: map[string]interface{}{
					types.CartMandateDataKey: singleProductCart,
				},
			},
		})
	}

	storage.StoreRiskData(updater.GetContextID(), map[string]interface{}{
		"ip_address":    "192.168.1.1",
		"device_id":     "device-12345",
		"session_token": "session-67890",
	})

	return nil
}

func UpdateCart(dataParts []map[string]interface{}, updater *common.TaskUpdater) error {
	storage := GetStorage()

	cartIDVal, ok := common.FindDataPart("cart_id", dataParts)
	if !ok {
		updater.Failed("Missing cart_id")
		return fmt.Errorf("missing cart_id")
	}
	cartID := fmt.Sprintf("%v", cartIDVal)

	var shippingAddress types.ContactAddress
	if err := common.ParseDataPart("shipping_address", dataParts, &shippingAddress); err != nil {
		updater.Failed(fmt.Sprintf("Invalid shipping_address: %v", err))
		return err
	}

	cartMandate := storage.GetCartMandate(cartID)
	if cartMandate == nil {
		updater.Failed(fmt.Sprintf("CartMandate not found for cart_id: %s", cartID))
		return fmt.Errorf("cart not found")
	}

	riskData := storage.GetRiskData(updater.GetContextID())
	if riskData == nil {
		updater.Failed(fmt.Sprintf("Missing risk_data for context_id: %s", updater.GetContextID()))
		return fmt.Errorf("missing risk data")
	}

	cartMandate.Contents.PaymentRequest.ShippingAddress = &shippingAddress

	shippingCost := types.PaymentItem{
		Label:        "Shipping",
		Amount:       types.PaymentCurrencyAmount{Currency: "USD", Value: 2.00},
		RefundPeriod: 30,
	}
	taxCost := types.PaymentItem{
		Label:        "Tax",
		Amount:       types.PaymentCurrencyAmount{Currency: "USD", Value: 1.50},
		RefundPeriod: 30,
	}

	cartMandate.Contents.PaymentRequest.Details.DisplayItems = append(
		cartMandate.Contents.PaymentRequest.Details.DisplayItems,
		shippingCost,
		taxCost,
	)

	var newTotal float64
	for _, item := range cartMandate.Contents.PaymentRequest.Details.DisplayItems {
		newTotal += item.Amount.Value
	}
	cartMandate.Contents.PaymentRequest.Details.Total.Amount.Value = newTotal

	authToken := FakeJWT
	cartMandate.MerchantAuthorization = &authToken

	updater.AddArtifact([]common.Part{
		{
			Kind: "data",
			Data: map[string]interface{}{
				types.CartMandateDataKey: cartMandate,
				"risk_data":              riskData,
			},
		},
	})

	updater.Complete()
	return nil
}

func InitiatePayment(dataParts []map[string]interface{}, updater *common.TaskUpdater) error {
	var paymentMandate types.PaymentMandate
	if err := common.ParseDataPart(types.PaymentMandateDataKey, dataParts, &paymentMandate); err != nil {
		updater.Failed(fmt.Sprintf("Missing payment_mandate: %v", err))
		return err
	}

	riskData, ok := common.FindDataPart("risk_data", dataParts)
	if !ok {
		updater.Failed("Missing risk_data")
		return fmt.Errorf("missing risk_data")
	}

	processorClient := common.NewA2AClient(
		"payment_processor_agent",
		ProcessorURLCard,
		[]string{ExtensionURI},
	)

	messageBuilder := common.NewMessageBuilder().
		SetContextID(updater.GetContextID()).
		AddText("initiate_payment").
		AddData(types.PaymentMandateDataKey, paymentMandate).
		AddData("risk_data", riskData)

	if challengeResp, ok := common.FindDataPart("challenge_response", dataParts); ok {
		messageBuilder.AddData("challenge_response", challengeResp)
	}

	task, err := processorClient.SendMessage(messageBuilder.Build())
	if err != nil {
		updater.Failed(fmt.Sprintf("Payment processor error: %v", err))
		return err
	}

	updater.UpdateStatus(task.Status.State, task.Status.Message)
	return nil
}
