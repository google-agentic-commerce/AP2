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

	"github.com/google-agentic-commerce/ap2/samples/go/pkg/common"
)

const systemPrompt = `You are a merchant agent. Your role is to help users with their shopping requests.

You can find items, update shopping carts, and initiate payments.`

var knownShoppingAgents = map[string]bool{
	"trusted_shopping_agent": true,
}

type MerchantAgentExecutor struct {
	baseExecutor *common.BaseExecutor
}

func NewMerchantAgentExecutor(extensions []common.Extension) *MerchantAgentExecutor {
	tools := []common.ToolInfo{
		{
			Name:        "find_items_workflow",
			Description: "Searches the merchant's catalog based on a shopping intent and returns a cart containing the top results.",
			Function:    FindItems,
		},
		{
			Name:        "update_cart",
			Description: "Updates an existing cart after a shipping address is provided. Adds shipping and tax costs.",
			Function:    UpdateCart,
		},
		{
			Name:        "initiate_payment",
			Description: "Initiates a payment for a given payment mandate. Forwards the payment request to the payment processor.",
			Function:    InitiatePayment,
		},
	}

	baseExecutor, err := common.NewBaseExecutor(extensions, tools, systemPrompt)
	if err != nil {
		log.Fatalf("Failed to create base executor: %v", err)
	}

	return &MerchantAgentExecutor{
		baseExecutor: baseExecutor,
	}
}

func (e *MerchantAgentExecutor) HandleRequest(message *common.Message, currentTask *common.Task) (*common.Task, error) {
	return e.baseExecutor.HandleRequestWithTools(message, currentTask, e.validateShoppingAgent)
}

func (e *MerchantAgentExecutor) validateShoppingAgent(dataParts []map[string]interface{}, updater *common.TaskUpdater) bool {
	agentID, ok := common.FindDataPart("shopping_agent_id", dataParts)
	if !ok {
		log.Println("Missing shopping_agent_id in request")
		updater.Failed("Unauthorized Request: Missing shopping_agent_id")
		return false
	}

	agentIDStr, ok := agentID.(string)
	if !ok {
		log.Printf("shopping_agent_id is not a string: %T", agentID)
		updater.Failed("Unauthorized Request: invalid shopping_agent_id format")
		return false
	}
	log.Printf("Received request from shopping_agent_id: %s", agentIDStr)

	if !knownShoppingAgents[agentIDStr] {
		log.Printf("Unknown Shopping Agent: %s", agentIDStr)
		updater.Failed(fmt.Sprintf("Unauthorized Request: Unknown agent '%s'", agentIDStr))
		return false
	}

	log.Printf("Authorized request from shopping_agent_id: %s", agentIDStr)
	return true
}
