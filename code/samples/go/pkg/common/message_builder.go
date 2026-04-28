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
	"github.com/google/uuid"
)

type MessageBuilder struct {
	message *Message
}

func NewMessageBuilder() *MessageBuilder {
	return &MessageBuilder{
		message: &Message{
			Kind:      "message",
			MessageID: uuid.New().String(),
			Parts:     []Part{},
			Role:      RoleAgent,
		},
	}
}

func (mb *MessageBuilder) AddText(text string) *MessageBuilder {
	mb.message.Parts = append(mb.message.Parts, Part{
		Kind: "text",
		Text: text,
	})
	return mb
}

func (mb *MessageBuilder) AddData(key string, data interface{}) *MessageBuilder {
	if data == nil {
		return mb
	}

	var nestedData map[string]interface{}
	if key != "" {
		nestedData = map[string]interface{}{key: data}
	} else {
		var ok bool
		nestedData, ok = data.(map[string]interface{})
		if !ok {
			nestedData = map[string]interface{}{"data": data}
		}
	}

	mb.message.Parts = append(mb.message.Parts, Part{
		Kind: "data",
		Data: nestedData,
	})
	return mb
}

func (mb *MessageBuilder) SetContextID(contextID string) *MessageBuilder {
	mb.message.ContextID = contextID
	return mb
}

func (mb *MessageBuilder) SetTaskID(taskID string) *MessageBuilder {
	mb.message.TaskID = taskID
	return mb
}

func (mb *MessageBuilder) Build() *Message {
	return mb.message
}
