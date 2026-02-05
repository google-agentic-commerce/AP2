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

package types

import (
	"encoding/json"
	"testing"
)

func TestTripConditionTypes(t *testing.T) {
	expectedTypes := []TripConditionType{
		TripConditionValueThreshold,
		TripConditionCumulativeThreshold,
		TripConditionVelocity,
		TripConditionAuthorityScope,
		TripConditionAnomaly,
		TripConditionTimeBased,
		TripConditionDeviation,
		TripConditionVendorTrust,
		TripConditionCustom,
	}

	for _, ct := range expectedTypes {
		if ct == "" {
			t.Errorf("TripConditionType should not be empty")
		}
	}

	// Verify string values match expected
	if TripConditionValueThreshold != "VALUE_THRESHOLD" {
		t.Errorf("Expected VALUE_THRESHOLD, got %s", TripConditionValueThreshold)
	}
	if TripConditionCumulativeThreshold != "CUMULATIVE_THRESHOLD" {
		t.Errorf("Expected CUMULATIVE_THRESHOLD, got %s", TripConditionCumulativeThreshold)
	}
}

func TestFCBStates(t *testing.T) {
	states := []struct {
		state    FCBState
		expected string
	}{
		{FCBStateClosed, "CLOSED"},
		{FCBStateOpen, "OPEN"},
		{FCBStateHalfOpen, "HALF_OPEN"},
		{FCBStateTerminated, "TERMINATED"},
	}

	for _, tc := range states {
		if string(tc.state) != tc.expected {
			t.Errorf("Expected %s, got %s", tc.expected, tc.state)
		}
	}
}

func TestNewHumanEscalation(t *testing.T) {
	escalation := NewHumanEscalation("esc-12345")

	if escalation.EscalationID != "esc-12345" {
		t.Errorf("Expected escalation ID 'esc-12345', got '%s'", escalation.EscalationID)
	}

	if escalation.TriggeredAt == "" {
		t.Error("Expected triggered_at to be set")
	}

	if escalation.DefaultActionOnTimeout == nil {
		t.Error("Expected default_action_on_timeout to be set")
	}

	if *escalation.DefaultActionOnTimeout != EscalationDecisionReject {
		t.Errorf("Expected default action REJECT, got %s", *escalation.DefaultActionOnTimeout)
	}
}

func TestNewFCBEvaluation(t *testing.T) {
	eval := NewFCBEvaluation(FCBStateClosed)

	if eval.FCBState != FCBStateClosed {
		t.Errorf("Expected state CLOSED, got %s", eval.FCBState)
	}

	if eval.TripResults == nil {
		t.Error("Expected TripResults to be initialized")
	}

	if len(eval.TripResults) != 0 {
		t.Errorf("Expected empty TripResults, got %d", len(eval.TripResults))
	}

	if eval.EvaluatedAt == "" {
		t.Error("Expected evaluated_at to be set")
	}
}

func TestFCBEvaluationAddTripResult(t *testing.T) {
	eval := NewFCBEvaluation(FCBStateClosed)

	// Add a passing result
	passResult := TripConditionResult{
		ConditionType: TripConditionValueThreshold,
		Status:        TripConditionStatusPass,
	}
	eval.AddTripResult(passResult)

	if eval.TripsEvaluated != 1 {
		t.Errorf("Expected 1 trip evaluated, got %d", eval.TripsEvaluated)
	}
	if eval.TripsTriggered != 0 {
		t.Errorf("Expected 0 trips triggered, got %d", eval.TripsTriggered)
	}

	// Add a failing result
	threshold := 10000.0
	actual := 15000.0
	failResult := TripConditionResult{
		ConditionType: TripConditionValueThreshold,
		Status:        TripConditionStatusFail,
		Threshold:     &threshold,
		ActualValue:   &actual,
	}
	eval.AddTripResult(failResult)

	if eval.TripsEvaluated != 2 {
		t.Errorf("Expected 2 trips evaluated, got %d", eval.TripsEvaluated)
	}
	if eval.TripsTriggered != 1 {
		t.Errorf("Expected 1 trip triggered, got %d", eval.TripsTriggered)
	}

	// Add a warning result
	warnResult := TripConditionResult{
		ConditionType: TripConditionVelocity,
		Status:        TripConditionStatusWarning,
	}
	eval.AddTripResult(warnResult)

	if eval.TripsTriggered != 2 {
		t.Errorf("Expected 2 trips triggered (fail + warning), got %d", eval.TripsTriggered)
	}
}

func TestFCBEvaluationHasTripped(t *testing.T) {
	eval := NewFCBEvaluation(FCBStateClosed)

	// Initially should not have tripped
	if eval.HasTripped() {
		t.Error("Expected HasTripped to be false with no results")
	}

	// Add passing result
	eval.AddTripResult(TripConditionResult{
		ConditionType: TripConditionValueThreshold,
		Status:        TripConditionStatusPass,
	})

	if eval.HasTripped() {
		t.Error("Expected HasTripped to be false with only PASS")
	}

	// Add warning result
	eval.AddTripResult(TripConditionResult{
		ConditionType: TripConditionVelocity,
		Status:        TripConditionStatusWarning,
	})

	if eval.HasTripped() {
		t.Error("Expected HasTripped to be false with WARNING (not FAIL)")
	}

	// Add failing result
	eval.AddTripResult(TripConditionResult{
		ConditionType: TripConditionCumulativeThreshold,
		Status:        TripConditionStatusFail,
	})

	if !eval.HasTripped() {
		t.Error("Expected HasTripped to be true after FAIL")
	}
}

func TestNewRiskPayload(t *testing.T) {
	payload := NewRiskPayload(AgentModalityHumanPresent)

	if payload.AgentModality != AgentModalityHumanPresent {
		t.Errorf("Expected HUMAN_PRESENT, got %s", payload.AgentModality)
	}

	payloadNotPresent := NewRiskPayload(AgentModalityHumanNotPresent)
	if payloadNotPresent.AgentModality != AgentModalityHumanNotPresent {
		t.Errorf("Expected HUMAN_NOT_PRESENT, got %s", payloadNotPresent.AgentModality)
	}
}

func TestRiskPayloadJSONSerialization(t *testing.T) {
	agentID := "agent-shopping-001"
	sessionID := "sess-abc123"
	cumulative := 500.0
	txnCount := 3

	payload := &RiskPayload{
		FCBEvaluation:          NewFCBEvaluation(FCBStateClosed),
		AgentModality:          AgentModalityHumanNotPresent,
		AgentID:                &agentID,
		SessionID:              &sessionID,
		CumulativeSessionValue: &cumulative,
		TransactionCountToday:  &txnCount,
		CustomSignals: map[string]any{
			"merchant_trust_score": 0.95,
			"buyer_tier":           "enterprise",
		},
	}

	// Serialize to JSON
	jsonBytes, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("Failed to marshal RiskPayload: %v", err)
	}

	// Deserialize back
	var decoded RiskPayload
	if err := json.Unmarshal(jsonBytes, &decoded); err != nil {
		t.Fatalf("Failed to unmarshal RiskPayload: %v", err)
	}

	// Verify fields
	if decoded.AgentModality != AgentModalityHumanNotPresent {
		t.Errorf("Expected HUMAN_NOT_PRESENT, got %s", decoded.AgentModality)
	}

	if decoded.AgentID == nil || *decoded.AgentID != agentID {
		t.Errorf("Expected agent ID %s, got %v", agentID, decoded.AgentID)
	}

	if decoded.FCBEvaluation == nil {
		t.Error("Expected FCBEvaluation to be present")
	}

	if decoded.CustomSignals == nil {
		t.Error("Expected CustomSignals to be present")
	}
}

func TestTripConditionResultJSONSerialization(t *testing.T) {
	threshold := 50000.0
	actual := 75000.0
	message := "Transaction exceeds daily limit"
	suggestion := "Request manager approval"

	result := TripConditionResult{
		ConditionType: TripConditionCumulativeThreshold,
		Status:        TripConditionStatusFail,
		Threshold:     &threshold,
		ActualValue:   &actual,
		Message:       &message,
		Suggestion:    &suggestion,
	}

	jsonBytes, err := json.Marshal(result)
	if err != nil {
		t.Fatalf("Failed to marshal TripConditionResult: %v", err)
	}

	var decoded TripConditionResult
	if err := json.Unmarshal(jsonBytes, &decoded); err != nil {
		t.Fatalf("Failed to unmarshal TripConditionResult: %v", err)
	}

	if decoded.ConditionType != TripConditionCumulativeThreshold {
		t.Errorf("Expected CUMULATIVE_THRESHOLD, got %s", decoded.ConditionType)
	}

	if decoded.Status != TripConditionStatusFail {
		t.Errorf("Expected FAIL, got %s", decoded.Status)
	}

	if decoded.Threshold == nil || *decoded.Threshold != threshold {
		t.Errorf("Expected threshold %f, got %v", threshold, decoded.Threshold)
	}
}

func TestDataKeysConstant(t *testing.T) {
	if RiskPayloadDataKey != "ap2.risk.RiskPayload" {
		t.Errorf("Unexpected RiskPayloadDataKey: %s", RiskPayloadDataKey)
	}

	if FCBEvaluationDataKey != "ap2.risk.FCBEvaluation" {
		t.Errorf("Unexpected FCBEvaluationDataKey: %s", FCBEvaluationDataKey)
	}
}

func TestCompleteEvaluationScenario(t *testing.T) {
	// Simulate a complete FCB evaluation scenario

	// 1. Create evaluation in CLOSED state
	eval := NewFCBEvaluation(FCBStateClosed)

	// 2. Evaluate VALUE_THRESHOLD - passes
	threshold1 := 10000.0
	actual1 := 8500.0
	eval.AddTripResult(TripConditionResult{
		ConditionType: TripConditionValueThreshold,
		Status:        TripConditionStatusPass,
		Threshold:     &threshold1,
		ActualValue:   &actual1,
	})

	// 3. Evaluate CUMULATIVE - fails
	threshold2 := 50000.0
	actual2 := 65000.0
	msg := "Daily cumulative limit exceeded"
	eval.AddTripResult(TripConditionResult{
		ConditionType: TripConditionCumulativeThreshold,
		Status:        TripConditionStatusFail,
		Threshold:     &threshold2,
		ActualValue:   &actual2,
		Message:       &msg,
	})

	// 4. Evaluation should have tripped
	if !eval.HasTripped() {
		t.Error("Expected evaluation to have tripped")
	}

	// 5. Transition state to OPEN
	eval.PreviousState = &eval.FCBState
	eval.FCBState = FCBStateOpen

	// 6. Create escalation
	eval.HumanEscalation = NewHumanEscalation("esc-001")

	// 7. Wrap in RiskPayload
	agentID := "shopping-agent-prod"
	payload := &RiskPayload{
		FCBEvaluation: eval,
		AgentModality: AgentModalityHumanNotPresent,
		AgentID:       &agentID,
	}

	// 8. Verify full scenario
	if payload.FCBEvaluation.FCBState != FCBStateOpen {
		t.Errorf("Expected OPEN state, got %s", payload.FCBEvaluation.FCBState)
	}

	if payload.FCBEvaluation.TripsEvaluated != 2 {
		t.Errorf("Expected 2 evaluations, got %d", payload.FCBEvaluation.TripsEvaluated)
	}

	if payload.FCBEvaluation.TripsTriggered != 1 {
		t.Errorf("Expected 1 triggered, got %d", payload.FCBEvaluation.TripsTriggered)
	}

	if payload.FCBEvaluation.HumanEscalation == nil {
		t.Error("Expected HumanEscalation to be set")
	}
}
