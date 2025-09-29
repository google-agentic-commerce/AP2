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

"""Payment channel framework for micropayments in AP2.

This module provides the foundation for high-frequency, sub-cent transactions
between agents through state channels, enabling pay-per-use and streaming
payment models for AI inference and API calls.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from ap2.types.payment_request import PaymentCurrencyAmount


class ChannelState(str, Enum):
    """States of a payment channel lifecycle."""

    OPENING = 'opening'
    ACTIVE = 'active'
    CLOSING = 'closing'
    CLOSED = 'closed'
    DISPUTED = 'disputed'
    EXPIRED = 'expired'


class DisputeReason(str, Enum):
    """Reasons for payment channel disputes."""

    INVALID_STATE = 'invalid_state'
    STALE_UPDATE = 'stale_update'
    INVALID_SIGNATURE = 'invalid_signature'
    INSUFFICIENT_FUNDS = 'insufficient_funds'
    TIMEOUT = 'timeout'
    FRAUD_ATTEMPT = 'fraud_attempt'


class ChannelParticipant(BaseModel):
    """Participant in a payment channel."""

    participant_id: str = Field(
        ..., description='Unique identifier for the participant'
    )
    agent_did: str | None = Field(
        None, description='DID of the agent representing this participant'
    )
    wallet_address: str = Field(
        ..., description='Blockchain wallet address for settlements'
    )
    role: str = Field(
        ..., description='Role in the channel (payer, payee, mediator)'
    )
    public_key: str = Field(
        ..., description='Public key for channel signature verification'
    )
    initial_balance: PaymentCurrencyAmount = Field(
        ..., description='Initial balance contributed to the channel'
    )
    current_balance: PaymentCurrencyAmount = Field(
        ..., description='Current balance in the channel'
    )


class ChannelPolicy(BaseModel):
    """Policy governing payment channel behavior."""

    max_transaction_amount: PaymentCurrencyAmount = Field(
        ..., description='Maximum amount per transaction'
    )
    min_transaction_amount: PaymentCurrencyAmount = Field(
        ..., description='Minimum amount per transaction'
    )
    dispute_timeout_seconds: int = Field(
        default=86400,
        description='Time to challenge disputed states (24 hours)',
    )
    max_pending_updates: int = Field(
        default=1000, description='Maximum number of pending state updates'
    )
    settlement_threshold: PaymentCurrencyAmount = Field(
        ..., description='Balance threshold triggering automatic settlement'
    )
    fee_rate: float = Field(
        default=0.001, description='Transaction fee rate (0.1% default)'
    )
    auto_close_timeout: int = Field(
        default=604800, description='Auto-close timeout in seconds (7 days)'
    )


class PaymentVoucher(BaseModel):
    """Off-chain payment voucher for micropayments."""

    voucher_id: str = Field(
        ..., description='Unique identifier for this voucher'
    )
    channel_id: str = Field(..., description='Payment channel identifier')
    from_participant: str = Field(
        ..., description='ID of participant making payment'
    )
    to_participant: str = Field(
        ..., description='ID of participant receiving payment'
    )
    amount: PaymentCurrencyAmount = Field(
        ..., description='Amount being transferred'
    )
    nonce: int = Field(..., description='Monotonic nonce for replay protection')
    cumulative_amount: PaymentCurrencyAmount = Field(
        ..., description='Total amount transferred to this participant'
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


class ChannelUpdate(BaseModel):
    """State update for a payment channel."""

    update_id: str = Field(..., description='Unique identifier for this update')
    channel_id: str = Field(..., description='Payment channel identifier')
    sequence_number: int = Field(
        ..., description='Monotonic sequence number for ordering'
    )
    previous_state_hash: str = Field(
        ..., description='Hash of the previous channel state'
    )
    new_balances: dict[str, PaymentCurrencyAmount] = Field(
        ..., description='New balances for all participants'
    )
    included_vouchers: list[str] = Field(
        default_factory=list,
        description='List of voucher IDs included in this update',
    )
    timestamp: str = Field(
        description='When the update was created, in ISO 8601 format',
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
    signatures: dict[str, str] = Field(
        default_factory=dict, description='Signatures from participants'
    )
    state_hash: str = Field(
        ..., description='Hash of the new channel state after this update'
    )


class PaymentChannel(BaseModel):
    """Core payment channel for micropayment transactions."""

    channel_id: str = Field(
        ..., description='Unique identifier for this channel'
    )
    participants: list[ChannelParticipant] = Field(
        ...,
        description='List of channel participants',
        min_length=2,
        max_length=10,
    )
    state: ChannelState = Field(
        default=ChannelState.OPENING, description='Current channel state'
    )
    policy: ChannelPolicy = Field(
        ..., description='Policies governing this channel'
    )
    total_capacity: PaymentCurrencyAmount = Field(
        ..., description='Total capacity of the channel'
    )
    current_state_hash: str = Field(
        ..., description='Hash of the current channel state'
    )
    sequence_number: int = Field(
        default=0, description='Current sequence number'
    )
    created_at: str = Field(
        description='When the channel was created, in ISO 8601 format',
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
    expires_at: str = Field(
        ..., description='When the channel expires, in ISO 8601 format'
    )
    last_activity: str = Field(
        description='Last activity timestamp, in ISO 8601 format',
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
    dispute_info: dict[str, Any] | None = Field(
        None, description='Information about any active disputes'
    )
    settlement_info: dict[str, Any] | None = Field(
        None, description='Information about channel settlement'
    )

    def get_participant(self, participant_id: str) -> ChannelParticipant | None:
        """Get a participant by ID."""
        for participant in self.participants:
            if participant.participant_id == participant_id:
                return participant
        return None

    def is_expired(self, current_time: datetime | None = None) -> bool:
        """Check if the channel has expired."""
        if current_time is None:
            current_time = datetime.now(UTC)

        expires_at = datetime.fromisoformat(
            self.expires_at.replace('Z', '+00:00')
        )
        return current_time > expires_at

    def get_total_balance(self) -> PaymentCurrencyAmount:
        """Calculate total balance across all participants."""
        if not self.participants:
            return PaymentCurrencyAmount(currency='USD', value=0.0)

        currency = self.participants[0].current_balance.currency
        total_value = sum(p.current_balance.value for p in self.participants)

        return PaymentCurrencyAmount(currency=currency, value=total_value)

    def can_process_payment(
        self, from_id: str, to_id: str, amount: PaymentCurrencyAmount
    ) -> tuple[bool, str]:
        """Check if a payment can be processed."""
        # Check channel state
        if self.state != ChannelState.ACTIVE:
            return False, f'Channel state is {self.state}, not active'

        # Check expiry
        if self.is_expired():
            return False, 'Channel has expired'

        # Check participants exist
        payer = self.get_participant(from_id)
        payee = self.get_participant(to_id)

        if not payer:
            return False, f'Payer {from_id} not found in channel'
        if not payee:
            return False, f'Payee {to_id} not found in channel'

        # Check currency compatibility
        if amount.currency != payer.current_balance.currency:
            return False, 'Currency mismatch'

        # Check sufficient balance
        if payer.current_balance.value < amount.value:
            return False, 'Insufficient balance'

        # Check policy limits
        if amount.value > self.policy.max_transaction_amount.value:
            return False, 'Amount exceeds maximum transaction limit'

        if amount.value < self.policy.min_transaction_amount.value:
            return False, 'Amount below minimum transaction limit'

        return True, 'Payment can be processed'


class ChannelOpenRequest(BaseModel):
    """Request to open a new payment channel."""

    requesting_participant: ChannelParticipant = Field(
        ..., description='Participant requesting channel creation'
    )
    target_participant: ChannelParticipant = Field(
        ..., description='Target participant for the channel'
    )
    proposed_policy: ChannelPolicy = Field(
        ..., description='Proposed channel policies'
    )
    duration_hours: int = Field(
        default=168,
        description='Requested channel duration in hours (7 days default)',
    )
    initial_deposit: PaymentCurrencyAmount = Field(
        ..., description='Initial deposit from requesting participant'
    )
    purpose: str = Field(..., description='Purpose description for the channel')
    metadata: dict[str, Any] = Field(
        default_factory=dict, description='Additional channel metadata'
    )


class ChannelCloseRequest(BaseModel):
    """Request to close a payment channel."""

    channel_id: str = Field(..., description='Channel to close')
    requesting_participant: str = Field(
        ..., description='ID of participant requesting closure'
    )
    final_balances: dict[str, PaymentCurrencyAmount] = Field(
        ..., description='Proposed final balances for all participants'
    )
    reason: str = Field(
        default='normal_closure', description='Reason for channel closure'
    )
    force_close: bool = Field(
        default=False, description='Whether to force close without consensus'
    )
    signature: str = Field(..., description='Signature authorizing the closure')


class ChannelDispute(BaseModel):
    """Dispute information for a payment channel."""

    dispute_id: str = Field(
        ..., description='Unique identifier for the dispute'
    )
    channel_id: str = Field(..., description='Channel under dispute')
    disputing_participant: str = Field(
        ..., description='ID of participant raising the dispute'
    )
    dispute_reason: DisputeReason = Field(
        ..., description='Reason for the dispute'
    )
    contested_state: dict[str, Any] = Field(
        ..., description='The state being contested'
    )
    evidence: list[dict[str, Any]] = Field(
        default_factory=list, description='Evidence supporting the dispute'
    )
    resolution_deadline: str = Field(
        ..., description='Deadline for dispute resolution, in ISO 8601 format'
    )
    status: str = Field(
        default='open', description='Current status of the dispute'
    )
    created_at: str = Field(
        description='When the dispute was created, in ISO 8601 format',
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )


class ChannelRegistry(BaseModel):
    """Registry of active payment channels for an agent or service."""

    registry_id: str = Field(
        ..., description='Unique identifier for this registry'
    )
    owner_agent_did: str = Field(
        ..., description='DID of the agent owning this registry'
    )
    active_channels: dict[str, PaymentChannel] = Field(
        default_factory=dict, description='Map of channel_id to PaymentChannel'
    )
    channel_history: list[str] = Field(
        default_factory=list,
        description='Historical list of closed channel IDs',
    )
    total_volume: dict[str, float] = Field(
        default_factory=dict, description='Total volume by currency'
    )
    total_transactions: int = Field(
        default=0, description='Total number of transactions processed'
    )
    created_at: str = Field(
        description='When the registry was created, in ISO 8601 format',
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
    last_updated: str = Field(
        description='Last update timestamp, in ISO 8601 format',
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )

    def add_channel(self, channel: PaymentChannel) -> None:
        """Add a new channel to the registry."""
        self.active_channels[channel.channel_id] = channel
        self.last_updated = datetime.now(UTC).isoformat()

    def remove_channel(self, channel_id: str) -> PaymentChannel | None:
        """Remove a channel from active registry and move to history."""
        channel = self.active_channels.pop(channel_id, None)
        if channel:
            self.channel_history.append(channel_id)

            # Update statistics
            total_balance = channel.get_total_balance()
            currency = total_balance.currency
            if currency not in self.total_volume:
                self.total_volume[currency] = 0.0
            self.total_volume[currency] += total_balance.value

            self.last_updated = datetime.now(UTC).isoformat()

        return channel

    def get_channels_by_participant(
        self, participant_id: str
    ) -> list[PaymentChannel]:
        """Get all channels involving a specific participant."""
        result = []
        for channel in self.active_channels.values():
            if any(
                p.participant_id == participant_id for p in channel.participants
            ):
                result.append(channel)
        return result

    def get_total_balance_for_participant(
        self, participant_id: str, currency: str
    ) -> float:
        """Get total balance across all channels for a participant."""
        total = 0.0
        for channel in self.active_channels.values():
            participant = channel.get_participant(participant_id)
            if participant and participant.current_balance.currency == currency:
                total += participant.current_balance.value
        return total
