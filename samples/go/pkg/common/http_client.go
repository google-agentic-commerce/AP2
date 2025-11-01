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
	"net/url"
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
	jsonData, err := json.Marshal(message)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal message: %w", err)
	}

	resp, err := c.httpClient.Post(c.BaseURL, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, err := io.ReadAll(resp.Body)
		if err != nil {
			return nil, fmt.Errorf("request failed with status %d: %w", resp.StatusCode, err)
		}
		return nil, fmt.Errorf("request failed with status %d: %s", resp.StatusCode, string(body))
	}

	var task Task
	if err := json.NewDecoder(resp.Body).Decode(&task); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return &task, nil
}

func (c *A2AClient) GetCard() (*AgentCard, error) {
	parsedURL, err := url.Parse(c.BaseURL)
	if err != nil {
		return nil, fmt.Errorf("failed to parse base URL: %w", err)
	}

	cardURL := fmt.Sprintf("%s://%s/.well-known/agent-card.json", parsedURL.Scheme, parsedURL.Host)

	resp, err := c.httpClient.Get(cardURL)
	if err != nil {
		return nil, fmt.Errorf("failed to get agent card: %w", err)
	}
	defer resp.Body.Close()

	var card AgentCard
	if err := json.NewDecoder(resp.Body).Decode(&card); err != nil {
		return nil, fmt.Errorf("failed to decode agent card: %w", err)
	}

	return &card, nil
}
