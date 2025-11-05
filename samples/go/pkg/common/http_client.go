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

package common

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"

	"github.com/google/uuid"
)

type A2AClient struct {
	Name               string
	BaseURL            string
	RequiredExtensions map[string]bool
	httpClient         *http.Client
}

func NewA2AClient(name, baseURL string, requiredExtensions []string) *A2AClient {
	extMap := make(map[string]bool)
	for _, ext := range requiredExtensions {
		extMap[ext] = true
	}

	return &A2AClient{
		Name:               name,
		BaseURL:            baseURL,
		RequiredExtensions: extMap,
		httpClient:         &http.Client{},
	}
}

func (c *A2AClient) SendMessage(message *Message) (*Task, error) {
	// Create JSON-RPC request with unique ID
	requestID := message.MessageID
	if requestID == "" {
		requestID = uuid.New().String()
	}

	rpcRequest := JSONRPCRequest{
		ID:      requestID,
		JSONRPC: "2.0",
		Method:  "sendMessage",
		Params: map[string]interface{}{
			"message": message,
		},
	}

	jsonData, err := json.Marshal(rpcRequest)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal JSONRPC request: %w", err)
	}

	resp, err := c.httpClient.Post(c.BaseURL, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("request failed with status %d: %s", resp.StatusCode, string(bodyBytes))
	}

	// First try to parse as JSONRPC response
	var rpcResponse JSONRPCResponse
	if err := json.Unmarshal(bodyBytes, &rpcResponse); err == nil && rpcResponse.JSONRPC == "2.0" {
		// It's a JSONRPC response
		if rpcResponse.Error != nil {
			return nil, fmt.Errorf("JSONRPC error: %s", rpcResponse.Error.Message)
		}

		// Convert result map to Task
		taskJSON, err := json.Marshal(rpcResponse.Result)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal result: %w", err)
		}

		var task Task
		if err := json.Unmarshal(taskJSON, &task); err != nil {
			return nil, fmt.Errorf("failed to decode task from JSONRPC result: %w", err)
		}

		return &task, nil
	}

	// Fallback to direct Task parsing (for backward compatibility)
	var task Task
	if err := json.Unmarshal(bodyBytes, &task); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return &task, nil
}

func (c *A2AClient) GetCard() (*AgentCard, error) {
	baseURL := c.BaseURL
	if baseURL[len(baseURL)-1] == '/' {
		baseURL = baseURL[:len(baseURL)-1]
	}

	cardURL := fmt.Sprintf("%s/.well-known/agent-card.json", baseURL)

	resp, err := c.httpClient.Get(cardURL)
	if err != nil {
		return nil, fmt.Errorf("failed to get agent card: %w", err)
	}
	defer resp.Body.Close()

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("agent card request failed with status %d: %s", resp.StatusCode, string(bodyBytes))
	}

	var card AgentCard
	if err := json.Unmarshal(bodyBytes, &card); err != nil {
		return nil, fmt.Errorf("failed to decode agent card: %w", err)
	}

	return &card, nil
}
