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
	"log"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"github.com/gorilla/mux"
)

type AgentExecutor interface {
	HandleRequest(message *Message, currentTask *Task) (*Task, error)
}

type AgentServer struct {
	Port      int
	AgentCard *AgentCard
	Executor  AgentExecutor
	RPCURL    string
	router    *mux.Router
}

func NewAgentServer(port int, agentCard *AgentCard, executor AgentExecutor, rpcURL string) *AgentServer {
	server := &AgentServer{
		Port:      port,
		AgentCard: agentCard,
		Executor:  executor,
		RPCURL:    rpcURL,
		router:    mux.NewRouter(),
	}
	server.setupRoutes()
	return server
}

func (s *AgentServer) setupRoutes() {
	s.router.HandleFunc(s.RPCURL, s.handleA2ARequest).Methods("POST")
	s.router.HandleFunc("/.well-known/agent-card.json", s.handleGetCard).Methods("GET")
	s.router.HandleFunc("/health", s.handleHealth).Methods("GET")
}

func (s *AgentServer) handleA2ARequest(w http.ResponseWriter, r *http.Request) {
	var message Message
	if err := json.NewDecoder(r.Body).Decode(&message); err != nil {
		log.Printf("Failed to decode request: %v", err)
		http.Error(w, fmt.Sprintf("Invalid request body: %v", err), http.StatusBadRequest)
		return
	}

	log.Printf("Received A2A message: %s", message.MessageID)

	task, err := s.Executor.HandleRequest(&message, nil)
	if err != nil {
		log.Printf("Error handling request: %v", err)
		http.Error(w, fmt.Sprintf("Error processing request: %v", err), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(task); err != nil {
		log.Printf("Failed to encode response: %v", err)
		http.Error(w, "Failed to encode response", http.StatusInternalServerError)
		return
	}
}

func (s *AgentServer) handleGetCard(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(s.AgentCard); err != nil {
		log.Printf("Failed to encode agent card: %v", err)
		http.Error(w, "Failed to encode agent card", http.StatusInternalServerError)
		return
	}
}

func (s *AgentServer) handleHealth(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(map[string]string{"status": "healthy"}); err != nil {
		log.Printf("Failed to encode health response: %v", err)
	}
}

func (s *AgentServer) Start() error {
	addr := fmt.Sprintf(":%d", s.Port)
	log.Printf("Starting %s on %s", s.AgentCard.Name, addr)
	log.Printf("Agent card available at: http://localhost%s/.well-known/agent-card.json", addr)

	server := &http.Server{
		Addr:         addr,
		Handler:      s.router,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	return server.ListenAndServe()
}

func LoadAgentCard(agentDir string) (*AgentCard, error) {
	cardPath := filepath.Join(agentDir, "agent.json")
	data, err := os.ReadFile(cardPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read agent card: %w", err)
	}

	var card AgentCard
	if err := json.Unmarshal(data, &card); err != nil {
		return nil, fmt.Errorf("failed to parse agent card: %w", err)
	}

	return &card, nil
}
