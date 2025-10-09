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

"""Streaming payment primitives for real-time micropayments.

This module provides the foundation for streaming payments, enabling pay-per-token,
pay-per-second, or pay-per-API-call models essential for AI inference and
real-time services.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from ap2.types.payment_request import PaymentCurrencyAmount


class PaymentRateType(str, Enum):
    """Types of payment rate calculations."""

    PER_SECOND = 'per_second'
    PER_MINUTE = 'per_minute'
    PER_HOUR = 'per_hour'
    PER_TOKEN = 'per_token'
    PER_REQUEST = 'per_request'
    PER_BYTE = 'per_byte'
    PER_COMPUTE_UNIT = 'per_compute_unit'
    FLAT_RATE = 'flat_rate'
    TIERED_RATE = 'tiered_rate'


class StreamStatus(str, Enum):
    """Status of a streaming payment."""

    INITIALIZING = 'initializing'
    ACTIVE = 'active'
    PAUSED = 'paused'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class PaymentRate(BaseModel):
    """Rate structure for streaming payments."""

    rate_type: PaymentRateType = Field(
        ..., description='Type of rate calculation'
    )
    rate_amount: PaymentCurrencyAmount = Field(
        ..., description='Amount charged per unit'
    )
    minimum_charge: PaymentCurrencyAmount | None = Field(
        None, description='Minimum charge regardless of usage'
    )
    maximum_charge: PaymentCurrencyAmount | None = Field(
        None, description='Maximum charge cap'
    )
    billing_frequency_seconds: int = Field(
        default=1, description='How often to bill (in seconds)'
    )
    unit_description: str = Field(
        ..., description='Description of what constitutes one unit'
    )
    tier_thresholds: list[dict[str, Any]] | None = Field(
        None,
        description='Tiered pricing thresholds for complex rate structures',
    )


class StreamingPaymentVoucher(BaseModel):
    """Voucher for incremental streaming payments."""

    voucher_id: str = Field(
        ..., description='Unique identifier for this voucher'
    )
    stream_id: str = Field(
        ..., description='Streaming payment session identifier'
    )
    channel_id: str = Field(..., description='Payment channel identifier')
    sequence_number: int = Field(
        ..., description='Sequence number within the stream'
    )
    increment_amount: PaymentCurrencyAmount = Field(
        ..., description='Incremental amount for this voucher'
    )
    cumulative_amount: PaymentCurrencyAmount = Field(
        ..., description='Total amount streamed so far'
    )
    units_consumed: float = Field(
        ...,
        description='Number of units consumed (tokens, seconds, requests, etc.)',
    )
    cumulative_units: float = Field(
        ..., description='Total units consumed in the stream'
    )
    rate_applied: PaymentRate = Field(
        ..., description='Rate structure used for this calculation'
    )
    timestamp: str = Field(
        description='When the voucher was created, in ISO 8601 format',
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
    signature: str = Field(
        ..., description='Cryptographic signature of the voucher'
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description='Additional voucher metadata'
    )


class PaymentCheckpoint(BaseModel):
    """Checkpoint for resumable streaming payments."""

    checkpoint_id: str = Field(
        ..., description='Unique identifier for this checkpoint'
    )
    stream_id: str = Field(
        ..., description='Streaming payment session identifier'
    )
    sequence_number: int = Field(
        ..., description='Sequence number at checkpoint'
    )
    cumulative_amount: PaymentCurrencyAmount = Field(
        ..., description='Total amount at checkpoint'
    )
    cumulative_units: float = Field(
        ..., description='Total units consumed at checkpoint'
    )
    timestamp: str = Field(
        description='When the checkpoint was created, in ISO 8601 format',
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
    state_hash: str = Field(
        ..., description='Hash of the stream state at this checkpoint'
    )
    signatures: dict[str, str] = Field(
        default_factory=dict, description='Participant signatures on checkpoint'
    )


class StreamingPaymentPolicy(BaseModel):
    """Policy governing automated streaming payments."""

    max_stream_duration_seconds: int = Field(
        default=3600,
        description='Maximum duration for a single stream (1 hour default)',
    )
    checkpoint_frequency_seconds: int = Field(
        default=60, description='How often to create checkpoints'
    )
    auto_pause_threshold: PaymentCurrencyAmount = Field(
        ..., description='Amount threshold that triggers automatic pause'
    )
    max_cumulative_amount: PaymentCurrencyAmount = Field(
        ..., description='Maximum total amount for the stream'
    )
    rate_adjustment_allowed: bool = Field(
        default=False, description='Whether rates can be adjusted during stream'
    )
    dispute_resolution_timeout: int = Field(
        default=300,
        description='Timeout for resolving streaming disputes (5 minutes)',
    )
    quality_requirements: dict[str, Any] | None = Field(
        None, description='Service quality requirements (SLA)'
    )


class StreamingPaymentSession(BaseModel):
    """Active streaming payment session."""

    stream_id: str = Field(..., description='Unique identifier for this stream')
    channel_id: str = Field(..., description='Payment channel identifier')
    payer_id: str = Field(..., description='ID of the paying participant')
    payee_id: str = Field(..., description='ID of the receiving participant')
    service_description: str = Field(
        ..., description='Description of the service being paid for'
    )
    rate: PaymentRate = Field(..., description='Rate structure for this stream')
    policy: StreamingPaymentPolicy = Field(
        ..., description='Policy governing this stream'
    )
    status: StreamStatus = Field(
        default=StreamStatus.INITIALIZING, description='Current stream status'
    )
    start_time: str = Field(
        description='When the stream started, in ISO 8601 format',
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
    end_time: str | None = Field(
        None, description='When the stream ended, in ISO 8601 format'
    )
    current_sequence: int = Field(
        default=0, description='Current sequence number'
    )
    cumulative_amount: PaymentCurrencyAmount = Field(
        ..., description='Total amount streamed so far'
    )
    cumulative_units: float = Field(
        default=0.0, description='Total units consumed'
    )
    last_checkpoint: PaymentCheckpoint | None = Field(
        None, description='Most recent checkpoint'
    )
    vouchers: list[StreamingPaymentVoucher] = Field(
        default_factory=list, description='List of vouchers in this stream'
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description='Additional stream metadata'
    )

    def calculate_next_payment(
        self, units_consumed: float
    ) -> PaymentCurrencyAmount:
        """Calculate the next payment amount based on units consumed."""
        if self.rate.rate_type == PaymentRateType.FLAT_RATE:
            # Flat rate - pay the full amount once
            if self.current_sequence == 0:
                return self.rate.rate_amount
            return PaymentCurrencyAmount(
                currency=self.rate.rate_amount.currency, value=0.0
            )

        if self.rate.rate_type in [
            PaymentRateType.PER_SECOND,
            PaymentRateType.PER_MINUTE,
            PaymentRateType.PER_HOUR,
            PaymentRateType.PER_TOKEN,
            PaymentRateType.PER_REQUEST,
            PaymentRateType.PER_BYTE,
            PaymentRateType.PER_COMPUTE_UNIT,
        ]:
            # Unit-based pricing
            increment_amount = self.rate.rate_amount.value * units_consumed
            return PaymentCurrencyAmount(
                currency=self.rate.rate_amount.currency, value=increment_amount
            )

        if self.rate.rate_type == PaymentRateType.TIERED_RATE:
            # Tiered pricing - calculate based on cumulative usage
            return self._calculate_tiered_payment(units_consumed)

        raise ValueError(f'Unsupported rate type: {self.rate.rate_type}')

    def _calculate_tiered_payment(
        self, units_consumed: float
    ) -> PaymentCurrencyAmount:
        """Calculate payment for tiered rate structure."""
        if not self.rate.tier_thresholds:
            # Fallback to simple rate
            increment_amount = self.rate.rate_amount.value * units_consumed
            return PaymentCurrencyAmount(
                currency=self.rate.rate_amount.currency, value=increment_amount
            )

        new_total_units = self.cumulative_units + units_consumed
        old_total_units = self.cumulative_units

        total_cost = 0.0
        for tier in self.rate.tier_thresholds:
            tier_min = tier.get('min_units', 0)
            tier_max = tier.get('max_units', float('inf'))
            tier_rate = tier.get('rate_per_unit', self.rate.rate_amount.value)

            # Calculate how many units fall in this tier for the increment
            old_units_in_tier = max(
                0, min(old_total_units, tier_max) - tier_min
            )
            new_units_in_tier = max(
                0, min(new_total_units, tier_max) - tier_min
            )

            increment_units_in_tier = new_units_in_tier - old_units_in_tier
            if increment_units_in_tier > 0:
                total_cost += increment_units_in_tier * tier_rate

        return PaymentCurrencyAmount(
            currency=self.rate.rate_amount.currency, value=total_cost
        )

    def add_voucher(
        self, units_consumed: float, metadata: dict[str, Any] | None = None
    ) -> StreamingPaymentVoucher:
        """Add a new voucher to the stream."""
        increment_amount = self.calculate_next_payment(units_consumed)
        new_cumulative_amount = PaymentCurrencyAmount(
            currency=self.cumulative_amount.currency,
            value=self.cumulative_amount.value + increment_amount.value,
        )
        new_cumulative_units = self.cumulative_units + units_consumed

        voucher = StreamingPaymentVoucher(
            voucher_id=f'{self.stream_id}_{self.current_sequence + 1}',
            stream_id=self.stream_id,
            channel_id=self.channel_id,
            sequence_number=self.current_sequence + 1,
            increment_amount=increment_amount,
            cumulative_amount=new_cumulative_amount,
            units_consumed=units_consumed,
            cumulative_units=new_cumulative_units,
            rate_applied=self.rate,
            signature='placeholder_signature',  # Would be cryptographically signed
            metadata=metadata or {},
        )

        # Update stream state
        self.vouchers.append(voucher)
        self.current_sequence += 1
        self.cumulative_amount = new_cumulative_amount
        self.cumulative_units = new_cumulative_units

        return voucher

    def create_checkpoint(self) -> PaymentCheckpoint:
        """Create a checkpoint of the current stream state."""
        checkpoint = PaymentCheckpoint(
            checkpoint_id=f'{self.stream_id}_checkpoint_{len(self.vouchers)}',
            stream_id=self.stream_id,
            sequence_number=self.current_sequence,
            cumulative_amount=self.cumulative_amount,
            cumulative_units=self.cumulative_units,
            state_hash=f'hash_{self.stream_id}_{self.current_sequence}',  # Would be actual hash
            signatures={},  # Would be signed by participants
        )

        self.last_checkpoint = checkpoint
        return checkpoint

    def pause_stream(self, reason: str = '') -> None:
        """Pause the streaming payment."""
        self.status = StreamStatus.PAUSED
        self.metadata['pause_reason'] = reason
        self.metadata['paused_at'] = datetime.now(UTC).isoformat()

    def resume_stream(self) -> None:
        """Resume the streaming payment."""
        if self.status == StreamStatus.PAUSED:
            self.status = StreamStatus.ACTIVE
            self.metadata['resumed_at'] = datetime.now(UTC).isoformat()

    def complete_stream(self) -> None:
        """Complete the streaming payment."""
        self.status = StreamStatus.COMPLETED
        self.end_time = datetime.now(UTC).isoformat()

    def is_within_limits(self) -> tuple[bool, str]:
        """Check if the stream is within policy limits."""
        # Check cumulative amount limit
        if (
            self.cumulative_amount.value
            > self.policy.max_cumulative_amount.value
        ):
            return False, 'Cumulative amount exceeds policy limit'

        # Check duration limit
        if self.status == StreamStatus.ACTIVE:
            start_dt = datetime.fromisoformat(
                self.start_time.replace('Z', '+00:00')
            )
            current_dt = datetime.now(UTC)
            duration_seconds = (current_dt - start_dt).total_seconds()

            if duration_seconds > self.policy.max_stream_duration_seconds:
                return False, 'Stream duration exceeds policy limit'

        # Check auto-pause threshold
        if (
            self.cumulative_amount.value
            >= self.policy.auto_pause_threshold.value
        ):
            return False, 'Auto-pause threshold reached'

        return True, 'Stream is within limits'


class StreamingPaymentManager(BaseModel):
    """Manager for multiple streaming payment sessions."""

    manager_id: str = Field(
        ..., description='Unique identifier for this manager'
    )
    agent_did: str = Field(
        ..., description='DID of the agent using this manager'
    )
    active_streams: dict[str, StreamingPaymentSession] = Field(
        default_factory=dict, description='Active streaming sessions'
    )
    completed_streams: list[str] = Field(
        default_factory=list, description='List of completed stream IDs'
    )
    total_volume: dict[str, float] = Field(
        default_factory=dict, description='Total volume by currency'
    )
    total_streams: int = Field(
        default=0, description='Total number of streams created'
    )
    created_at: str = Field(
        description='When the manager was created, in ISO 8601 format',
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )

    def create_stream(
        self,
        channel_id: str,
        payer_id: str,
        payee_id: str,
        service_description: str,
        rate: PaymentRate,
        policy: StreamingPaymentPolicy,
    ) -> StreamingPaymentSession:
        """Create a new streaming payment session."""
        stream_id = f'stream_{self.agent_did}_{self.total_streams + 1}'

        stream = StreamingPaymentSession(
            stream_id=stream_id,
            channel_id=channel_id,
            payer_id=payer_id,
            payee_id=payee_id,
            service_description=service_description,
            rate=rate,
            policy=policy,
            cumulative_amount=PaymentCurrencyAmount(
                currency=rate.rate_amount.currency, value=0.0
            ),
        )

        self.active_streams[stream_id] = stream
        self.total_streams += 1

        return stream

    def get_stream(self, stream_id: str) -> StreamingPaymentSession | None:
        """Get an active streaming session."""
        return self.active_streams.get(stream_id)

    def complete_stream(self, stream_id: str) -> bool:
        """Complete a streaming session."""
        stream = self.active_streams.pop(stream_id, None)
        if stream:
            stream.complete_stream()
            self.completed_streams.append(stream_id)

            # Update statistics
            currency = stream.cumulative_amount.currency
            if currency not in self.total_volume:
                self.total_volume[currency] = 0.0
            self.total_volume[currency] += stream.cumulative_amount.value

            return True
        return False

    def get_streams_by_channel(
        self, channel_id: str
    ) -> list[StreamingPaymentSession]:
        """Get all streams for a specific channel."""
        return [
            stream
            for stream in self.active_streams.values()
            if stream.channel_id == channel_id
        ]

    def cleanup_expired_streams(self) -> list[str]:
        """Clean up expired streaming sessions."""
        expired_streams = []
        current_time = datetime.now(UTC)

        for stream_id, stream in list(self.active_streams.items()):
            start_time = datetime.fromisoformat(
                stream.start_time.replace('Z', '+00:00')
            )
            duration = (current_time - start_time).total_seconds()

            if duration > stream.policy.max_stream_duration_seconds:
                expired_streams.append(stream_id)
                self.complete_stream(stream_id)

        return expired_streams
