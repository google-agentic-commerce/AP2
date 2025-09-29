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

"""Channel lifecycle management for micropayment channels."""

import hashlib
import uuid

from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

from ap2.types.payment_channels import (
    ChannelCloseRequest,
    ChannelDispute,
    ChannelOpenRequest,
    ChannelParticipant,
    ChannelState,
    DisputeReason,
    PaymentChannel,
    PaymentVoucher,
)
from ap2.types.payment_request import PaymentCurrencyAmount


class ChannelOperationResult(BaseModel):
    """Result of a channel operation."""

    success: bool = Field(..., description='Whether the operation succeeded')
    channel_id: str | None = Field(None, description='Channel ID if applicable')
    message: str = Field(..., description='Result message')
    data: dict[str, Any] = Field(
        default_factory=dict, description='Additional result data'
    )


class ChannelManager(BaseModel):
    """Manages payment channel lifecycle and operations."""

    manager_id: str = Field(
        ..., description='Unique identifier for this manager'
    )
    agent_did: str = Field(
        ..., description='DID of the agent using this manager'
    )
    active_channels: dict[str, PaymentChannel] = Field(
        default_factory=dict, description='Active payment channels'
    )
    channel_history: list[str] = Field(
        default_factory=list, description='Historical channel IDs'
    )
    pending_operations: dict[str, dict[str, Any]] = Field(
        default_factory=dict, description='Pending channel operations'
    )
    security_config: dict[str, Any] = Field(
        default_factory=dict, description='Security configuration'
    )

    def open_channel(
        self, request: ChannelOpenRequest
    ) -> ChannelOperationResult:
        """Open a new payment channel."""
        try:
            # Generate channel ID
            channel_id = f'ch_{uuid.uuid4()}'

            # Validate participants
            if (
                request.requesting_participant.participant_id
                == request.target_participant.participant_id
            ):
                return ChannelOperationResult(
                    success=False,
                    message='Requesting and target participants cannot be the same',
                )

            # Create channel
            participants = [
                request.requesting_participant,
                request.target_participant,
            ]

            # Calculate total capacity
            total_capacity = PaymentCurrencyAmount(
                currency=request.initial_deposit.currency,
                value=sum(p.initial_balance.value for p in participants),
            )

            # Set expiry time
            expiry_time = datetime.now(UTC) + timedelta(
                hours=request.duration_hours
            )

            channel = PaymentChannel(
                channel_id=channel_id,
                participants=participants,
                state=ChannelState.OPENING,
                policy=request.proposed_policy,
                total_capacity=total_capacity,
                current_state_hash=self._calculate_state_hash(
                    channel_id, participants
                ),
                expires_at=expiry_time.isoformat(),
            )

            # Store the channel
            self.active_channels[channel_id] = channel

            return ChannelOperationResult(
                success=True,
                channel_id=channel_id,
                message=f'Channel {channel_id} opened successfully',
                data={
                    'channel': channel.model_dump(),
                    'next_step': 'activate_channel',
                },
            )

        except Exception as e:
            return ChannelOperationResult(
                success=False, message=f'Failed to open channel: {e!s}'
            )

    def activate_channel(self, channel_id: str) -> ChannelOperationResult:
        """Activate a channel after both parties confirm."""
        channel = self.active_channels.get(channel_id)
        if not channel:
            return ChannelOperationResult(
                success=False, message=f'Channel {channel_id} not found'
            )

        if channel.state != ChannelState.OPENING:
            return ChannelOperationResult(
                success=False,
                message=f'Channel {channel_id} is not in opening state',
            )

        # In a real implementation, this would verify both participants have confirmed
        channel.state = ChannelState.ACTIVE
        channel.last_activity = datetime.now(UTC).isoformat()

        return ChannelOperationResult(
            success=True,
            channel_id=channel_id,
            message=f'Channel {channel_id} activated successfully',
        )

    def process_payment(
        self,
        channel_id: str,
        from_participant: str,
        to_participant: str,
        amount: PaymentCurrencyAmount,
        metadata: dict[str, Any] | None = None,
    ) -> ChannelOperationResult:
        """Process a payment through the channel."""
        channel = self.active_channels.get(channel_id)
        if not channel:
            return ChannelOperationResult(
                success=False, message=f'Channel {channel_id} not found'
            )

        # Check if payment can be processed
        can_process, reason = channel.can_process_payment(
            from_participant, to_participant, amount
        )
        if not can_process:
            return ChannelOperationResult(
                success=False, message=f'Payment rejected: {reason}'
            )

        # Create payment voucher
        voucher = PaymentVoucher(
            voucher_id=f'voucher_{uuid.uuid4()}',
            channel_id=channel_id,
            from_participant=from_participant,
            to_participant=to_participant,
            amount=amount,
            nonce=channel.sequence_number + 1,
            cumulative_amount=amount,  # Simplified - would track cumulative properly
            signature=self._sign_voucher(channel_id, from_participant, amount),
            metadata=metadata or {},
        )

        # Update channel balances
        payer = channel.get_participant(from_participant)
        payee = channel.get_participant(to_participant)

        if payer and payee:
            payer.current_balance.value -= amount.value
            payee.current_balance.value += amount.value

            # Update channel state
            channel.sequence_number += 1
            channel.last_activity = datetime.now(UTC).isoformat()
            channel.current_state_hash = self._calculate_state_hash(
                channel_id, channel.participants
            )

        return ChannelOperationResult(
            success=True,
            channel_id=channel_id,
            message='Payment processed successfully',
            data={
                'voucher': voucher.model_dump(),
                'new_balances': {
                    p.participant_id: p.current_balance.model_dump()
                    for p in channel.participants
                },
            },
        )

    def close_channel(
        self, request: ChannelCloseRequest
    ) -> ChannelOperationResult:
        """Close a payment channel."""
        channel = self.active_channels.get(request.channel_id)
        if not channel:
            return ChannelOperationResult(
                success=False, message=f'Channel {request.channel_id} not found'
            )

        if channel.state not in [ChannelState.ACTIVE, ChannelState.CLOSING]:
            return ChannelOperationResult(
                success=False,
                message=f'Channel {request.channel_id} cannot be closed in state {channel.state}',
            )

        try:
            # Validate final balances
            if not self._validate_final_balances(
                channel, request.final_balances
            ):
                return ChannelOperationResult(
                    success=False,
                    message='Final balances do not match channel state',
                )

            # Update channel state
            channel.state = (
                ChannelState.CLOSING
                if not request.force_close
                else ChannelState.CLOSED
            )
            channel.settlement_info = {
                'final_balances': {
                    k: v.model_dump() for k, v in request.final_balances.items()
                },
                'closed_by': request.requesting_participant,
                'close_reason': request.reason,
                'closure_time': datetime.now(UTC).isoformat(),
            }

            if request.force_close or channel.state == ChannelState.CLOSED:
                # Move to history
                self.channel_history.append(request.channel_id)
                del self.active_channels[request.channel_id]

            return ChannelOperationResult(
                success=True,
                channel_id=request.channel_id,
                message=f'Channel {request.channel_id} {"closed" if channel.state == ChannelState.CLOSED else "closing"}',
                data=channel.settlement_info,
            )

        except Exception as e:
            return ChannelOperationResult(
                success=False, message=f'Failed to close channel: {e!s}'
            )

    def dispute_channel(
        self,
        channel_id: str,
        disputing_participant: str,
        reason: DisputeReason,
        evidence: list[dict[str, Any]],
    ) -> ChannelOperationResult:
        """Raise a dispute for a channel."""
        channel = self.active_channels.get(channel_id)
        if not channel:
            return ChannelOperationResult(
                success=False, message=f'Channel {channel_id} not found'
            )

        # Create dispute
        dispute = ChannelDispute(
            dispute_id=f'dispute_{uuid.uuid4()}',
            channel_id=channel_id,
            disputing_participant=disputing_participant,
            dispute_reason=reason,
            contested_state=channel.model_dump(),
            evidence=evidence,
            resolution_deadline=(
                datetime.now(UTC)
                + timedelta(seconds=channel.policy.dispute_timeout_seconds)
            ).isoformat(),
        )

        # Update channel state
        channel.state = ChannelState.DISPUTED
        channel.dispute_info = dispute.model_dump()

        return ChannelOperationResult(
            success=True,
            channel_id=channel_id,
            message=f'Dispute {dispute.dispute_id} created for channel {channel_id}',
            data={'dispute': dispute.model_dump()},
        )

    def get_channel_status(self, channel_id: str) -> dict[str, Any] | None:
        """Get comprehensive status of a channel."""
        channel = self.active_channels.get(channel_id)
        if not channel:
            return None

        return {
            'channel_id': channel_id,
            'state': channel.state,
            'participants': [
                {
                    'id': p.participant_id,
                    'balance': p.current_balance.model_dump(),
                    'role': p.role,
                }
                for p in channel.participants
            ],
            'total_capacity': channel.total_capacity.model_dump(),
            'sequence_number': channel.sequence_number,
            'expires_at': channel.expires_at,
            'last_activity': channel.last_activity,
            'is_expired': channel.is_expired(),
            'dispute_info': channel.dispute_info,
            'settlement_info': channel.settlement_info,
        }

    def cleanup_expired_channels(self) -> list[str]:
        """Clean up expired channels."""
        expired_channels = []
        current_time = datetime.now(UTC)

        for channel_id, channel in list(self.active_channels.items()):
            if channel.is_expired(current_time):
                expired_channels.append(channel_id)

                # Force close expired channel
                channel.state = ChannelState.EXPIRED
                channel.settlement_info = {
                    'final_balances': {
                        p.participant_id: p.current_balance.model_dump()
                        for p in channel.participants
                    },
                    'close_reason': 'expired',
                    'closure_time': current_time.isoformat(),
                }

                self.channel_history.append(channel_id)
                del self.active_channels[channel_id]

        return expired_channels

    def get_channels_by_participant(
        self, participant_id: str
    ) -> list[dict[str, Any]]:
        """Get all channels involving a specific participant."""
        result = []
        for channel_id, channel in self.active_channels.items():
            if any(
                p.participant_id == participant_id for p in channel.participants
            ):
                result.append(self.get_channel_status(channel_id))
        return [status for status in result if status is not None]

    def _calculate_state_hash(
        self, channel_id: str, participants: list[ChannelParticipant]
    ) -> str:
        """Calculate hash of channel state."""
        state_data = f'{channel_id}'
        for participant in participants:
            state_data += f'{participant.participant_id}:{participant.current_balance.value}'

        return hashlib.sha256(state_data.encode()).hexdigest()

    def _sign_voucher(
        self,
        channel_id: str,
        from_participant: str,
        amount: PaymentCurrencyAmount,
    ) -> str:
        """Create signature for payment voucher (mock implementation)."""
        voucher_data = (
            f'{channel_id}:{from_participant}:{amount.value}:{amount.currency}'
        )
        return hashlib.sha256(voucher_data.encode()).hexdigest()

    def _validate_final_balances(
        self,
        channel: PaymentChannel,
        final_balances: dict[str, PaymentCurrencyAmount],
    ) -> bool:
        """Validate that final balances are consistent with channel state."""
        # Check that all participants are accounted for
        participant_ids = {p.participant_id for p in channel.participants}
        final_balance_ids = set(final_balances.keys())

        if participant_ids != final_balance_ids:
            return False

        # Check that total balances match channel capacity
        total_final = sum(balance.value for balance in final_balances.values())
        total_capacity = channel.total_capacity.value

        # Allow for small floating-point differences
        return abs(total_final - total_capacity) < 0.001
