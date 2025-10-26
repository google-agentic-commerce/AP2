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
	"fmt"
	"log"

	"github.com/google-agentic-commerce/ap2/samples/go/pkg/ap2/types"
	"github.com/google-agentic-commerce/ap2/samples/go/pkg/common"
)

const (
	ExtensionURI     = "https://github.com/google-agentic-commerce/ap2/v1"
	FakeJWT          = "eyJhbGciOiJSUzI1NiIsImtpZIwMjQwOTA..."
	ProcessorURLCard = "http://localhost:8003/a2a/merchant_payment_processor_agent"
)

func FindItems(dataParts []map[string]interface{}, updater *common.TaskUpdater) error {
	storage := GetStorage()

	var query string
	if val, ok := common.FindDataPart("shopping_intent", dataParts); ok {
		query = fmt.Sprintf("%v", val)
	}

	log.Printf("Searching for products with query: %s", query)

	products := storage.SearchProducts(query)

	cartMandate := storage.CreateCartMandate(products)

	storage.StoreRiskData(updater.GetContextID(), map[string]interface{}{
		"ip_address":    "192.168.1.1",
		"device_id":     "device-12345",
		"session_token": "session-67890",
	})

	updater.AddArtifact([]common.Part{
		{
			Data: &common.DataPart{
				Data: map[string]interface{}{
					types.CartMandateDataKey: cartMandate,
				},
			},
		},
	})

	updater.Complete()
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
			Data: &common.DataPart{
				Data: map[string]interface{}{
					types.CartMandateDataKey: cartMandate,
					"risk_data":              riskData,
				},
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

	paymentMethodType := paymentMandate.PaymentMandateContents.PaymentResponse.MethodName
	log.Printf("Initiating payment with method: %s", paymentMethodType)

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
