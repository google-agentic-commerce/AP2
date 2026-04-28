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
	"encoding/json"
	"fmt"
)

func ExtractTextParts(message *Message) []string {
	var texts []string
	for _, part := range message.Parts {
		if part.Text != "" {
			texts = append(texts, part.Text)
		}
	}
	return texts
}

func ExtractDataParts(message *Message) []map[string]interface{} {
	var dataParts []map[string]interface{}
	for _, part := range message.Parts {
		if part.Data != nil {
			dataParts = append(dataParts, part.Data)
		}
	}
	return dataParts
}

func FindDataPart(key string, dataParts []map[string]interface{}) (interface{}, bool) {
	for _, data := range dataParts {
		if val, exists := data[key]; exists {
			return val, true
		}
	}
	return nil, false
}

func ParseDataPart(key string, dataParts []map[string]interface{}, target interface{}) error {
	val, found := FindDataPart(key, dataParts)
	if !found {
		return fmt.Errorf("key %s not found in data parts", key)
	}

	jsonBytes, err := json.Marshal(val)
	if err != nil {
		return fmt.Errorf("failed to marshal data: %w", err)
	}

	if err := json.Unmarshal(jsonBytes, target); err != nil {
		return fmt.Errorf("failed to unmarshal to target: %w", err)
	}

	return nil
}
