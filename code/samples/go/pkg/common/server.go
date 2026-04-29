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
	s.router.Use(s.loggingMiddleware)
	s.router.HandleFunc(s.RPCURL, s.handleA2ARequest).Methods("POST")
	s.router.HandleFunc("/.well-known/agent-card.json", s.handleGetCard).Methods("GET")
	s.router.HandleFunc(s.RPCURL+"/.well-known/agent-card.json", s.handleGetCard).Methods("GET")
	s.router.HandleFunc("/health", s.handleHealth).Methods("GET")
}

func (s *AgentServer) loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		next.ServeHTTP(w, r)
	})
}

func (s *AgentServer) handleA2ARequest(w http.ResponseWriter, r *http.Request) {
	var rpcRequest JSONRPCRequest
	if err := json.NewDecoder(r.Body).Decode(&rpcRequest); err != nil {
		http.Error(w, fmt.Sprintf("Invalid request body: %v", err), http.StatusBadRequest)
		return
	}

	messageData, ok := rpcRequest.Params["message"]
	if !ok {
		s.sendJSONRPCError(w, rpcRequest.ID, -32602, "Missing 'message' in params")
		return
	}

	messageJSON, err := json.Marshal(messageData)
	if err != nil {
		s.sendJSONRPCError(w, rpcRequest.ID, -32603, "Failed to process message data")
		return
	}

	var message Message
	if err := json.Unmarshal(messageJSON, &message); err != nil {
		s.sendJSONRPCError(w, rpcRequest.ID, -32602, fmt.Sprintf("Invalid message format: %v", err))
		return
	}

	task, err := s.Executor.HandleRequest(&message, nil)
	if err != nil {
		s.sendJSONRPCError(w, rpcRequest.ID, -32603, fmt.Sprintf("Executor error: %v", err))
		return
	}

	// Convert task to map[string]interface{} for direct inclusion in result
	var result map[string]interface{}
	if task != nil {
		taskJSON, _ := json.Marshal(task)
		json.Unmarshal(taskJSON, &result)
	}

	rpcResponse := JSONRPCResponse{
		ID:      rpcRequest.ID,
		JSONRPC: "2.0",
		Result: result,
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(rpcResponse); err != nil {
		http.Error(w, "Failed to encode response", http.StatusInternalServerError)
		return
	}
}

func (s *AgentServer) sendJSONRPCError(w http.ResponseWriter, id string, code int, message string) {
	response := JSONRPCResponse{
		ID:      id,
		JSONRPC: "2.0",
		Error: &JSONRPCError{
			Code:    code,
			Message: message,
		},
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(response)
}

func (s *AgentServer) handleGetCard(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(s.AgentCard); err != nil {
		http.Error(w, "Failed to encode agent card", http.StatusInternalServerError)
		return
	}
}

func (s *AgentServer) handleHealth(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "healthy"})
}

func (s *AgentServer) Start() error {
	addr := fmt.Sprintf(":%d", s.Port)
	log.Printf("Starting %s on port %d", s.AgentCard.Name, s.Port)
	log.Printf("Agent Card URL: http://localhost%s%s/.well-known/agent-card.json", addr, s.RPCURL)
	log.Printf("RPC URL: http://localhost%s%s", addr, s.RPCURL)

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
