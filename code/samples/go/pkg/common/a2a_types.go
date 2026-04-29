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

type Role string

const (
	RoleAgent Role = "agent"
	RoleUser  Role = "user"
)

type TextPart struct {
	Text string `json:"text"`
}

type DataPart struct {
	Data map[string]interface{} `json:"data"`
}

type Part struct {
	Kind     string                 `json:"kind,omitempty"`
	Text     string                 `json:"text,omitempty"`
	Data     map[string]interface{} `json:"data,omitempty"`
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

type Message struct {
	Kind              string                 `json:"kind,omitempty"`
	MessageID         string                 `json:"messageId"`
	Parts             []Part                 `json:"parts"`
	Role              Role                   `json:"role"`
	ContextID         string                 `json:"contextId,omitempty"`
	TaskID            string                 `json:"taskId,omitempty"`
	Extensions        map[string]interface{} `json:"extensions,omitempty"`
	Metadata          map[string]interface{} `json:"metadata,omitempty"`
	ReferenceTaskIds  []string               `json:"referenceTaskIds,omitempty"`
}

type TaskState string

const (
	TaskStateCreated   TaskState = "created"
	TaskStatePending   TaskState = "pending"
	TaskStateCompleted TaskState = "completed"
	TaskStateFailed    TaskState = "failed"
)

type TaskStatus struct {
	State   TaskState `json:"state"`
	Message *Message  `json:"message,omitempty"`
}

type Artifact struct {
	ArtifactID string `json:"artifactId"`
	Parts      []Part `json:"parts"`
}

type Task struct {
	ID        string     `json:"id"`
	ContextID string     `json:"contextId"`
	Status    TaskStatus `json:"status"`
	History   []Message  `json:"history"`
	Artifacts []Artifact `json:"artifacts"`
}

type AgentCard struct {
	Name               string            `json:"name"`
	Description        string            `json:"description"`
	URL                string            `json:"url"`
	PreferredTransport string            `json:"preferredTransport"`
	ProtocolVersion    string            `json:"protocolVersion"`
	Version            string            `json:"version"`
	DefaultInputModes  []string          `json:"defaultInputModes"`
	DefaultOutputModes []string          `json:"defaultOutputModes"`
	Capabilities       AgentCapabilities `json:"capabilities"`
	Skills             []Skill           `json:"skills"`
}

type AgentCapabilities struct {
	Extensions []Extension `json:"extensions"`
}

type Extension struct {
	URI         string `json:"uri"`
	Description string `json:"description"`
	Required    bool   `json:"required"`
}

type Skill struct {
	ID          string                 `json:"id"`
	Name        string                 `json:"name"`
	Description string                 `json:"description"`
	Parameters  map[string]interface{} `json:"parameters,omitempty"`
	Tags        []string               `json:"tags,omitempty"`
}
