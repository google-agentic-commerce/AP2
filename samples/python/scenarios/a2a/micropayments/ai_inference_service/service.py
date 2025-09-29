#!/usr/bin/env python3

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

"""AI Inference Service with micropayment channels.

This sample demonstrates how to build an AI service that accepts micropayments
for inference requests, supporting pay-per-token and streaming payment models.

Example usage:
    python service.py --port 8080 --model "gpt-3.5-turbo" --rate-per-token 0.0001
"""

import argparse
import asyncio
import uuid

from typing import Any

from ap2.channels.channel_manager import ChannelManager, ChannelOperationResult
from ap2.types.payment_channels import (
    ChannelOpenRequest,
    ChannelParticipant,
    ChannelPolicy,
)
from ap2.types.payment_request import CryptoPaymentAmount
from ap2.types.streaming_payments import (
    PaymentRate,
    PaymentRateType,
    StreamStatus,
    StreamingPaymentManager,
    StreamingPaymentPolicy,
    StreamingPaymentSession,
)


class AIInferenceService:
    """AI inference service with micropayment channel support."""

    def __init__(
        self,
        service_did: str,
        model_name: str,
        rate_per_token: float,
        currency: str = 'USDC',
        blockchain_network: str = 'kite',
    ):
        """Initialize the AI inference service.

        Args:
            service_did: DID of the service
            model_name: Name of the AI model being served
            rate_per_token: Cost per token in the specified currency
            currency: Payment currency (default: USDC)
            blockchain_network: Blockchain network (default: kite)
        """
        self.service_did = service_did
        self.model_name = model_name
        self.currency = currency
        self.blockchain_network = blockchain_network

        # Initialize payment components
        self.channel_manager = ChannelManager(
            manager_id=f'channel_mgr_{service_did}', agent_did=service_did
        )

        self.streaming_manager = StreamingPaymentManager(
            manager_id=f'stream_mgr_{service_did}', agent_did=service_did
        )

        # Service configuration
        self.payment_rate = PaymentRate(
            rate_type=PaymentRateType.PER_TOKEN,
            rate_amount=CryptoPaymentAmount(
                currency=currency,
                value=rate_per_token,
                blockchain_network=blockchain_network,
                decimal_places=6,  # USDC has 6 decimal places
            ),
            minimum_charge=CryptoPaymentAmount(
                currency=currency,
                value=0.001,  # Minimum charge of 0.001 USDC
                blockchain_network=blockchain_network,
                decimal_places=6,
            ),
            billing_frequency_seconds=1,
            unit_description='AI model tokens',
        )

        self.service_policy = StreamingPaymentPolicy(
            max_stream_duration_seconds=3600,  # 1 hour max
            checkpoint_frequency_seconds=30,  # Checkpoint every 30 seconds
            auto_pause_threshold=CryptoPaymentAmount(
                currency=currency,
                value=10.0,  # Auto-pause at $10
                blockchain_network=blockchain_network,
                decimal_places=6,
            ),
            max_cumulative_amount=CryptoPaymentAmount(
                currency=currency,
                value=100.0,  # Max $100 per stream
                blockchain_network=blockchain_network,
                decimal_places=6,
            ),
            rate_adjustment_allowed=False,
        )

        # Service statistics
        self.total_requests = 0
        self.total_tokens_processed = 0
        self.total_revenue = 0.0
        self.active_clients = {}

    async def handle_channel_open_request(
        self, client_did: str, client_wallet: str, initial_deposit: float
    ) -> ChannelOperationResult:
        """Handle a request to open a payment channel."""
        print(f'📨 Channel open request from {client_did}')

        # Create participant for client
        client_participant = ChannelParticipant(
            participant_id=client_did,
            agent_did=client_did,
            wallet_address=client_wallet,
            role='payer',
            public_key=f'pubkey_{client_did}',  # Mock public key
            initial_balance=CryptoPaymentAmount(
                currency=self.currency,
                value=initial_deposit,
                blockchain_network=self.blockchain_network,
                decimal_places=6,
            ),
            current_balance=CryptoPaymentAmount(
                currency=self.currency,
                value=initial_deposit,
                blockchain_network=self.blockchain_network,
                decimal_places=6,
            ),
        )

        # Create participant for service
        service_participant = ChannelParticipant(
            participant_id=self.service_did,
            agent_did=self.service_did,
            wallet_address=f'0x{uuid.uuid4().hex[:40]}',  # Mock service wallet
            role='payee',
            public_key=f'pubkey_{self.service_did}',  # Mock public key
            initial_balance=CryptoPaymentAmount(
                currency=self.currency,
                value=0.0,
                blockchain_network=self.blockchain_network,
                decimal_places=6,
            ),
            current_balance=CryptoPaymentAmount(
                currency=self.currency,
                value=0.0,
                blockchain_network=self.blockchain_network,
                decimal_places=6,
            ),
        )

        # Create channel policy
        policy = ChannelPolicy(
            max_transaction_amount=CryptoPaymentAmount(
                currency=self.currency,
                value=1.0,  # Max $1 per transaction
                blockchain_network=self.blockchain_network,
                decimal_places=6,
            ),
            min_transaction_amount=CryptoPaymentAmount(
                currency=self.currency,
                value=0.0001,  # Min $0.0001 per transaction
                blockchain_network=self.blockchain_network,
                decimal_places=6,
            ),
            settlement_threshold=CryptoPaymentAmount(
                currency=self.currency,
                value=5.0,  # Auto-settle at $5
                blockchain_network=self.blockchain_network,
                decimal_places=6,
            ),
            fee_rate=0.001,  # 0.1% fee
            auto_close_timeout=86400,  # 24 hours
        )

        # Create channel open request
        open_request = ChannelOpenRequest(
            requesting_participant=client_participant,
            target_participant=service_participant,
            proposed_policy=policy,
            duration_hours=24,  # 24 hour channel
            initial_deposit=CryptoPaymentAmount(
                currency=self.currency,
                value=initial_deposit,
                blockchain_network=self.blockchain_network,
                decimal_places=6,
            ),
            purpose=f'AI inference payments for {self.model_name}',
        )

        # Open the channel
        result = self.channel_manager.open_channel(open_request)

        if result.success:
            # Automatically activate the channel
            activation_result = self.channel_manager.activate_channel(
                result.channel_id
            )
            if activation_result.success:
                print(f'✅ Channel {result.channel_id} opened and activated')
                self.active_clients[client_did] = result.channel_id
            else:
                print(
                    f'❌ Failed to activate channel: {activation_result.message}'
                )

        return result

    async def start_streaming_session(
        self, client_did: str, service_description: str = 'AI inference tokens'
    ) -> StreamingPaymentSession | None:
        """Start a streaming payment session for a client."""
        channel_id = self.active_clients.get(client_did)
        if not channel_id:
            print(f'❌ No active channel found for client {client_did}')
            return None

        # Create streaming session
        stream = self.streaming_manager.create_stream(
            channel_id=channel_id,
            payer_id=client_did,
            payee_id=self.service_did,
            service_description=service_description,
            rate=self.payment_rate,
            policy=self.service_policy,
        )

        stream.status = StreamStatus.ACTIVE
        print(
            f'🌊 Started streaming session {stream.stream_id} for {client_did}'
        )
        return stream

    async def process_inference_request(
        self, client_did: str, prompt: str, max_tokens: int = 100
    ) -> dict[str, Any]:
        """Process an AI inference request with micropayment."""
        print(f'🧠 Processing inference request from {client_did}')
        print(f'   Prompt: {prompt[:50]}{"..." if len(prompt) > 50 else ""}')
        print(f'   Max tokens: {max_tokens}')

        # Get or create streaming session
        active_streams = self.streaming_manager.get_streams_by_channel(
            self.active_clients.get(client_did, '')
        )

        stream = None
        if active_streams:
            stream = active_streams[0]  # Use existing stream
        else:
            stream = await self.start_streaming_session(client_did)

        if not stream:
            return {
                'error': 'Failed to establish payment stream',
                'status': 'payment_required',
            }

        # Simulate AI inference (mock implementation)
        generated_text, actual_tokens = self._mock_ai_inference(
            prompt, max_tokens
        )

        # Calculate payment for actual tokens used
        payment_amount = self.payment_rate.rate_amount.value * actual_tokens

        # Check if payment can be processed
        channel = self.channel_manager.active_channels.get(stream.channel_id)
        if not channel:
            return {
                'error': 'Payment channel not found',
                'status': 'payment_error',
            }

        can_pay, reason = channel.can_process_payment(
            client_did,
            self.service_did,
            CryptoPaymentAmount(
                currency=self.currency,
                value=payment_amount,
                blockchain_network=self.blockchain_network,
                decimal_places=6,
            ),
        )

        if not can_pay:
            stream.pause_stream(f'Payment failed: {reason}')
            return {
                'error': f'Payment failed: {reason}',
                'status': 'insufficient_funds',
                'required_amount': payment_amount,
                'currency': self.currency,
            }

        # Process payment through streaming voucher
        try:
            voucher = stream.add_voucher(
                units_consumed=actual_tokens,
                metadata={
                    'prompt_length': len(prompt),
                    'response_length': len(generated_text),
                    'model': self.model_name,
                },
            )

            # Process payment through channel
            payment_result = self.channel_manager.process_payment(
                channel_id=stream.channel_id,
                from_participant=client_did,
                to_participant=self.service_did,
                amount=voucher.increment_amount,
                metadata={
                    'stream_id': stream.stream_id,
                    'voucher_id': voucher.voucher_id,
                    'service_type': 'ai_inference',
                },
            )

            if not payment_result.success:
                stream.pause_stream(
                    f'Payment processing failed: {payment_result.message}'
                )
                return {
                    'error': f'Payment processing failed: {payment_result.message}',
                    'status': 'payment_error',
                }

            # Update service statistics
            self.total_requests += 1
            self.total_tokens_processed += actual_tokens
            self.total_revenue += payment_amount

            print(
                f'💰 Payment processed: {payment_amount} {self.currency} for {actual_tokens} tokens'
            )

            return {
                'status': 'success',
                'response': generated_text,
                'tokens_used': actual_tokens,
                'cost': payment_amount,
                'currency': self.currency,
                'voucher_id': voucher.voucher_id,
                'stream_id': stream.stream_id,
            }

        except Exception as e:
            stream.pause_stream(f'Processing error: {e!s}')
            return {
                'error': f'Processing error: {e!s}',
                'status': 'service_error',
            }

    def _mock_ai_inference(
        self, prompt: str, max_tokens: int
    ) -> tuple[str, int]:
        """Mock AI inference that generates a response and counts tokens."""
        # Simulate token processing (1 token ≈ 4 characters)
        prompt_tokens = len(prompt) // 4

        # Generate mock response
        responses = [
            "I understand your request. Here's a helpful response based on the information provided.",
            "Thank you for your query. I'll analyze this and provide you with a comprehensive answer.",
            'Based on your input, I can suggest several approaches to address this topic effectively.',
            'This is an interesting question that requires careful consideration of multiple factors.',
            'I appreciate your question. Let me break this down into manageable components for you.',
        ]

        import random

        response = random.choice(responses)

        # Limit response to max_tokens (approximately)
        max_response_chars = max_tokens * 4
        if len(response) > max_response_chars:
            response = response[:max_response_chars] + '...'

        response_tokens = len(response) // 4
        total_tokens = prompt_tokens + response_tokens

        return response, total_tokens

    def get_service_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        active_channels = len(self.channel_manager.active_channels)
        active_streams = len(self.streaming_manager.active_streams)

        return {
            'service_did': self.service_did,
            'model_name': self.model_name,
            'total_requests': self.total_requests,
            'total_tokens_processed': self.total_tokens_processed,
            'total_revenue': self.total_revenue,
            'currency': self.currency,
            'rate_per_token': self.payment_rate.rate_amount.value,
            'active_channels': active_channels,
            'active_streams': active_streams,
            'active_clients': list(self.active_clients.keys()),
        }

    async def cleanup_expired_resources(self):
        """Clean up expired channels and streams."""
        # Clean up expired channels
        expired_channels = self.channel_manager.cleanup_expired_channels()
        if expired_channels:
            print(f'🧹 Cleaned up {len(expired_channels)} expired channels')

        # Clean up expired streams
        expired_streams = self.streaming_manager.cleanup_expired_streams()
        if expired_streams:
            print(f'🧹 Cleaned up {len(expired_streams)} expired streams')

        # Remove inactive clients
        inactive_clients = []
        for client_did, channel_id in self.active_clients.items():
            if channel_id not in self.channel_manager.active_channels:
                inactive_clients.append(client_did)

        for client_did in inactive_clients:
            del self.active_clients[client_did]


async def main():
    """Main function demonstrating the AI inference service."""
    parser = argparse.ArgumentParser(
        description='AI Inference Service with Micropayments'
    )
    parser.add_argument(
        '--model', default='gpt-3.5-turbo', help='AI model name'
    )
    parser.add_argument(
        '--rate-per-token', type=float, default=0.0001, help='Rate per token'
    )
    parser.add_argument('--currency', default='USDC', help='Payment currency')
    parser.add_argument('--network', default='kite', help='Blockchain network')

    args = parser.parse_args()

    # Initialize service
    service_did = f'did:kite:1:ai_service_{uuid.uuid4().hex[:8]}'
    service = AIInferenceService(
        service_did=service_did,
        model_name=args.model,
        rate_per_token=args.rate_per_token,
        currency=args.currency,
        blockchain_network=args.network,
    )

    print('🤖 AI Inference Service with Micropayments')
    print('=' * 50)
    print(f'Service DID: {service_did}')
    print(f'Model: {args.model}')
    print(f'Rate: {args.rate_per_token} {args.currency} per token')
    print(f'Network: {args.network}')
    print()

    # Simulate client interactions
    clients = [
        {
            'did': f'did:kite:1:client_alice_{uuid.uuid4().hex[:8]}',
            'wallet': f'0x{uuid.uuid4().hex[:40]}',
            'deposit': 5.0,
        },
        {
            'did': f'did:kite:1:client_bob_{uuid.uuid4().hex[:8]}',
            'wallet': f'0x{uuid.uuid4().hex[:40]}',
            'deposit': 10.0,
        },
    ]

    # Setup channels for clients
    for client in clients:
        print(f'🔗 Setting up channel for {client["did"][:20]}...')
        result = await service.handle_channel_open_request(
            client['did'], client['wallet'], client['deposit']
        )

        if result.success:
            print(f'✅ Channel opened: {result.channel_id}')
        else:
            print(f'❌ Failed to open channel: {result.message}')

    print()

    # Simulate inference requests
    inference_requests = [
        {
            'client': clients[0]['did'],
            'prompt': 'What are the benefits of using micropayment channels for AI services?',
            'max_tokens': 150,
        },
        {
            'client': clients[1]['did'],
            'prompt': 'Explain how streaming payments work in blockchain applications',
            'max_tokens': 200,
        },
        {
            'client': clients[0]['did'],
            'prompt': 'How do agent-to-agent payments differ from traditional payment systems?',
            'max_tokens': 100,
        },
    ]

    for i, request in enumerate(inference_requests, 1):
        print(f'🧠 Processing request {i}/3...')
        result = await service.process_inference_request(
            request['client'], request['prompt'], request['max_tokens']
        )

        if result.get('status') == 'success':
            print(
                f'✅ Response: {result["response"][:80]}{"..." if len(result["response"]) > 80 else ""}'
            )
            print(
                f'   Cost: {result["cost"]} {result["currency"]} for {result["tokens_used"]} tokens'
            )
        else:
            print(f'❌ Error: {result.get("error", "Unknown error")}')

        print()

        # Small delay between requests
        await asyncio.sleep(1)

    # Show final statistics
    stats = service.get_service_stats()
    print('📊 Final Service Statistics:')
    print(f'   Total requests: {stats["total_requests"]}')
    print(f'   Total tokens: {stats["total_tokens_processed"]}')
    print(f'   Total revenue: {stats["total_revenue"]} {stats["currency"]}')
    print(f'   Active channels: {stats["active_channels"]}')
    print(f'   Active streams: {stats["active_streams"]}')

    # Cleanup
    await service.cleanup_expired_resources()


if __name__ == '__main__':
    asyncio.run(main())
