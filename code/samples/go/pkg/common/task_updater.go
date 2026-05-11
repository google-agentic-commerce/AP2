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
	"sync"

	"github.com/google/uuid"
)

type TaskUpdater struct {
	task  *Task
	mutex sync.Mutex
}

func NewTaskUpdater(contextID string) *TaskUpdater {
	return &TaskUpdater{
		task: &Task{
			ID:        uuid.New().String(),
			ContextID: contextID,
			Status: TaskStatus{
				State: TaskStateCreated,
			},
			History:   []Message{},
			Artifacts: []Artifact{},
		},
	}
}

func (tu *TaskUpdater) GetTask() *Task {
	tu.mutex.Lock()
	defer tu.mutex.Unlock()
	return tu.task
}

func (tu *TaskUpdater) GetContextID() string {
	return tu.task.ContextID
}

func (tu *TaskUpdater) AddMessage(message *Message) {
	tu.mutex.Lock()
	defer tu.mutex.Unlock()
	tu.task.History = append(tu.task.History, *message)
}

func (tu *TaskUpdater) AddArtifact(parts []Part) {
	tu.mutex.Lock()
	defer tu.mutex.Unlock()
	artifact := Artifact{
		ArtifactID: uuid.New().String(),
		Parts:      parts,
	}
	tu.task.Artifacts = append(tu.task.Artifacts, artifact)
}

func (tu *TaskUpdater) UpdateStatus(state TaskState, message *Message) {
	tu.mutex.Lock()
	defer tu.mutex.Unlock()
	tu.task.Status = TaskStatus{
		State:   state,
		Message: message,
	}
}

func (tu *TaskUpdater) Complete() {
	tu.UpdateStatus(TaskStateCompleted, nil)
}

func (tu *TaskUpdater) Failed(errorText string) {
	msg := NewMessageBuilder().
		AddText(errorText).
		Build()
	tu.UpdateStatus(TaskStateFailed, msg)
}

func (tu *TaskUpdater) NewAgentMessage(parts []Part) *Message {
	return &Message{
		Kind:      "message",
		MessageID: uuid.New().String(),
		Parts:     parts,
		Role:      RoleAgent,
		ContextID: tu.task.ContextID,
	}
}
