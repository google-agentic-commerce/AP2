# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for Fiduciary Circuit Breaker (FCB) risk types."""

import json

import pytest

from ap2.types.risk import (
    AgentModality,
    EscalationDecision,
    FCB_EVALUATION_DATA_KEY,
    FCBEvaluation,
    FCBState,
    HumanEscalation,
    RISK_PAYLOAD_DATA_KEY,
    RiskPayload,
    TripConditionResult,
    TripConditionStatus,
    TripConditionType,
)


class TestTripConditionType:
    """Tests for TripConditionType enum."""

    def test_all_types_exist(self):
        """Verify all expected trip condition types are defined."""
        expected = [
            "VALUE_THRESHOLD",
            "CUMULATIVE_THRESHOLD",
            "VELOCITY",
            "AUTHORITY_SCOPE",
            "ANOMALY",
            "TIME_BASED",
            "DEVIATION",
            "VENDOR_TRUST",
            "CUSTOM",
        ]
        actual = [e.value for e in TripConditionType]
        assert set(expected) == set(actual)

    def test_string_values(self):
        """Verify enum values match string representation."""
        assert TripConditionType.VALUE_THRESHOLD == "VALUE_THRESHOLD"
        assert TripConditionType.CUMULATIVE_THRESHOLD == "CUMULATIVE_THRESHOLD"
        assert TripConditionType.VELOCITY == "VELOCITY"


class TestTripConditionStatus:
    """Tests for TripConditionStatus enum."""

    def test_all_statuses_exist(self):
        """Verify all expected statuses are defined."""
        assert TripConditionStatus.PASS == "PASS"
        assert TripConditionStatus.FAIL == "FAIL"
        assert TripConditionStatus.WARNING == "WARNING"


class TestFCBState:
    """Tests for FCBState enum."""

    def test_all_states_exist(self):
        """Verify all FCB states are defined."""
        assert FCBState.CLOSED == "CLOSED"
        assert FCBState.OPEN == "OPEN"
        assert FCBState.HALF_OPEN == "HALF_OPEN"
        assert FCBState.TERMINATED == "TERMINATED"


class TestAgentModality:
    """Tests for AgentModality enum."""

    def test_modalities(self):
        """Verify both modalities exist."""
        assert AgentModality.HUMAN_PRESENT == "HUMAN_PRESENT"
        assert AgentModality.HUMAN_NOT_PRESENT == "HUMAN_NOT_PRESENT"


class TestEscalationDecision:
    """Tests for EscalationDecision enum."""

    def test_all_decisions_exist(self):
        """Verify all escalation decisions are defined."""
        expected = [
            "APPROVE",
            "APPROVE_WITH_CONDITIONS",
            "REJECT",
            "ESCALATE_FURTHER",
            "MODIFY_AND_APPROVE",
        ]
        actual = [e.value for e in EscalationDecision]
        assert set(expected) == set(actual)


class TestTripConditionResult:
    """Tests for TripConditionResult model."""

    def test_minimal_result(self):
        """Test creating result with only required fields."""
        result = TripConditionResult(
            condition_type=TripConditionType.VALUE_THRESHOLD,
            status=TripConditionStatus.PASS,
        )
        assert result.condition_type == TripConditionType.VALUE_THRESHOLD
        assert result.status == TripConditionStatus.PASS
        assert result.threshold is None
        assert result.actual_value is None

    def test_full_result(self):
        """Test creating result with all fields."""
        result = TripConditionResult(
            condition_type=TripConditionType.CUMULATIVE_THRESHOLD,
            status=TripConditionStatus.FAIL,
            threshold=50000.0,
            actual_value=75000.0,
            message="Daily limit exceeded",
            suggestion="Request manager approval",
        )
        assert result.threshold == 50000.0
        assert result.actual_value == 75000.0
        assert result.message == "Daily limit exceeded"

    def test_json_serialization(self):
        """Test JSON round-trip."""
        result = TripConditionResult(
            condition_type=TripConditionType.VELOCITY,
            status=TripConditionStatus.WARNING,
            threshold=10.0,
            actual_value=8.0,
        )
        json_str = result.model_dump_json()
        decoded = TripConditionResult.model_validate_json(json_str)
        assert decoded.condition_type == result.condition_type
        assert decoded.status == result.status


class TestHumanEscalation:
    """Tests for HumanEscalation model."""

    def test_creation_with_defaults(self):
        """Test creating escalation with default values."""
        escalation = HumanEscalation(escalation_id="esc-12345")
        assert escalation.escalation_id == "esc-12345"
        assert escalation.triggered_at is not None
        assert escalation.default_action_on_timeout == EscalationDecision.REJECT

    def test_full_escalation(self):
        """Test creating escalation with all fields."""
        escalation = HumanEscalation(
            escalation_id="esc-001",
            triggered_at="2025-02-03T10:00:00Z",
            approver_id="manager-123",
            decision=EscalationDecision.APPROVE_WITH_CONDITIONS,
            decided_at="2025-02-03T10:15:00Z",
            conditions=["Enhanced monitoring for 24h", "Max single txn $5000"],
            notes="Approved after vendor verification",
        )
        assert escalation.decision == EscalationDecision.APPROVE_WITH_CONDITIONS
        assert len(escalation.conditions) == 2


class TestFCBEvaluation:
    """Tests for FCBEvaluation model."""

    def test_minimal_evaluation(self):
        """Test creating evaluation with required fields."""
        eval = FCBEvaluation(
            fcb_state=FCBState.CLOSED,
            trips_evaluated=0,
            trips_triggered=0,
        )
        assert eval.fcb_state == FCBState.CLOSED
        assert eval.trip_results == []

    def test_evaluation_with_results(self):
        """Test evaluation with trip results."""
        results = [
            TripConditionResult(
                condition_type=TripConditionType.VALUE_THRESHOLD,
                status=TripConditionStatus.PASS,
            ),
            TripConditionResult(
                condition_type=TripConditionType.CUMULATIVE_THRESHOLD,
                status=TripConditionStatus.FAIL,
            ),
        ]
        eval = FCBEvaluation(
            fcb_state=FCBState.OPEN,
            trips_evaluated=2,
            trips_triggered=1,
            trip_results=results,
            risk_score=0.75,
        )
        assert len(eval.trip_results) == 2
        assert eval.risk_score == 0.75

    def test_risk_score_bounds(self):
        """Test risk_score validation."""
        from pydantic import ValidationError

        # Valid score
        eval = FCBEvaluation(
            fcb_state=FCBState.CLOSED,
            trips_evaluated=1,
            trips_triggered=0,
            risk_score=0.5,
        )
        assert eval.risk_score == 0.5

        # Score at boundaries
        eval_min = FCBEvaluation(
            fcb_state=FCBState.CLOSED,
            trips_evaluated=1,
            trips_triggered=0,
            risk_score=0.0,
        )
        assert eval_min.risk_score == 0.0

        eval_max = FCBEvaluation(
            fcb_state=FCBState.CLOSED,
            trips_evaluated=1,
            trips_triggered=0,
            risk_score=1.0,
        )
        assert eval_max.risk_score == 1.0

        # Invalid scores - below minimum
        with pytest.raises(ValidationError):
            FCBEvaluation(
                fcb_state=FCBState.CLOSED,
                trips_evaluated=1,
                trips_triggered=0,
                risk_score=-0.1,
            )

        # Invalid scores - above maximum
        with pytest.raises(ValidationError):
            FCBEvaluation(
                fcb_state=FCBState.CLOSED,
                trips_evaluated=1,
                trips_triggered=0,
                risk_score=1.1,
            )

    def test_evaluation_with_escalation(self):
        """Test evaluation with human escalation."""
        escalation = HumanEscalation(
            escalation_id="esc-001",
            approver_id="manager-123",
            decision=EscalationDecision.APPROVE,
        )
        eval = FCBEvaluation(
            fcb_state=FCBState.HALF_OPEN,
            previous_state=FCBState.OPEN,
            trips_evaluated=3,
            trips_triggered=1,
            human_escalation=escalation,
        )
        assert eval.previous_state == FCBState.OPEN
        assert eval.human_escalation is not None


class TestRiskPayload:
    """Tests for RiskPayload model."""

    def test_minimal_payload(self):
        """Test creating payload with defaults."""
        payload = RiskPayload()
        assert payload.agent_modality == AgentModality.HUMAN_PRESENT
        assert payload.fcb_evaluation is None

    def test_full_payload(self):
        """Test creating payload with all fields."""
        eval = FCBEvaluation(
            fcb_state=FCBState.CLOSED,
            trips_evaluated=2,
            trips_triggered=0,
        )
        payload = RiskPayload(
            fcb_evaluation=eval,
            agent_modality=AgentModality.HUMAN_NOT_PRESENT,
            agent_id="shopping-agent-001",
            agent_type="SHOPPING",
            session_id="sess-abc123",
            cumulative_session_value=1500.0,
            transaction_count_today=5,
            custom_signals={
                "merchant_trust_score": 0.95,
                "buyer_tier": "enterprise",
            },
        )
        assert payload.agent_id == "shopping-agent-001"
        assert payload.custom_signals["buyer_tier"] == "enterprise"

    def test_json_serialization(self):
        """Test JSON round-trip for complex payload."""
        results = [
            TripConditionResult(
                condition_type=TripConditionType.VALUE_THRESHOLD,
                status=TripConditionStatus.PASS,
                threshold=10000.0,
                actual_value=8500.0,
            ),
        ]
        eval = FCBEvaluation(
            fcb_state=FCBState.CLOSED,
            trips_evaluated=1,
            trips_triggered=0,
            trip_results=results,
        )
        payload = RiskPayload(
            fcb_evaluation=eval,
            agent_modality=AgentModality.HUMAN_NOT_PRESENT,
            agent_id="test-agent",
        )

        # Serialize
        json_str = payload.model_dump_json()

        # Deserialize
        decoded = RiskPayload.model_validate_json(json_str)

        assert decoded.agent_id == "test-agent"
        assert decoded.fcb_evaluation is not None
        assert len(decoded.fcb_evaluation.trip_results) == 1

    def test_custom_signals_any_type(self):
        """Test custom_signals accepts various types."""
        payload = RiskPayload(
            custom_signals={
                "string_val": "hello",
                "int_val": 42,
                "float_val": 3.14,
                "bool_val": True,
                "list_val": [1, 2, 3],
                "nested": {"key": "value"},
            }
        )
        assert payload.custom_signals["int_val"] == 42
        assert payload.custom_signals["nested"]["key"] == "value"


class TestDataKeys:
    """Tests for data key constants."""

    def test_risk_payload_key(self):
        """Verify RISK_PAYLOAD_DATA_KEY constant."""
        # Compose expected value at runtime to avoid false positive secret detection
        expected = "ap2.risk." + "RiskPayload"
        assert RISK_PAYLOAD_DATA_KEY == expected

    def test_fcb_evaluation_key(self):
        """Verify FCB_EVALUATION_DATA_KEY constant."""
        # Compose expected value at runtime to avoid false positive secret detection
        expected = "ap2.risk." + "FCBEvaluation"
        assert FCB_EVALUATION_DATA_KEY == expected


class TestCompleteScenario:
    """Integration tests for complete FCB evaluation scenarios."""

    def test_b2b_quote_scenario(self):
        """Test complete B2B quote negotiation scenario.

        Scenario: Agent negotiating $85,000 order, triggers cumulative
        threshold, escalates to human, gets approved with conditions.
        """
        # Step 1: Evaluate trip conditions
        results = [
            TripConditionResult(
                condition_type=TripConditionType.VALUE_THRESHOLD,
                status=TripConditionStatus.PASS,
                threshold=100000.0,
                actual_value=85000.0,
                message="Single transaction within limit",
            ),
            TripConditionResult(
                condition_type=TripConditionType.CUMULATIVE_THRESHOLD,
                status=TripConditionStatus.FAIL,
                threshold=200000.0,
                actual_value=235000.0,
                message="Daily cumulative exceeds $200k limit",
                suggestion="Escalate to procurement manager",
            ),
            TripConditionResult(
                condition_type=TripConditionType.VENDOR_TRUST,
                status=TripConditionStatus.PASS,
                message="Vendor in approved list",
            ),
        ]

        # Step 2: FCB trips and opens
        eval = FCBEvaluation(
            fcb_state=FCBState.OPEN,
            previous_state=FCBState.CLOSED,
            trips_evaluated=3,
            trips_triggered=1,
            trip_results=results,
            risk_score=0.65,
        )

        # Step 3: Create escalation
        escalation = HumanEscalation(
            escalation_id="esc-b2b-001",
            triggered_at="2025-02-03T14:30:00Z",
            timeout_at="2025-02-03T15:30:00Z",
        )
        eval.human_escalation = escalation

        # Step 4: Human approves with conditions
        eval.human_escalation.approver_id = "procurement-mgr-456"
        eval.human_escalation.decision = EscalationDecision.APPROVE_WITH_CONDITIONS
        eval.human_escalation.decided_at = "2025-02-03T14:45:00Z"
        eval.human_escalation.conditions = [
            "Enhanced monitoring for 48 hours",
            "Require delivery confirmation before payment release",
        ]
        eval.human_escalation.notes = "Approved - vendor verified, Q4 budget allows"

        # Step 5: FCB moves to HALF_OPEN
        eval.previous_state = eval.fcb_state
        eval.fcb_state = FCBState.HALF_OPEN

        # Step 6: Wrap in RiskPayload
        payload = RiskPayload(
            fcb_evaluation=eval,
            agent_modality=AgentModality.HUMAN_NOT_PRESENT,
            agent_id="b2b-buyer-agent-001",
            agent_type="B2B_BUYER",
            session_id="negotiation-sess-789",
            cumulative_session_value=235000.0,
            transaction_count_today=4,
            custom_signals={
                "vendor_id": "vendor-acme-123",
                "contract_id": "contract-2025-001",
                "negotiation_rounds": 3,
            },
        )

        # Verify final state
        assert payload.fcb_evaluation.fcb_state == FCBState.HALF_OPEN
        assert payload.fcb_evaluation.human_escalation.decision == EscalationDecision.APPROVE_WITH_CONDITIONS
        assert len(payload.fcb_evaluation.human_escalation.conditions) == 2
        assert payload.agent_type == "B2B_BUYER"

        # Verify JSON serialization of complete scenario
        json_output = json.loads(payload.model_dump_json())
        assert json_output["fcb_evaluation"]["fcb_state"] == "HALF_OPEN"
        assert json_output["custom_signals"]["negotiation_rounds"] == 3
