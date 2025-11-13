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
	"context"
	"fmt"
	"log"
	"os"
	"strings"

	"github.com/google/generative-ai-go/genai"
	"google.golang.org/api/option"
)

type ToolFunc func(dataParts []map[string]interface{}, updater *TaskUpdater) error

type ToolInfo struct {
	Name        string
	Description string
	Function    ToolFunc
}

type FunctionResolver struct {
	client       *genai.Client
	model        *genai.GenerativeModel
	tools        []ToolInfo
	instructions string
}

func NewFunctionResolver(tools []ToolInfo, instructions string) (*FunctionResolver, error) {
	apiKey := os.Getenv("GOOGLE_API_KEY")
	if apiKey == "" {
		log.Println("Warning: GOOGLE_API_KEY not set, LLM-based tool routing disabled")
		return &FunctionResolver{
			tools:        tools,
			instructions: instructions,
		}, nil
	}

	ctx := context.Background()
	client, err := genai.NewClient(ctx, option.WithAPIKey(apiKey))
	if err != nil {
		return nil, fmt.Errorf("failed to create genai client: %w", err)
	}

	model := client.GenerativeModel("gemini-2.5-flash")
	model.SystemInstruction = &genai.Content{
		Parts: []genai.Part{genai.Text(instructions)},
	}

	var functionDeclarations []*genai.FunctionDeclaration
	for _, tool := range tools {
		functionDeclarations = append(functionDeclarations, &genai.FunctionDeclaration{
			Name:        tool.Name,
			Description: tool.Description,
		})
	}

	model.Tools = []*genai.Tool{
		{
			FunctionDeclarations: functionDeclarations,
		},
	}

	model.ToolConfig = &genai.ToolConfig{
		FunctionCallingConfig: &genai.FunctionCallingConfig{
			Mode: genai.FunctionCallingAny,
		},
	}

	return &FunctionResolver{
		client:       client,
		model:        model,
		tools:        tools,
		instructions: instructions,
	}, nil
}

func (fr *FunctionResolver) DetermineToolToUse(prompt string) (string, error) {
	if fr.client == nil {
		return fr.fallbackToolSelection(prompt), nil
	}

	ctx := context.Background()
	resp, err := fr.model.GenerateContent(ctx, genai.Text(prompt))
	if err != nil {
		log.Printf("LLM error, falling back to simple matching: %v", err)
		return fr.fallbackToolSelection(prompt), nil
	}

	if resp == nil || len(resp.Candidates) == 0 {
		return fr.fallbackToolSelection(prompt), nil
	}

	for _, candidate := range resp.Candidates {
		if candidate.Content == nil {
			continue
		}
		for _, part := range candidate.Content.Parts {
			if fc, ok := part.(genai.FunctionCall); ok {
				log.Printf("LLM selected tool: %s", fc.Name)
				return fc.Name, nil
			}
		}
	}

	return fr.fallbackToolSelection(prompt), nil
}

func (fr *FunctionResolver) fallbackToolSelection(prompt string) string {
	log.Printf("Using fallback tool selection for prompt: %s", prompt)

	for _, tool := range fr.tools {
		if containsIgnoreCase(prompt, tool.Name) {
			return tool.Name
		}
	}

	return "unknown"
}

func (fr *FunctionResolver) GetTool(name string) (ToolFunc, error) {
	for _, tool := range fr.tools {
		if tool.Name == name {
			return tool.Function, nil
		}
	}
	return nil, fmt.Errorf("tool not found: %s", name)
}

func (fr *FunctionResolver) Close() {
	if fr.client != nil {
		fr.client.Close()
	}
}

func containsIgnoreCase(s, substr string) bool {
	return strings.Contains(strings.ToLower(s), strings.ToLower(substr))
}
