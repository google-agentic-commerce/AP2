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

// Package types provides Fiduciary Circuit Breaker (FCB) risk types for AP2.
//
// This file implements structured types for the Risk Payload referenced in
// AP2 Section 7.4 (Risk Signals). The FCB pattern provides runtime governance
// for autonomous agent transactions through:
//   - Trip conditions that evaluate agent behavior against predefined thresholds
//   - A state machine for governance (CLOSED → OPEN → HALF_OPEN)
//   - Human escalation protocol for exceptional cases
//   - Structured risk signals for network/issuer visibility
package types

import "time"

// Data key prefix for risk types.
const riskDataKeyPrefix = "ap2.risk."

// Data keys for AP2 message data parts.
var (
	RiskPayloadDataKey   = riskDataKeyPrefix + "RiskPayload"
	FCBEvaluationDataKey = riskDataKeyPrefix + "FCBEvaluation"
)

// TripConditionType represents categories of runtime risk checks.
type TripConditionType string

const (
	// TripConditionValueThreshold - Single transaction exceeds monetary limit.
	TripConditionValueThreshold TripConditionType = "VALUE_THRESHOLD"

	// TripConditionCumulativeThreshold - Running totals exceed threshold.
	TripConditionCumulativeThreshold TripConditionType = "CUMULATIVE_THRESHOLD"

	// TripConditionVelocity - Too many actions in a time window.
	TripConditionVelocity TripConditionType = "VELOCITY"

	// TripConditionAuthorityScope - Action outside delegated domain.
	TripConditionAuthorityScope TripConditionType = "AUTHORITY_SCOPE"

	// TripConditionAnomaly - ML model detects unusual pattern.
	TripConditionAnomaly TripConditionType = "ANOMALY"

	// TripConditionTimeBased - Action during restricted time period.
	TripConditionTimeBased TripConditionType = "TIME_BASED"

	// TripConditionDeviation - Significant departure from baseline.
	TripConditionDeviation TripConditionType = "DEVIATION"

	// TripConditionVendorTrust - Transaction with untrusted counterparty.
	TripConditionVendorTrust TripConditionType = "VENDOR_TRUST"

	// TripConditionCustom - Implementation-specific trip condition.
	TripConditionCustom TripConditionType = "CUSTOM"
)

// TripConditionStatus represents the result of evaluating a trip condition.
type TripConditionStatus string

const (
	// TripConditionStatusPass - Condition satisfied, no risk detected.
	TripConditionStatusPass TripConditionStatus = "PASS"

	// TripConditionStatusFail - Condition failed, FCB should trip.
	TripConditionStatusFail TripConditionStatus = "FAIL"

	// TripConditionStatusWarning - Approaching threshold.
	TripConditionStatusWarning TripConditionStatus = "WARNING"
)

// FCBState represents states of the Fiduciary Circuit Breaker.
type FCBState string

const (
	// FCBStateClosed - Normal operation, agent acts autonomously.
	FCBStateClosed FCBState = "CLOSED"

	// FCBStateOpen - All actions blocked, requires human review.
	FCBStateOpen FCBState = "OPEN"

	// FCBStateHalfOpen - Limited operations with enhanced monitoring.
	FCBStateHalfOpen FCBState = "HALF_OPEN"

	// FCBStateTerminated - Permanently halted, no recovery.
	FCBStateTerminated FCBState = "TERMINATED"
)

// AgentModality indicates whether human is present during transaction.
type AgentModality string

const (
	// AgentModalityHumanPresent - User is in-session.
	AgentModalityHumanPresent AgentModality = "HUMAN_PRESENT"

	// AgentModalityHumanNotPresent - User delegated task, not in-session.
	AgentModalityHumanNotPresent AgentModality = "HUMAN_NOT_PRESENT"
)

// EscalationDecision represents human approver's decision.
type EscalationDecision string

const (
	// EscalationDecisionApprove - Action approved, FCB returns to CLOSED.
	EscalationDecisionApprove EscalationDecision = "APPROVE"

	// EscalationDecisionApproveWithConditions - Approved with monitoring.
	EscalationDecisionApproveWithConditions EscalationDecision = "APPROVE_WITH_CONDITIONS"

	// EscalationDecisionReject - Action rejected, FCB terminates.
	EscalationDecisionReject EscalationDecision = "REJECT"

	// EscalationDecisionEscalateFurther - Forward to higher authority.
	EscalationDecisionEscalateFurther EscalationDecision = "ESCALATE_FURTHER"

	// EscalationDecisionModifyAndApprove - Adjust parameters, then approve.
	EscalationDecisionModifyAndApprove EscalationDecision = "MODIFY_AND_APPROVE"
)

// TripConditionResult captures the outcome of one risk check.
type TripConditionResult struct {
	ConditionType TripConditionType   `json:"condition_type"`         // Type of condition evaluated.
	Status        TripConditionStatus `json:"status"`                 // Pass, fail, or warning.
	Threshold     *float64            `json:"threshold,omitempty"`    // Limit checked against.
	ActualValue   *float64            `json:"actual_value,omitempty"` // Observed value.
	Message       *string             `json:"message,omitempty"`      // Human-readable explanation.
	Suggestion    *string             `json:"suggestion,omitempty"`   // Suggested resolution.
}

// HumanEscalation captures details when FCB trips and requires human review.
type HumanEscalation struct {
	EscalationID           string              `json:"escalation_id"`                       // Unique ID for this escalation.
	TriggeredAt            string              `json:"triggered_at,omitempty"`              // When triggered (RFC3339).
	ApproverID             *string             `json:"approver_id,omitempty"`               // Reviewer who handled this.
	Decision               *EscalationDecision `json:"decision,omitempty"`                  // Approver's decision.
	DecidedAt              *string             `json:"decided_at,omitempty"`                // When decided (RFC3339).
	Conditions             []string            `json:"conditions,omitempty"`                // Conditions for conditional approval.
	Notes                  *string             `json:"notes,omitempty"`                     // Approver notes.
	TimeoutAt              *string             `json:"timeout_at,omitempty"`                // Deadline for resolution (RFC3339).
	DefaultActionOnTimeout *EscalationDecision `json:"default_action_on_timeout,omitempty"` // Action if timeout expires.
}

// NewHumanEscalation creates a new HumanEscalation with timestamp.
func NewHumanEscalation(escalationID string) *HumanEscalation {
	defaultAction := EscalationDecisionReject
	return &HumanEscalation{
		EscalationID:           escalationID,
		TriggeredAt:            time.Now().UTC().Format(time.RFC3339),
		DefaultActionOnTimeout: &defaultAction,
	}
}

// FCBEvaluation contains complete FCB evaluation results.
type FCBEvaluation struct {
	FCBState        FCBState              `json:"fcb_state"`                  // Current FCB state.
	PreviousState   *FCBState             `json:"previous_state,omitempty"`   // State before this evaluation.
	TripsEvaluated  int                   `json:"trips_evaluated"`            // Total conditions checked.
	TripsTriggered  int                   `json:"trips_triggered"`            // Conditions that triggered.
	TripResults     []TripConditionResult `json:"trip_results,omitempty"`     // Results; use AddTripResult to update.
	RiskScore       *float64              `json:"risk_score,omitempty"`       // Aggregate score 0.0-1.0.
	HumanEscalation *HumanEscalation      `json:"human_escalation,omitempty"` // Escalation if FCB tripped.
	EvaluatedAt     string                `json:"evaluated_at,omitempty"`     // When evaluated (RFC3339).
}

// NewFCBEvaluation creates a new FCBEvaluation with timestamp.
func NewFCBEvaluation(state FCBState) *FCBEvaluation {
	return &FCBEvaluation{
		FCBState:    state,
		TripResults: []TripConditionResult{},
		EvaluatedAt: time.Now().UTC().Format(time.RFC3339),
	}
}

// AddTripResult adds a trip condition result and updates counters.
func (e *FCBEvaluation) AddTripResult(result TripConditionResult) {
	e.TripResults = append(e.TripResults, result)
	e.TripsEvaluated++
	if result.Status == TripConditionStatusFail || result.Status == TripConditionStatusWarning {
		e.TripsTriggered++
	}
}

// HasTripped returns true if any trip condition failed.
func (e *FCBEvaluation) HasTripped() bool {
	for _, r := range e.TripResults {
		if r.Status == TripConditionStatusFail {
			return true
		}
	}
	return false
}

// RiskPayload is the container for risk signals in AP2 messages.
type RiskPayload struct {
	FCBEvaluation          *FCBEvaluation `json:"fcb_evaluation,omitempty"`           // FCB evaluation results.
	AgentModality          AgentModality  `json:"agent_modality"`                     // Human present or not.
	AgentID                *string        `json:"agent_id,omitempty"`                 // Agent identifier.
	AgentType              *string        `json:"agent_type,omitempty"`               // Agent category.
	SessionID              *string        `json:"session_id,omitempty"`               // Session for correlation.
	CumulativeSessionValue *float64       `json:"cumulative_session_value,omitempty"` // Total session value so far.
	TransactionCountToday  *int           `json:"transaction_count_today,omitempty"`  // Transactions today.
	CustomSignals          map[string]any `json:"custom_signals,omitempty"`           // Implementation-specific signals.
}

// NewRiskPayload creates a new RiskPayload with default modality.
func NewRiskPayload(modality AgentModality) *RiskPayload {
	return &RiskPayload{
		AgentModality: modality,
	}
}
