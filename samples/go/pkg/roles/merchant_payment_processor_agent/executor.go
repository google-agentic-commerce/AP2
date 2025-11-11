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

package merchant_payment_processor_agent

import (
	"fmt"
	"log"

	"github.com/google-agentic-commerce/ap2/samples/go/pkg/ap2/types"
	"github.com/google-agentic-commerce/ap2/samples/go/pkg/common"
)

const systemPrompt = `You are a merchant payment processor agent. Your role is to process payments on behalf of merchants.

You can initiate and authorize payment transactions.`

type PaymentProcessorExecutor struct {
	baseExecutor *common.BaseExecutor
}

func NewPaymentProcessorExecutor(extensions []common.Extension) *PaymentProcessorExecutor {
	tools := []common.ToolInfo{
		{
			Name:        "initiate_payment",
			Description: "Processes a payment using the provided payment mandate and risk data.",
			Function:    InitiatePayment,
		},
	}

	baseExecutor, err := common.NewBaseExecutor(extensions, tools, systemPrompt)
	if err != nil {
		log.Fatalf("Failed to create base executor: %v", err)
	}

	return &PaymentProcessorExecutor{
		baseExecutor: baseExecutor,
	}
}

func (e *PaymentProcessorExecutor) HandleRequest(message *common.Message, currentTask *common.Task) (*common.Task, error) {
	return e.baseExecutor.HandleRequestWithTools(message, currentTask, nil)
}

func InitiatePayment(dataParts []map[string]interface{}, updater *common.TaskUpdater) error {
	var paymentMandate types.PaymentMandate
	if err := common.ParseDataPart(types.PaymentMandateDataKey, dataParts, &paymentMandate); err != nil {
		updater.Failed(fmt.Sprintf("Missing or invalid payment_mandate: %v", err))
		return err
	}

	riskData, ok := common.FindDataPart("risk_data", dataParts)
	if !ok {
		updater.Failed("Missing risk_data")
		return fmt.Errorf("missing risk_data")
	}

	log.Printf("Processing payment for mandate: %s", paymentMandate.PaymentMandateContents.PaymentMandateID)
	log.Printf("Risk data: %v", riskData)

	updater.AddArtifact([]common.Part{
		{
			Kind: "data",
			Data: map[string]interface{}{
				"payment_status":     "SUCCESS",
				"transaction_id":     "txn-" + paymentMandate.PaymentMandateContents.PaymentMandateID,
				"authorization_code": "AUTH-123456",
			},
		},
	})

	updater.Complete()
	return nil
}
