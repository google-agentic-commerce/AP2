# Copyright 2026 Tenzro Network.
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

"""AP2 sample: DID-based settlement (TDIP example).

Walks an AP2 mandate chain — IntentMandate -> CartMandate ->
PaymentMandate — through four nested validation ceilings and a
Plonky3 STARK settlement commitment. The principal is a TDIP human DID
(`did:tenzro:human:alice`); the delegate is a TDIP machine DID
(`did:tenzro:machine:shopper`). The pattern is identity-system-
agnostic: any DID method with a comparable delegation primitive plugs
in by reimplementing ``tenzro_client.TenzroClient``.

See ``README.md`` in this directory for the full prose explanation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from ap2.models.mandate import (
    CartContents,
    CartMandate,
    IntentMandate,
    PaymentMandate,
    PaymentMandateContents,
)
from ap2.models.payment_request import (
    PaymentCurrencyAmount,
    PaymentDetailsInit,
    PaymentItem,
    PaymentMethodData,
    PaymentRequest,
    PaymentResponse,
)

from tenzro_client import TenzroClient, TenzroRpcError


# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------

# Payment method identifier for Tenzro micropayment channels. This is
# the AP2 ``supported_methods`` string the merchant advertises and the
# PaymentMandate carries. It maps onto Tenzro's MPP / channel layer
# (see crates/tenzro-payments and the mpp-specs draft).
TENZRO_CHANNEL_PAYMENT_METHOD = "tenzro:micropayment-channel"

# DID examples. Replace with real, registered DIDs to exercise live
# enforcement.
PRINCIPAL_DID = "did:tenzro:human:alice"
DELEGATE_DID = "did:tenzro:machine:shopper"
MERCHANT_DID = "did:tenzro:machine:bookshop"

# Currency / asset choice. AP2 uses ISO-4217 currency codes in
# PaymentCurrencyAmount; the Tenzro side encodes the asset onto the
# settlement channel separately.
CURRENCY_CODE = "USD"

# Budgets (in cents — kept as int to match AP2's PaymentItem.amount
# semantics, which require a string-decimal value at serialization
# time but flow as ints in our local arithmetic).
INTENT_MAX_CENTS = 5_000        # $50.00
DELEGATION_SCOPE_CAP_CENTS = 10_000   # $100.00 (TDIP DelegationScope ceiling)
SPENDING_POLICY_DAILY_CENTS = 5_000   # $50.00 (TDIP runtime SpendingPolicy)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def cents_to_decimal(cents: int) -> str:
    """Format integer cents as a fixed-2-decimal display string (e.g. '37.50')."""
    sign = "-" if cents < 0 else ""
    whole, frac = divmod(abs(cents), 100)
    return f"{sign}{whole}.{frac:02d}"


def cents_to_float(cents: int) -> float:
    """Convert integer cents to a float major-unit value for AP2's
    ``PaymentCurrencyAmount.value`` (which is typed as ``float``)."""
    return round(cents / 100.0, 2)


def section(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def kv(label: str, value: Any, *, width: int = 32) -> None:
    print(f"  {label.ljust(width)}  {value}")


# ----------------------------------------------------------------------
# AP2 mandate construction
# ----------------------------------------------------------------------


def build_intent_mandate() -> IntentMandate:
    """Build the principal-side IntentMandate.

    AP2's IntentMandate is identity-system-agnostic. The principal DID
    is conveyed out-of-band (in TDIP / x402 / a custom A2A extension);
    the AP2 mandate itself only carries the natural-language intent and
    the merchant / SKU constraints. The DID binding is enforced by the
    Tenzro validator at ``validateMandatePair`` time.
    """
    expiry = (datetime.now(UTC) + timedelta(hours=24)).isoformat()
    return IntentMandate(
        user_cart_confirmation_required=False,
        natural_language_description=(
            "Buy two used hardcover Rust programming books, total under "
            f"${cents_to_decimal(INTENT_MAX_CENTS)}."
        ),
        merchants=[MERCHANT_DID],
        skus=None,  # any SKU permitted
        requires_refundability=False,
        intent_expiry=expiry,
    )


def build_cart_mandate() -> CartMandate:
    """Build the merchant-signed CartMandate.

    Items are deterministic so the test can pin the cart total.
    """
    items: list[PaymentItem] = [
        PaymentItem(
            label="Programming Rust, 2nd ed. (used)",
            amount=PaymentCurrencyAmount(
                currency=CURRENCY_CODE, value=cents_to_float(2_000)
            ),
        ),
        PaymentItem(
            label="Rust for Rustaceans (used)",
            amount=PaymentCurrencyAmount(
                currency=CURRENCY_CODE, value=cents_to_float(1_750)
            ),
        ),
    ]
    total_cents = 2_000 + 1_750  # $37.50

    payment_request = PaymentRequest(
        method_data=[
            PaymentMethodData(
                supported_methods=TENZRO_CHANNEL_PAYMENT_METHOD,
                data={
                    "rail": "tenzro-micropayment-channel",
                    "asset": "USD",
                    "settlement_chain": "tenzro:testnet",
                },
            )
        ],
        details=PaymentDetailsInit(
            id=f"order-{uuid.uuid4().hex[:8]}",
            display_items=items,
            total=PaymentItem(
                label="Total",
                amount=PaymentCurrencyAmount(
                    currency=CURRENCY_CODE,
                    value=cents_to_float(total_cents),
                ),
            ),
        ),
    )

    cart_expiry = (datetime.now(UTC) + timedelta(minutes=15)).isoformat()
    contents = CartContents(
        id=f"cart-{uuid.uuid4().hex[:8]}",
        user_cart_confirmation_required=False,
        payment_request=payment_request,
        cart_expiry=cart_expiry,
        merchant_name=MERCHANT_DID,
    )
    return CartMandate(contents=contents, merchant_authorization=None)


def build_payment_mandate(cart: CartMandate) -> PaymentMandate:
    """Build the user-side PaymentMandate authorizing the cart."""
    contents = PaymentMandateContents(
        payment_mandate_id=f"pm-{uuid.uuid4().hex[:8]}",
        payment_details_id=cart.contents.payment_request.details.id,
        payment_details_total=cart.contents.payment_request.details.total,
        payment_response=PaymentResponse(
            request_id=cart.contents.payment_request.details.id,
            method_name=TENZRO_CHANNEL_PAYMENT_METHOD,
            details={
                "channel_id": f"chan-{uuid.uuid4().hex[:8]}",
                "payer_did": PRINCIPAL_DID,
                "delegate_did": DELEGATE_DID,
            },
        ),
        merchant_agent=MERCHANT_DID,
    )
    return PaymentMandate(
        payment_mandate_contents=contents,
        user_authorization=None,
    )


# ----------------------------------------------------------------------
# Tenzro VDC envelope
# ----------------------------------------------------------------------
#
# Tenzro's ``tenzro_ap2ValidateMandatePair`` RPC accepts two signed-VDC
# envelopes. For the sample we construct unsigned skeleton envelopes —
# the live RPC requires real Ed25519 signatures, but the validation
# call paths exercised here (mandate cross-checks + DelegationScope +
# SpendingPolicy) are the ones the sample is showing. A production
# integration would sign these with the principal's TDIP key and the
# agent's TDIP key respectively.


def to_tenzro_intent_vdc(
    intent: IntentMandate,
    *,
    principal_did: str,
    agent_did: str,
) -> dict[str, Any]:
    """Project AP2 IntentMandate -> Tenzro VDC envelope (unsigned)."""
    expiry_dt = datetime.fromisoformat(intent.intent_expiry)
    now = datetime.now(UTC)
    return {
        "version": "0.2",
        "kind": "intent",
        "payload": {
            "kind": "intent",
            "mandate_id": str(uuid.uuid4()),
            "principal_did": principal_did,
            "agent_did": agent_did,
            "description": intent.natural_language_description,
            "max_amount": INTENT_MAX_CENTS,  # cents
            "asset": CURRENCY_CODE,
            "allowed_merchants": list(intent.merchants or []),
            "allowed_categories": [],
            "max_uses": 1,
            "issued_at": now.isoformat(),
            "expires_at": expiry_dt.isoformat(),
            "presence": "human_not_present",
            "metadata": {},
        },
        "signer_did": principal_did,
        "signer_public_key": [],  # filled in by a production signer
        "signature": [],
        "alg": "ed25519",
    }


def to_tenzro_cart_vdc(
    cart: CartMandate,
    *,
    intent_mandate_id: str,
    agent_did: str,
    merchant_did: str,
) -> dict[str, Any]:
    """Project AP2 CartMandate -> Tenzro VDC envelope (unsigned)."""
    items = []
    for it in cart.contents.payment_request.details.display_items:
        cents = int(round(it.amount.value * 100))
        items.append(
            {
                "sku": it.label,
                "description": it.label,
                "quantity": 1,
                "unit_price": cents,
                "total": cents,
                "category": None,
            }
        )
    total_cents = int(
        round(cart.contents.payment_request.details.total.amount.value * 100)
    )
    cart_expiry = datetime.fromisoformat(cart.contents.cart_expiry)
    now = datetime.now(UTC)
    return {
        "version": "0.2",
        "kind": "cart",
        "payload": {
            "kind": "cart",
            "mandate_id": cart.contents.id,
            "intent_mandate_id": intent_mandate_id,
            "agent_did": agent_did,
            "merchant_did": merchant_did,
            "items": items,
            "total_amount": total_cents,
            "asset": CURRENCY_CODE,
            "chain": "tenzro:testnet",
            "committed_at": now.isoformat(),
            "expires_at": cart_expiry.isoformat(),
            "metadata": {},
        },
        "signer_did": agent_did,
        "signer_public_key": [],
        "signature": [],
        "alg": "ed25519",
    }


# ----------------------------------------------------------------------
# Local validation (for environments without live Tenzro access)
# ----------------------------------------------------------------------


def local_validate_mandates(
    intent_vdc: dict[str, Any],
    cart_vdc: dict[str, Any],
    *,
    delegation_cap_cents: int,
    daily_remaining_cents: int,
) -> tuple[bool, list[tuple[str, bool, str]]]:
    """Run the four ceilings locally so the sample produces useful
    output even when ``tenzro_ap2ValidateMandatePair`` is unreachable.

    Returns ``(overall_ok, [(label, ok, detail), ...])``.
    """
    ip = intent_vdc["payload"]
    cp = cart_vdc["payload"]
    results: list[tuple[str, bool, str]] = []

    # 1. AP2 IntentMandate constraints
    intent_ok = (
        cp["total_amount"] <= ip["max_amount"]
        and ip["agent_did"] == cp["agent_did"]
        and (not ip["allowed_merchants"] or cp["merchant_did"] in ip["allowed_merchants"])
        and datetime.fromisoformat(ip["expires_at"]) > datetime.now(UTC)
    )
    results.append(
        (
            "AP2 IntentMandate constraints",
            intent_ok,
            f"max_amount={ip['max_amount']} cents, cart total={cp['total_amount']} cents",
        )
    )

    # 2. AP2 CartMandate consistency
    recomputed = sum(item["total"] for item in cp["items"])
    cart_ok = (
        recomputed == cp["total_amount"]
        and datetime.fromisoformat(cp["expires_at"]) > datetime.now(UTC)
    )
    results.append(
        (
            "AP2 CartMandate consistency",
            cart_ok,
            f"recomputed={recomputed} cents, claimed={cp['total_amount']} cents",
        )
    )

    # 3. TDIP DelegationScope (protocol-level ceiling)
    deleg_ok = cp["total_amount"] <= delegation_cap_cents
    results.append(
        (
            "TDIP DelegationScope",
            deleg_ok,
            f"{cp['total_amount']} cents <= {delegation_cap_cents} cents scope cap",
        )
    )

    # 4. TDIP runtime SpendingPolicy (execution-level ceiling)
    policy_ok = cp["total_amount"] <= daily_remaining_cents
    results.append(
        (
            "TDIP SpendingPolicy",
            policy_ok,
            f"{cp['total_amount']} cents <= {daily_remaining_cents} cents daily window",
        )
    )

    return all(ok for _, ok, _ in results), results


# ----------------------------------------------------------------------
# Settlement (Plonky3 STARK commitment)
# ----------------------------------------------------------------------


def compute_zk_commitment(
    *, circuit_id: str, proof_hex: str, public_inputs_hex: list[str]
) -> str:
    """Compute the same SHA-256 commitment the on-chain ZK_VERIFY precompile expects.

    Mirrors ``tenzro_zk::compute_zk_commitment`` in the workspace:
        SHA-256(circuit_id || proof_bytes || sum_i (len_le(pi_i) || pi_i))
    Lengths are 4-byte little-endian. Proof and public inputs are hex
    strings prefixed with ``0x``.
    """

    def unhex(s: str) -> bytes:
        return bytes.fromhex(s.removeprefix("0x"))

    h = hashlib.sha256()
    h.update(circuit_id.encode("utf-8"))
    h.update(unhex(proof_hex))
    for pi in public_inputs_hex:
        b = unhex(pi)
        h.update(len(b).to_bytes(4, "little"))
        h.update(b)
    return "0x" + h.hexdigest()


def settle(
    client: TenzroClient,
    *,
    payment_mandate: PaymentMandate,
    cart_total_cents: int,
) -> dict[str, Any]:
    """Generate a Plonky3 STARK + commitment, then return a simulated channel receipt."""
    # Witness fields — small values so the field-element conversion at
    # the RPC boundary is unambiguous. `service_proof` is a hash of the
    # PaymentMandate that pins the commitment to *this* settlement.
    service_proof_hash = hashlib.sha256(
        payment_mandate.model_dump_json().encode("utf-8")
    ).digest()
    service_proof_int = int.from_bytes(service_proof_hash[:4], "little")

    proof_env = client.create_zk_proof_settlement(
        payer_balance=10_000,          # cents — payer has $100 in channel
        service_proof=service_proof_int,
        nonce=2,
        prev_nonce=1,
        amount=cart_total_cents,
    )
    commitment = compute_zk_commitment(
        circuit_id=proof_env["circuit_id"],
        proof_hex=proof_env["proof"],
        public_inputs_hex=proof_env["public_inputs"],
    )

    channel_id = payment_mandate.payment_mandate_contents.payment_response.details[
        "channel_id"
    ]
    receipt = client.settle_channel_simulated(
        channel_id=channel_id,
        payment_amount=cart_total_cents,
        proof_commitment_hex=commitment,
    )
    return {
        "proof_envelope": proof_env,
        "commitment": commitment,
        "receipt": receipt,
    }


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------


def run(client: TenzroClient, *, offline: bool) -> int:
    print("=== AP2 sample: DID-based settlement (TDIP example) ===")
    print(f"RPC: {client.rpc_url}")

    # 1. Resolve principal + delegate DIDs (live RPC, read-only)
    section("[1/2] Resolving DIDs")
    if not offline:
        try:
            principal = client.resolve_did(PRINCIPAL_DID)
            kv("Principal", f"{PRINCIPAL_DID} ({principal.identity_type})")
            kv("  kyc_tier", principal.kyc_tier or "Unverified")
            delegate = client.resolve_did(DELEGATE_DID)
            kv("Delegate ", f"{DELEGATE_DID} ({delegate.identity_type})")
            kv("  controller_did", delegate.controller_did or "(autonomous)")
        except (TenzroRpcError, Exception) as e:  # noqa: BLE001
            print(
                f"  (skipping live resolve: {type(e).__name__}: {e}) — proceeding "
                "with literal DIDs; this is fine when the testnet doesn't "
                "have these example identities registered."
            )
    else:
        print("  (offline: literal DIDs only)")

    # 2. Build mandate chain
    section("[2/2] AP2 mandate chain")
    intent = build_intent_mandate()
    cart = build_cart_mandate()
    payment = build_payment_mandate(cart)

    intent_vdc = to_tenzro_intent_vdc(
        intent, principal_did=PRINCIPAL_DID, agent_did=DELEGATE_DID
    )
    cart_vdc = to_tenzro_cart_vdc(
        cart,
        intent_mandate_id=intent_vdc["payload"]["mandate_id"],
        agent_did=DELEGATE_DID,
        merchant_did=MERCHANT_DID,
    )

    cart_total_cents = cart_vdc["payload"]["total_amount"]
    kv("IntentMandate.max_amount", f"${cents_to_decimal(INTENT_MAX_CENTS)} {CURRENCY_CODE}")
    kv("CartMandate.total_amount", f"${cents_to_decimal(cart_total_cents)} {CURRENCY_CODE}")
    kv("PaymentMandate.method", TENZRO_CHANNEL_PAYMENT_METHOD)

    # Validation — four ceilings
    section("Validating against four nested ceilings")
    overall, results = local_validate_mandates(
        intent_vdc,
        cart_vdc,
        delegation_cap_cents=DELEGATION_SCOPE_CAP_CENTS,
        daily_remaining_cents=SPENDING_POLICY_DAILY_CENTS,
    )
    for label, ok, detail in results:
        kv(label, ("OK   " if ok else "FAIL ") + detail)
    if not overall:
        print("\nLocal validation failed — aborting before contacting the RPC.")
        return 2

    # Cross-check via the live Tenzro RPC (covers the same checks plus
    # signature verification once the VDCs are signed for real).
    if not offline:
        try:
            rpc_outcome = client.validate_mandate_pair(
                intent_vdc, cart_vdc, enforce_delegation=True
            )
            kv("Tenzro RPC validateMandatePair", json.dumps(rpc_outcome))
        except TenzroRpcError as e:
            print(
                f"  (RPC validateMandatePair returned error {e.code}: {e.message}; "
                "expected when the example DIDs / signatures are unregistered — "
                "the local checks above already cover the four ceilings)"
            )
    else:
        print("  (offline: skipping RPC cross-check)")

    # Settlement — Plonky3 STARK commitment
    section("Settling via Plonky3 commitment (settlement AIR)")
    if offline:
        kv("note", "offline mode — skipping create_zk_proof RPC")
        return 0
    try:
        outcome = settle(client, payment_mandate=payment, cart_total_cents=cart_total_cents)
        env = outcome["proof_envelope"]
        kv("circuit_id", env["circuit_id"])
        kv("proof_size_bytes", env.get("proof_size_bytes"))
        kv("commitment (sha256)", outcome["commitment"])
        kv("receipt.channel_id", outcome["receipt"]["channel_id"])
        kv(
            "receipt.payment_amount",
            f"${cents_to_decimal(outcome['receipt']['payment_amount'])} {CURRENCY_CODE}",
        )
        kv("receipt.status", outcome["receipt"]["status"])
    except TenzroRpcError as e:
        print(f"  (settlement RPC error {e.code}: {e.message})")
        return 3

    print("\n=== Done. Mandate chain validated and settlement-ready. ===")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rpc-url",
        default=os.environ.get("TENZRO_RPC_URL"),
        help="Tenzro JSON-RPC URL (default: $TENZRO_RPC_URL or https://rpc.tenzro.network)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip all live RPC calls; run local checks only.",
    )
    args = parser.parse_args(argv)

    client = TenzroClient(rpc_url=args.rpc_url)
    return run(client, offline=args.offline)


if __name__ == "__main__":
    sys.exit(main())
