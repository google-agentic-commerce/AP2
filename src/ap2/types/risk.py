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

"""Structured Risk Payload schema for Section 7.4 Risk Signals.

Defines the types used for runtime risk governance between agents,
including trip conditions, circuit breaker (FCB) state, and the
overall risk payload that can be attached to mandates.
"""

from datetime import datetime
from datetime import timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class TripConditionType(str, Enum):
  """The type of trip condition evaluated during risk assessment."""

  VALUE_THRESHOLD = "VALUE_THRESHOLD"
  CUMULATIVE_THRESHOLD = "CUMULATIVE_THRESHOLD"
  VELOCITY = "VELOCITY"
  AUTHORITY_SCOPE = "AUTHORITY_SCOPE"
  ANOMALY = "ANOMALY"
  TIME_BASED = "TIME_BASED"
  DEVIATION = "DEVIATION"


class TripConditionStatus(str, Enum):
  """The result status of a trip condition evaluation."""

  PASS = "PASS"
  FAIL = "FAIL"
  WARNING = "WARNING"


class FCBState(str, Enum):
  """The state of the Fiduciary Circuit Breaker (FCB).

  The FCB acts as a runtime safety mechanism that can halt or throttle
  agent actions when risk thresholds are exceeded.
  """

  CLOSED = "CLOSED"
  OPEN = "OPEN"
  HALF_OPEN = "HALF_OPEN"
  TERMINATED = "TERMINATED"


class TripCondition(BaseModel):
  """A single trip condition evaluated as part of risk assessment.

  Each trip condition represents one risk check performed against the
  current transaction or agent action.
  """

  type: TripConditionType = Field(
      ...,
      description="The type of trip condition being evaluated.",
  )
  status: TripConditionStatus = Field(
      ...,
      description="The result status of this trip condition evaluation.",
  )
  threshold: Optional[float] = Field(
      None,
      description=(
          "The threshold value for this condition. For example, a maximum"
          " transaction amount or rate limit."
      ),
  )
  actual_value: Optional[float] = Field(
      None,
      description=(
          "The actual observed value that was compared against the threshold."
      ),
  )
  description: Optional[str] = Field(
      None,
      description=(
          "A human-readable description of the trip condition and its result."
      ),
  )


class RiskPayload(BaseModel):
  """Structured risk payload for Section 7.4 risk signal exchange.

  This payload captures the current risk assessment state, including
  the fiduciary circuit breaker state, evaluated trip conditions, an
  overall risk score, and the identity of the agent that produced the
  assessment.
  """

  fcb_state: FCBState = Field(
      ...,
      description=(
          "The current state of the Fiduciary Circuit Breaker. CLOSED means"
          " normal operation, OPEN means the circuit has tripped and actions"
          " are blocked, HALF_OPEN means the system is testing whether it is"
          " safe to resume, and TERMINATED means the circuit is permanently"
          " open."
      ),
  )
  trip_conditions: list[TripCondition] = Field(
      default_factory=list,
      description=(
          "The list of trip conditions that were evaluated as part of the"
          " risk assessment."
      ),
  )
  risk_score: Optional[float] = Field(
      None,
      description=(
          "An overall risk score for the transaction, typically in the range"
          " [0.0, 1.0] where 0.0 indicates no risk and 1.0 indicates maximum"
          " risk."
      ),
  )
  agent_identity: Optional[str] = Field(
      None,
      description=(
          "The identity of the agent that produced this risk assessment."
      ),
  )
  timestamp: str = Field(
      description=(
          "The date and time the risk assessment was produced, in ISO 8601"
          " format."
      ),
      default_factory=lambda: datetime.now(timezone.utc).isoformat(),
  )
