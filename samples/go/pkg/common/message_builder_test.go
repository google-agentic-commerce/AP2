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
	"testing"
)

func TestMessageBuilder(t *testing.T) {
	builder := NewMessageBuilder()

	message := builder.
		AddText("Hello, world!").
		AddData("key1", "value1").
		SetContextID("ctx-123").
		SetTaskID("task-456").
		Build()

	if len(message.Parts) != 2 {
		t.Errorf("Expected 2 parts, got %d", len(message.Parts))
	}

	if message.Parts[0].Text == "" {
		t.Error("Expected first part to have text")
	}

	if message.Parts[0].Text != "Hello, world!" {
		t.Errorf("Expected text 'Hello, world!', got '%s'", message.Parts[0].Text)
	}

	if message.Parts[1].Data == nil {
		t.Error("Expected second part to be DataPart")
	}

	if message.ContextID != "ctx-123" {
		t.Errorf("Expected context ID 'ctx-123', got '%s'", message.ContextID)
	}

	if message.TaskID != "task-456" {
		t.Errorf("Expected task ID 'task-456', got '%s'", message.TaskID)
	}

	if message.Role != RoleAgent {
		t.Errorf("Expected role 'agent', got '%s'", message.Role)
	}
}

func TestExtractTextParts(t *testing.T) {
	message := NewMessageBuilder().
		AddText("First").
		AddText("Second").
		Build()

	texts := ExtractTextParts(message)

	if len(texts) != 2 {
		t.Errorf("Expected 2 text parts, got %d", len(texts))
	}

	if texts[0] != "First" {
		t.Errorf("Expected 'First', got '%s'", texts[0])
	}

	if texts[1] != "Second" {
		t.Errorf("Expected 'Second', got '%s'", texts[1])
	}
}

func TestExtractDataParts(t *testing.T) {
	message := NewMessageBuilder().
		AddData("key1", "value1").
		AddData("key2", "value2").
		Build()

	dataParts := ExtractDataParts(message)

	if len(dataParts) != 2 {
		t.Errorf("Expected 2 data parts, got %d", len(dataParts))
	}
}

func TestFindDataPart(t *testing.T) {
	message := NewMessageBuilder().
		AddData("key1", "value1").
		AddData("key2", map[string]interface{}{"nested": "value"}).
		Build()

	dataParts := ExtractDataParts(message)

	val, found := FindDataPart("key1", dataParts)
	if !found {
		t.Error("Expected to find key1")
	}

	if val != "value1" {
		t.Errorf("Expected 'value1', got '%v'", val)
	}

	_, notFound := FindDataPart("nonexistent", dataParts)
	if notFound {
		t.Error("Should not have found nonexistent key")
	}
}
