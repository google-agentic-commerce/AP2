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

"""AP2 type definitions."""

from ap2.models.mandate import (
    CART_MANDATE_DATA_KEY,
    INTENT_MANDATE_DATA_KEY,
    PAYMENT_MANDATE_DATA_KEY,
    CartContents,
    CartMandate,
    IntentMandate,
    PaymentMandate,
    PaymentMandateContents,
)
from ap2.models.risk import (
    FCB_EVALUATION_DATA_KEY,
    RISK_PAYLOAD_DATA_KEY,
    AgentModality,
    EscalationDecision,
    FCBEvaluation,
    FCBState,
    HumanEscalation,
    RiskPayload,
    TripConditionResult,
    TripConditionStatus,
    TripConditionType,
)


__all__ = [
    'CART_MANDATE_DATA_KEY',
    'FCB_EVALUATION_DATA_KEY',
    'INTENT_MANDATE_DATA_KEY',
    'PAYMENT_MANDATE_DATA_KEY',
    'RISK_PAYLOAD_DATA_KEY',
    'AgentModality',
    'CartContents',
    'CartMandate',
    'EscalationDecision',
    'FCBEvaluation',
    'FCBState',
    'HumanEscalation',
    'IntentMandate',
    'PaymentMandate',
    'PaymentMandateContents',
    'RiskPayload',
    'TripConditionResult',
    'TripConditionStatus',
    'TripConditionType',
]
