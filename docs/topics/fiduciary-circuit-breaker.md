# Fiduciary Circuit Breaker (FCB) Extension

!!! info

    This extension provides structured risk types for AP2 Section 7.4 (Risk Signals).

    `v0.1-alpha` (see [roadmap](../roadmap.md))

## Overview

The **Fiduciary Circuit Breaker (FCB)** is a runtime governance pattern that complements AP2's mandate-based authorization. While mandates prove that an agent has authority to act, FCB monitors *how* the agent exercises that authority in real-time.

### Why FCB?

AP2 mandates validate authority at signing time:

- ✅ "Agent has a valid IntentMandate with $50,000 budget"
- ✅ "This transaction is within the mandate constraints"

But mandates don't address runtime behaviors:

- ❌ "Agent already spent $30,000 today across 10 transactions"
- ❌ "Agent is making purchases 3x faster than normal"
- ❌ "Agent is buying from an unfamiliar vendor in a high-risk region"

FCB fills this gap by providing **cross-transaction behavioral monitoring** that can trip and require human intervention when something looks wrong.

## Conceptual Model

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                    AGENT GOVERNANCE STACK                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Layer 3: RUNTIME GOVERNANCE (FCB)                                         │
│   ─────────────────────────────────                                         │
│   Question: "Should this action proceed RIGHT NOW?"                         │
│   Evaluates: Cumulative risk, velocity, anomalies, thresholds               │
│   Output: ALLOW / TRIP (escalate to human)                                  │
│                                                                             │
│   Layer 2: PAYMENT AUTHORIZATION (AP2 Mandates)                             │
│   ─────────────────────────────────────────────                             │
│   Question: "Does agent have cryptographic proof of authority?"             │
│   Evaluates: User-signed mandates, intent constraints                       │
│   Output: Valid credential / Reject                                         │
│                                                                             │
│   Layer 1: AGENT IDENTITY & DISCOVERY                                       │
│   ────────────────────────────────────                                      │
│   Question: "Is this agent authentic?"                                      │
│   Evaluates: Agent cards, trust registries                                  │
│   Output: Verified identity / Untrusted                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## FCB States

The FCB operates as a state machine:

| State | Behavior | Entry Condition |
| ----- | -------- | --------------- |
| **CLOSED** | Normal operation. Agent acts autonomously. | Initial state; human approves from OPEN; or conditions met from HALF_OPEN |
| **OPEN** | All actions blocked. Requires human review. | Any trip condition fails from CLOSED; or conditions violated from HALF_OPEN |
| **HALF_OPEN** | Limited operations with enhanced monitoring. | Human approves with conditions from OPEN |
| **TERMINATED** | Permanently halted. No recovery. | Human rejects from OPEN; or timeout |

### State Transitions

```text
CLOSED ──[trip condition fails]──► OPEN
   ▲                                  │
   │                    ┌─────────────┼─────────────┐
   │                    │             │             │
   │              [approve]   [approve w/conditions]  [reject]
   │                    │             │             │
   │                    │             ▼             ▼
   └────────────────────┘        HALF_OPEN    TERMINATED
                                     │
                           ┌─────────┴─────────┐
                           │                   │
                    [conditions met]    [conditions violated]
                           │                   │
                           ▼                   ▼
                        CLOSED               OPEN
```

## Trip Conditions

Trip conditions are predicate functions that evaluate agent behavior:

| Type | Description | Example |
| ---- | ----------- | ------- |
| `VALUE_THRESHOLD` | Single transaction exceeds limit | Order > $100,000 |
| `CUMULATIVE_THRESHOLD` | Running total exceeds threshold | Daily spend > $500,000 |
| `VELOCITY` | Too many actions too quickly | > 10 transactions/minute |
| `AUTHORITY_SCOPE` | Action outside delegated domain | Modifying payment account |
| `ANOMALY` | ML model detects unusual pattern | Behavior inconsistent with baseline |
| `TIME_BASED` | Action during restricted period | Trade outside market hours |
| `DEVIATION` | Significant departure from baseline | Price 30% below historical average |
| `VENDOR_TRUST` | Untrusted counterparty | New vendor in high-risk region |

## Usage in AP2 Messages

### Including RiskPayload in Messages

The `RiskPayload` can be attached to any AP2 message via the `risk_data` DataPart:

```json
{
  "messageId": "msg_123",
  "parts": [
    {
      "kind": "data",
      "data": {
        "ap2.mandates.PaymentMandate": { ... },
        "ap2.risk.RiskPayload": {
          "fcb_evaluation": {
            "fcb_state": "CLOSED",
            "trips_evaluated": 8,
            "trips_triggered": 0,
            "trip_results": [
              {
                "condition_type": "VALUE_THRESHOLD",
                "status": "PASS",
                "threshold": 100000,
                "actual_value": 45000
              },
              {
                "condition_type": "CUMULATIVE_THRESHOLD",
                "status": "PASS",
                "threshold": 500000,
                "actual_value": 125000
              }
            ],
            "risk_score": 0.15,
            "evaluated_at": "2026-02-03T14:30:00Z"
          },
          "agent_modality": "HUMAN_NOT_PRESENT",
          "agent_id": "agent_xyz",
          "agent_type": "B2B_BUYER",
          "session_id": "session_abc123",
          "cumulative_session_value": 125000,
          "transaction_count_today": 3
        }
      }
    }
  ]
}
```

### FCB Trip with Human Escalation

When FCB trips, the `human_escalation` field captures the escalation flow:

```json
{
  "ap2.risk.RiskPayload": {
    "fcb_evaluation": {
      "fcb_state": "HALF_OPEN",
      "previous_state": "OPEN",
      "trips_evaluated": 8,
      "trips_triggered": 2,
      "trip_results": [
        {
          "condition_type": "CUMULATIVE_THRESHOLD",
          "status": "FAIL",
          "threshold": 500000,
          "actual_value": 525000,
          "message": "Daily cumulative spend exceeds $500,000 limit"
        },
        {
          "condition_type": "VENDOR_TRUST",
          "status": "WARNING",
          "message": "New vendor not in approved registry"
        }
      ],
      "risk_score": 0.72,
      "human_escalation": {
        "escalation_id": "esc_789",
        "triggered_at": "2026-02-03T14:30:00Z",
        "approver_id": "user_john_smith",
        "decision": "APPROVE_WITH_CONDITIONS",
        "decided_at": "2026-02-03T14:45:00Z",
        "conditions": [
          "Add vendor to approved registry",
          "Enhanced monitoring for 7 days"
        ],
        "notes": "Approved given strong counterparty history"
      },
      "evaluated_at": "2026-02-03T14:30:00Z"
    },
    "agent_modality": "HUMAN_NOT_PRESENT"
  }
}
```

## Python Types

```python
from ap2.types.risk import (
    RiskPayload,
    FCBEvaluation,
    FCBState,
    TripConditionResult,
    TripConditionType,
    TripConditionStatus,
    AgentModality,
)

# Create an FCB evaluation
evaluation = FCBEvaluation(
    fcb_state=FCBState.CLOSED,
    trips_evaluated=3,
    trips_triggered=0,
    trip_results=[
        TripConditionResult(
            condition_type=TripConditionType.VALUE_THRESHOLD,
            status=TripConditionStatus.PASS,
            threshold=100000,
            actual_value=45000,
        )
    ],
    risk_score=0.15,
)

# Create risk payload
risk_payload = RiskPayload(
    fcb_evaluation=evaluation,
    agent_modality=AgentModality.HUMAN_NOT_PRESENT,
    agent_id="agent_xyz",
    session_id="session_abc123",
)
```

## Go Types

```go
import "github.com/google-agentic-commerce/ap2/samples/go/pkg/ap2/types"

// Create an FCB evaluation
evaluation := types.NewFCBEvaluation(types.FCBStateClosed)
threshold := 100000.0
actualValue := 45000.0
riskScore := 0.15
evaluation.AddTripResult(types.TripConditionResult{
    ConditionType: types.TripConditionValueThreshold,
    Status:        types.TripConditionStatusPass,
    Threshold:     &threshold,
    ActualValue:   &actualValue,
})
evaluation.RiskScore = &riskScore

// Create risk payload
riskPayload := types.NewRiskPayload(types.AgentModalityHumanNotPresent)
riskPayload.FCBEvaluation = evaluation
agentID := "agent_xyz"
riskPayload.AgentID = &agentID
```

## Benefits for Payment Ecosystem

### For Merchants

- Real-time visibility into agent behavior before accepting transaction
- Ability to require higher security for risky transactions

### For Payment Networks

- Standardized risk signals for authorization decisions
- Clear audit trail of FCB state and human approvals

### For Issuers

- Additional data points for fraud detection
- Visibility into agent vs. human-initiated transactions

### For Users

- Confidence that agents operate within guardrails
- Human oversight for exceptional cases

## References

- [AP2 Specification Section 7.4: Risk Signals](../specification.md#74-risk-signals)
- [Circuit Breaker Pattern - Michael Nygard, Release It! (2007)](https://pragprog.com/titles/mnee2/release-it-second-edition/)
