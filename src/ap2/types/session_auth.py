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

"""Session-based authorization for autonomous agent transactions."""

from datetime import datetime
from datetime import timezone
from enum import Enum
from typing import Any, Optional

from ap2.types.payment_request import PaymentCurrencyAmount
from pydantic import BaseModel
from pydantic import Field


class SessionAuthType(str, Enum):
    """Types of session authorization methods."""

    EPHEMERAL_KEY = "ephemeral_key"
    DELEGATED_SIGNATURE = "delegated_signature"
    SMART_CONTRACT = "smart_contract"
    HARDWARE_ATTESTATION = "hardware_attestation"


class SessionStatus(str, Enum):
    """Status of a session authorization."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"


class SessionIntent(BaseModel):
    """Specific intent authorized within a session."""

    intent_id: str = Field(..., description="Unique identifier for this intent.")
    action: str = Field(
        ..., description="Type of action authorized (e.g., 'purchase', 'subscription')."
    )
    max_amount: Optional[PaymentCurrencyAmount] = Field(
        None, description="Maximum amount authorized for this intent."
    )
    valid_until: str = Field(
        ..., description="When this intent expires, in ISO 8601 format."
    )
    merchant_restrictions: Optional[list[str]] = Field(
        None, description="List of allowed merchant identifiers."
    )
    category_restrictions: Optional[list[str]] = Field(
        None, description="List of allowed product categories."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional intent-specific metadata."
    )


class SessionCredential(BaseModel):
    """Cryptographic credential for a session."""

    credential_id: str = Field(
        ..., description="Unique identifier for this credential."
    )
    public_key: str = Field(
        ..., description="Base64-encoded public key for session verification."
    )
    signature_algorithm: str = Field(
        default="ES256", description="Cryptographic signature algorithm used."
    )
    key_derivation_method: str = Field(
        default="random", description="How the session key was derived."
    )
    attestation: Optional[str] = Field(
        None, description="Hardware or software attestation for key generation."
    )
    created_at: str = Field(
        description="When the credential was created, in ISO 8601 format.",
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


class SessionAuthorization(BaseModel):
    """Authorization framework for autonomous agent sessions.

    This enables time-bounded, scope-limited delegation of user authority
    to AI agents through cryptographic session credentials.
    """

    session_id: str = Field(
        ..., description="Unique identifier for this session."
    )
    agent_did: str = Field(
        ..., description="Decentralized identifier of the authorized agent."
    )
    user_wallet_address: str = Field(
        ..., description="Wallet address of the authorizing user."
    )
    auth_type: SessionAuthType = Field(
        ..., description="Type of session authorization mechanism."
    )
    credential: SessionCredential = Field(
        ..., description="Cryptographic credential for session verification."
    )
    intents: list[SessionIntent] = Field(
        ..., description="List of specific intents authorized in this session."
    )
    session_expiry: str = Field(
        ..., description="When the entire session expires, in ISO 8601 format."
    )
    status: SessionStatus = Field(
        default=SessionStatus.ACTIVE, description="Current status of the session."
    )
    revocation_registry_uri: Optional[str] = Field(
        None, description="URI for checking session revocation status."
    )
    delegation_proof: Optional[str] = Field(
        None,
        description="Cryptographic proof of delegation from user to agent.",
    )
    interaction_pattern: str = Field(
        default="server-initiated",
        description="Expected interaction pattern for this session.",
        pattern="^(server-initiated|client-initiated)$",
    )
    nonce: int = Field(
        default=0, description="Replay protection nonce for session operations."
    )
    created_at: str = Field(
        description="When the session was created, in ISO 8601 format.",
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    last_used: Optional[str] = Field(
        None, description="When the session was last used, in ISO 8601 format."
    )

    def is_valid(self, current_time: Optional[datetime] = None) -> bool:
        """Check if the session is currently valid.

        Args:
            current_time: Time to check validity against. If None, uses current time.

        Returns:
            True if session is valid, False otherwise
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        # Check status
        if self.status != SessionStatus.ACTIVE:
            return False

        # Check expiry
        expiry_time = datetime.fromisoformat(self.session_expiry.replace("Z", "+00:00"))
        if current_time > expiry_time:
            return False

        return True

    def has_intent_for_action(self, action: str, amount: Optional[PaymentCurrencyAmount] = None) -> bool:
        """Check if session has valid intent for a specific action.

        Args:
            action: The action to check authorization for
            amount: Optional amount to check against intent limits

        Returns:
            True if session authorizes this action, False otherwise
        """
        if not self.is_valid():
            return False

        current_time = datetime.now(timezone.utc)

        for intent in self.intents:
            # Check if intent covers this action
            if intent.action != action:
                continue

            # Check if intent is still valid
            intent_expiry = datetime.fromisoformat(intent.valid_until.replace("Z", "+00:00"))
            if current_time > intent_expiry:
                continue

            # Check amount limits if specified
            if amount and intent.max_amount:
                if amount.currency != intent.max_amount.currency:
                    continue  # Currency mismatch
                if amount.value > intent.max_amount.value:
                    continue  # Amount exceeds limit

            return True

        return False

    def get_valid_intents(self, current_time: Optional[datetime] = None) -> list[SessionIntent]:
        """Get all currently valid intents for this session.

        Args:
            current_time: Time to check validity against. If None, uses current time.

        Returns:
            List of valid session intents
        """
        if not self.is_valid(current_time):
            return []

        if current_time is None:
            current_time = datetime.now(timezone.utc)

        valid_intents = []
        for intent in self.intents:
            intent_expiry = datetime.fromisoformat(intent.valid_until.replace("Z", "+00:00"))
            if current_time <= intent_expiry:
                valid_intents.append(intent)

        return valid_intents

    def increment_nonce(self) -> int:
        """Increment the session nonce for replay protection.

        Returns:
            The new nonce value
        """
        self.nonce += 1
        self.last_used = datetime.now(timezone.utc).isoformat()
        return self.nonce

    def revoke(self, reason: str = "manual_revocation") -> None:
        """Revoke this session authorization.

        Args:
            reason: Reason for revocation
        """
        self.status = SessionStatus.REVOKED
        self.last_used = datetime.now(timezone.utc).isoformat()
        # In a real implementation, this would also update the revocation registry


class SessionAuthorizationRequest(BaseModel):
    """Request to create a new session authorization."""

    user_wallet_address: str = Field(
        ..., description="Wallet address of the user granting authorization."
    )
    agent_did: str = Field(
        ..., description="DID of the agent requesting authorization."
    )
    requested_intents: list[SessionIntent] = Field(
        ..., description="List of intents the agent is requesting."
    )
    session_duration_hours: int = Field(
        default=24, description="Requested session duration in hours.", ge=1, le=168
    )
    auth_type: SessionAuthType = Field(
        default=SessionAuthType.EPHEMERAL_KEY,
        description="Preferred authorization method.",
    )
    interaction_pattern: str = Field(
        default="server-initiated",
        description="Expected interaction pattern.",
        pattern="^(server-initiated|client-initiated)$",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional request metadata."
    )


class SessionRevocationList(BaseModel):
    """List of revoked session identifiers."""

    revoked_sessions: list[str] = Field(
        default_factory=list, description="List of revoked session IDs."
    )
    issuer: str = Field(..., description="Entity that issued this revocation list.")
    issued_at: str = Field(
        description="When this list was issued, in ISO 8601 format.",
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    next_update: str = Field(
        ..., description="When the next update is expected, in ISO 8601 format."
    )
    sequence_number: int = Field(
        default=1, description="Sequence number for this revocation list."
    )

    def is_revoked(self, session_id: str) -> bool:
        """Check if a session ID is in the revocation list.

        Args:
            session_id: Session identifier to check

        Returns:
            True if session is revoked, False otherwise
        """
        return session_id in self.revoked_sessions

    def add_revocation(self, session_id: str) -> None:
        """Add a session to the revocation list.

        Args:
            session_id: Session identifier to revoke
        """
        if session_id not in self.revoked_sessions:
            self.revoked_sessions.append(session_id)
            self.issued_at = datetime.now(timezone.utc).isoformat()
            self.sequence_number += 1