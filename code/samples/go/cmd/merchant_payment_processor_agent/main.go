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

package main

import (
	"log"

	"github.com/google-agentic-commerce/ap2/samples/go/pkg/common"
	"github.com/google-agentic-commerce/ap2/samples/go/pkg/roles/merchant_payment_processor_agent"
)

const (
	AgentPort = 8003
	RPCURL    = "/a2a/merchant_payment_processor_agent"
)

func main() {
	agentCard, err := common.LoadAgentCard("pkg/roles/merchant_payment_processor_agent")
	if err != nil {
		log.Fatalf("Failed to load agent card: %v", err)
	}

	executor := merchant_payment_processor_agent.NewPaymentProcessorExecutor(agentCard.Capabilities.Extensions)

	server := common.NewAgentServer(AgentPort, agentCard, executor, RPCURL)

	if err := server.Start(); err != nil {
		log.Fatalf("Server error: %v", err)
	}
}
