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

package credentials_provider_agent

import (
	"log"

	"github.com/google-agentic-commerce/ap2/samples/go/pkg/ap2/types"
	"github.com/google-agentic-commerce/ap2/samples/go/pkg/common"
)

const systemPrompt = `You are a credentials provider agent. Your role is to manage user payment credentials and wallet information.

You can retrieve payment methods for users.`

type CredentialsProviderExecutor struct {
	baseExecutor *common.BaseExecutor
}

func NewCredentialsProviderExecutor(extensions []common.Extension) *CredentialsProviderExecutor {
	tools := []common.ToolInfo{
		{
			Name:        "get_payment_method",
			Description: "Retrieves the user's payment method details from their wallet.",
			Function:    GetPaymentMethod,
		},
	}

	baseExecutor, err := common.NewBaseExecutor(extensions, tools, systemPrompt)
	if err != nil {
		log.Fatalf("Failed to create base executor: %v", err)
	}

	return &CredentialsProviderExecutor{
		baseExecutor: baseExecutor,
	}
}

func (e *CredentialsProviderExecutor) HandleRequest(message *common.Message, currentTask *common.Task) (*common.Task, error) {
	return e.baseExecutor.HandleRequestWithTools(message, currentTask, nil)
}

func GetPaymentMethod(_ []map[string]interface{}, updater *common.TaskUpdater) error {
	paymentResponse := types.PaymentResponse{
		RequestID:  "payment-req-123",
		MethodName: "CARD",
		Details: map[string]interface{}{
			"card_number":     "4111111111111111",
			"expiry_month":    "12",
			"expiry_year":     "2025",
			"cvv":             "123",
			"cardholder_name": "John Doe",
		},
	}

	updater.AddArtifact([]common.Part{
		{
			Kind: "data",
			Data: map[string]interface{}{
				"payment_response": paymentResponse,
			},
		},
	})

	updater.Complete()
	return nil
}
