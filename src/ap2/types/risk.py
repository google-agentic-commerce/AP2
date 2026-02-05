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

"""Fiduciary Circuit Breaker (FCB) risk types for the Agent Payments Protocol.

This module provides structured types for the Risk Payload referenced in
AP2 Section 7.4 (Risk Signals). It implements the Fiduciary Circuit Breaker
pattern for runtime governance of autonomous agent transactions.

The FCB pattern provides:
- Trip conditions that evaluate agent behavior against predefined thresholds
- A state machine for governance (CLOSED → OPEN → HALF_OPEN)
- Human escalation protocol for exceptional cases
- Structured risk signals for network/issuer visibility
"""

from datetime import datetime
from datetime import timezone
from enum import Enum
from typing import Any
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


RISK_PAYLOAD_DATA_KEY = "ap2.risk.RiskPayload"
FCB_EVALUATION_DATA_KEY = "ap2.risk.FCBEvaluation"


class TripConditionType(str, Enum):
    """Categories of runtime risk checks that can trigger FCB.

    These trip conditions evaluate agent behavior beyond what mandates capture,
    focusing on cumulative, temporal, and anomalous patterns.
    """

    VALUE_THRESHOLD = "VALUE_THRESHOLD"
    """Single transaction exceeds monetary limit."""

    CUMULATIVE_THRESHOLD = "CUMULATIVE_THRESHOLD"
    """Running totals across transactions exceed threshold."""

    VELOCITY = "VELOCITY"
    """Too many actions in a time window (e.g., >10 txns/minute)."""

    AUTHORITY_SCOPE = "AUTHORITY_SCOPE"
    """Action outside the agent's delegated domain."""

    ANOMALY = "ANOMALY"
    """ML model detects unusual behavioral pattern."""

    TIME_BASED = "TIME_BASED"
    """Action during restricted time period."""

    DEVIATION = "DEVIATION"
    """Significant departure from historical baseline."""

    VENDOR_TRUST = "VENDOR_TRUST"
    """Transaction with unverified or untrusted counterparty."""

    CUSTOM = "CUSTOM"
    """Implementation-specific trip condition."""


class TripConditionStatus(str, Enum):
    """Result of evaluating a single trip condition."""

    PASS = "PASS"
    """Condition satisfied, no risk detected."""

    FAIL = "FAIL"
    """Condition failed, FCB should trip."""

    WARNING = "WARNING"
    """Approaching threshold, enhanced monitoring recommended."""


class FCBState(str, Enum):
    """States of the Fiduciary Circuit Breaker.

    The FCB operates as a state machine that governs agent autonomy:
    - CLOSED: Normal operation, agent acts autonomously
    - OPEN: All consequential actions blocked, requires human review
    - HALF_OPEN: Limited operations with enhanced monitoring
    - TERMINATED: Permanently halted, no recovery
    """

    CLOSED = "CLOSED"
    """Normal operation. Agent has full delegated authority."""

    OPEN = "OPEN"
    """All consequential actions blocked. Requires human review."""

    HALF_OPEN = "HALF_OPEN"
    """Limited operations permitted. Enhanced monitoring active."""

    TERMINATED = "TERMINATED"
    """Permanently halted. No recovery possible."""


class AgentModality(str, Enum):
    """Transaction modality indicating human presence."""

    HUMAN_PRESENT = "HUMAN_PRESENT"
    """User is in-session during the transaction."""

    HUMAN_NOT_PRESENT = "HUMAN_NOT_PRESENT"
    """User delegated task to agent, not in-session."""


class EscalationDecision(str, Enum):
    """Human approver's decision on an escalated action."""

    APPROVE = "APPROVE"
    """Action approved, FCB returns to CLOSED."""

    APPROVE_WITH_CONDITIONS = "APPROVE_WITH_CONDITIONS"
    """Action approved with monitoring, FCB moves to HALF_OPEN."""

    REJECT = "REJECT"
    """Action rejected, FCB moves to TERMINATED."""

    ESCALATE_FURTHER = "ESCALATE_FURTHER"
    """Forward to higher authority."""

    MODIFY_AND_APPROVE = "MODIFY_AND_APPROVE"
    """Adjust action parameters, then approve."""


class TripConditionResult(BaseModel):
    """Result of evaluating a single trip condition.

    Captures the outcome of one risk check, including the threshold,
    actual value, and any diagnostic message.
    """

    condition_type: TripConditionType = Field(
        ...,
        description="The type of trip condition that was evaluated.",
    )
    status: TripConditionStatus = Field(
        ...,
        description="Whether the condition passed, failed, or warned.",
    )
    threshold: Optional[float] = Field(
        None,
        description="The threshold value that was checked against.",
    )
    actual_value: Optional[float] = Field(
        None,
        description="The actual value observed.",
    )
    message: Optional[str] = Field(
        None,
        description="Human-readable explanation of the result.",
    )
    suggestion: Optional[str] = Field(
        None,
        description="Suggested action or resolution.",
    )


class HumanEscalation(BaseModel):
    """Details of a human escalation when FCB trips.

    Captures the escalation request, the human's decision, and any
    conditions attached to the approval.
    """

    escalation_id: str = Field(
        ...,
        description="Unique identifier for this escalation.",
    )
    triggered_at: str = Field(
        description="When the escalation was triggered, ISO 8601 format.",
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    approver_id: Optional[str] = Field(
        None,
        description="Identifier of the human who reviewed the escalation.",
    )
    decision: Optional[EscalationDecision] = Field(
        None,
        description="The human approver's decision.",
    )
    decided_at: Optional[str] = Field(
        None,
        description="When the decision was made, ISO 8601 format.",
    )
    conditions: Optional[list[str]] = Field(
        None,
        description="Conditions attached to an APPROVE_WITH_CONDITIONS decision.",
    )
    notes: Optional[str] = Field(
        None,
        description="Free-form notes from the approver.",
    )
    timeout_at: Optional[str] = Field(
        None,
        description="When the escalation will timeout if not resolved.",
    )
    default_action_on_timeout: Optional[EscalationDecision] = Field(
        EscalationDecision.REJECT,
        description="Action to take if escalation times out.",
    )


class FCBEvaluation(BaseModel):
    """Complete FCB evaluation result for a transaction.

    This is the primary object attached to the RiskPayload, containing
    the full evaluation results from the Fiduciary Circuit Breaker.
    """

    fcb_state: FCBState = Field(
        ...,
        description="Current state of the FCB after evaluation.",
    )
    previous_state: Optional[FCBState] = Field(
        None,
        description="FCB state before this evaluation (for state transitions).",
    )
    trips_evaluated: int = Field(
        ...,
        description="Total number of trip conditions evaluated.",
    )
    trips_triggered: int = Field(
        ...,
        description="Number of trip conditions that triggered (FAIL or WARNING).",
    )
    trip_results: list[TripConditionResult] = Field(
        default_factory=list,
        description="Individual results for each trip condition evaluated.",
    )
    risk_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Aggregate risk score from 0.0 (lowest) to 1.0 (highest).",
    )
    human_escalation: Optional[HumanEscalation] = Field(
        None,
        description="Escalation details if FCB tripped and required human review.",
    )
    evaluated_at: str = Field(
        description="When the FCB evaluation occurred, ISO 8601 format.",
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


class RiskPayload(BaseModel):
    """Container for risk-related signals in AP2 messages.

    This is the top-level risk object that can be attached to IntentMandate,
    CartMandate, and PaymentMandate messages via the `risk_data` DataPart.

    It provides visibility to merchants, payment processors, networks, and
    issuers about the runtime governance state of the agent transaction.
    """

    fcb_evaluation: Optional[FCBEvaluation] = Field(
        None,
        description="Fiduciary Circuit Breaker evaluation results.",
    )
    agent_modality: AgentModality = Field(
        AgentModality.HUMAN_PRESENT,
        description="Whether user was present during transaction.",
    )
    agent_id: Optional[str] = Field(
        None,
        description="Identifier of the agent initiating the transaction.",
    )
    agent_type: Optional[str] = Field(
        None,
        description="Type/category of agent (e.g., 'SHOPPING', 'B2B_BUYER').",
    )
    session_id: Optional[str] = Field(
        None,
        description="Session identifier for correlation.",
    )
    cumulative_session_value: Optional[float] = Field(
        None,
        description="Total transaction value in this session so far.",
    )
    transaction_count_today: Optional[int] = Field(
        None,
        description="Number of transactions by this agent today.",
    )
    custom_signals: Optional[dict[str, Any]] = Field(
        None,
        description="Implementation-specific risk signals.",
    )
