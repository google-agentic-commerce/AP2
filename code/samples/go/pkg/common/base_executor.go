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
	"fmt"
)

type BaseExecutor struct {
	SupportedExtensions map[string]bool
	Tools               []ToolInfo
	ToolResolver        *FunctionResolver
	SystemPrompt        string
}

func NewBaseExecutor(extensions []Extension, tools []ToolInfo, systemPrompt string) (*BaseExecutor, error) {
	extMap := make(map[string]bool)
	for _, ext := range extensions {
		extMap[ext.URI] = true
	}

	resolver, err := NewFunctionResolver(tools, systemPrompt)
	if err != nil {
		return nil, fmt.Errorf("failed to create function resolver: %w", err)
	}

	return &BaseExecutor{
		SupportedExtensions: extMap,
		Tools:               tools,
		ToolResolver:        resolver,
		SystemPrompt:        systemPrompt,
	}, nil
}

func (be *BaseExecutor) HandleRequestWithTools(message *Message, _ *Task, validateFunc func([]map[string]interface{}, *TaskUpdater) bool) (*Task, error) {
	contextID := message.ContextID
	if contextID == "" {
		contextID = message.MessageID
	}

	updater := NewTaskUpdater(contextID)
	updater.AddMessage(message)

	dataParts := ExtractDataParts(message)
	textParts := ExtractTextParts(message)

	if validateFunc != nil {
		if !validateFunc(dataParts, updater) {
			return updater.GetTask(), nil
		}
	}

	if len(textParts) == 0 {
		updater.Failed("No text instructions provided")
		return updater.GetTask(), nil
	}

	prompt := textParts[0]

	toolName, err := be.ToolResolver.DetermineToolToUse(prompt)
	if err != nil {
		updater.Failed(fmt.Sprintf("Failed to determine tool: %v", err))
		return updater.GetTask(), nil
	}

	toolFunc, err := be.ToolResolver.GetTool(toolName)
	if err != nil {
		updater.Failed(fmt.Sprintf("Tool not found: %s", toolName))
		return updater.GetTask(), nil
	}

	toolFunc(dataParts, updater)

	return updater.GetTask(), nil
}

func (be *BaseExecutor) Close() {
	if be.ToolResolver != nil {
		be.ToolResolver.Close()
	}
}
