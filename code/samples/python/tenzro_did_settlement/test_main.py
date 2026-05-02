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

"""End-to-end test for the AP2 DID-based settlement sample.

Runs the full ``main.run`` flow against a stub Tenzro JSON-RPC backend
mocked with ``responses``. This avoids any dependency on a live testnet
during CI.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest
import responses
from responses import matchers

import main as sample_main
from main import (
    DELEGATE_DID,
    PRINCIPAL_DID,
    build_cart_mandate,
    build_intent_mandate,
    build_payment_mandate,
    cents_to_float,
    compute_zk_commitment,
    local_validate_mandates,
    to_tenzro_cart_vdc,
    to_tenzro_intent_vdc,
)
from tenzro_client import TenzroClient

STUB_RPC = "https://rpc.stub.tenzro.test"


# ----------------------------------------------------------------------
# Stub RPC fixtures
# ----------------------------------------------------------------------


def _rpc_response(rpc_id: int, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rpc_id, "result": result}


def _stub_resolve_human(rsps: responses.RequestsMock) -> None:
    rsps.add(
        responses.POST,
        STUB_RPC,
        match=[
            matchers.json_params_matcher(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tenzro_resolveIdentity",
                    "params": [{"did": PRINCIPAL_DID}],
                }
            )
        ],
        json=_rpc_response(
            1,
            {
                "identity_type": "Human",
                "kyc_tier": "Basic",
                "controller_did": None,
            },
        ),
        status=200,
    )


def _stub_resolve_machine(rsps: responses.RequestsMock) -> None:
    rsps.add(
        responses.POST,
        STUB_RPC,
        match=[
            matchers.json_params_matcher(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tenzro_resolveIdentity",
                    "params": [{"did": DELEGATE_DID}],
                }
            )
        ],
        json=_rpc_response(
            2,
            {
                "identity_type": "Machine",
                "kyc_tier": None,
                "controller_did": PRINCIPAL_DID,
            },
        ),
        status=200,
    )


def _stub_validate_mandate_pair(rsps: responses.RequestsMock) -> None:
    """Match any ``tenzro_ap2ValidateMandatePair`` POST and return ``valid: true``.

    We don't pin the exact body because the mandate IDs and timestamps
    are non-deterministic across test runs.
    """

    def _matcher(req: Any) -> tuple[bool, str]:
        try:
            body = json.loads(req.body)
        except Exception as e:  # noqa: BLE001
            return False, f"non-json body: {e}"
        ok = body.get("method") == "tenzro_ap2ValidateMandatePair"
        return ok, "method ok" if ok else f"method={body.get('method')}"

    rsps.add(
        responses.POST,
        STUB_RPC,
        match=[_matcher],
        json={
            "jsonrpc": "2.0",
            "id": 0,  # responses does not let us know the id ahead of time
            "result": {
                "valid": True,
                "delegation_enforced": True,
                "principal_did": PRINCIPAL_DID,
                "agent_did": DELEGATE_DID,
            },
        },
        status=200,
    )


def _stub_create_zk_proof(rsps: responses.RequestsMock) -> None:
    def _matcher(req: Any) -> tuple[bool, str]:
        try:
            body = json.loads(req.body)
        except Exception as e:  # noqa: BLE001
            return False, f"non-json body: {e}"
        if body.get("method") != "tenzro_createZkProof":
            return False, f"method={body.get('method')}"
        params = body.get("params", [{}])[0]
        return (
            params.get("circuit_id") == "settlement",
            f"circuit_id={params.get('circuit_id')}",
        )

    rsps.add(
        responses.POST,
        STUB_RPC,
        match=[_matcher],
        json={
            "jsonrpc": "2.0",
            "id": 0,
            "result": {
                "circuit_id": "settlement",
                "proof": "0xdeadbeef",
                "public_inputs": ["0xcafebabe", "0xfeedface"],
                "proof_size_bytes": 4,
                "created_at": "2026-05-02T00:00:00Z",
            },
        },
        status=200,
    )


# ----------------------------------------------------------------------
# Unit tests for the building blocks
# ----------------------------------------------------------------------


def test_intent_and_cart_build_and_round_trip() -> None:
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
        merchant_did="did:tenzro:machine:bookshop",
    )

    # AP2 SDK objects round-tripped via Pydantic
    assert intent.merchants == ["did:tenzro:machine:bookshop"]
    assert len(cart.contents.payment_request.details.display_items) == 2
    assert cart.contents.payment_request.details.total.amount.value == cents_to_float(
        3_750
    )
    assert (
        payment.payment_mandate_contents.payment_response.method_name
        == "tenzro:micropayment-channel"
    )

    # Tenzro VDC projections
    assert cart_vdc["payload"]["total_amount"] == 3_750
    assert sum(it["total"] for it in cart_vdc["payload"]["items"]) == 3_750
    assert intent_vdc["payload"]["max_amount"] == 5_000


def test_local_validation_passes_within_all_ceilings() -> None:
    intent = build_intent_mandate()
    cart = build_cart_mandate()
    intent_vdc = to_tenzro_intent_vdc(
        intent, principal_did=PRINCIPAL_DID, agent_did=DELEGATE_DID
    )
    cart_vdc = to_tenzro_cart_vdc(
        cart,
        intent_mandate_id=intent_vdc["payload"]["mandate_id"],
        agent_did=DELEGATE_DID,
        merchant_did="did:tenzro:machine:bookshop",
    )

    overall, results = local_validate_mandates(
        intent_vdc,
        cart_vdc,
        delegation_cap_cents=10_000,
        daily_remaining_cents=5_000,
    )
    assert overall, results
    labels = [label for label, _ok, _ in results]
    assert labels == [
        "AP2 IntentMandate constraints",
        "AP2 CartMandate consistency",
        "TDIP DelegationScope",
        "TDIP SpendingPolicy",
    ]


def test_local_validation_rejects_when_daily_window_exceeded() -> None:
    intent = build_intent_mandate()
    cart = build_cart_mandate()
    intent_vdc = to_tenzro_intent_vdc(
        intent, principal_did=PRINCIPAL_DID, agent_did=DELEGATE_DID
    )
    cart_vdc = to_tenzro_cart_vdc(
        cart,
        intent_mandate_id=intent_vdc["payload"]["mandate_id"],
        agent_did=DELEGATE_DID,
        merchant_did="did:tenzro:machine:bookshop",
    )
    overall, results = local_validate_mandates(
        intent_vdc,
        cart_vdc,
        delegation_cap_cents=10_000,
        daily_remaining_cents=1_000,  # only $10 left in daily window
    )
    assert not overall
    failed = [label for label, ok, _ in results if not ok]
    assert failed == ["TDIP SpendingPolicy"]


def test_compute_zk_commitment_matches_expected_shape() -> None:
    commitment = compute_zk_commitment(
        circuit_id="settlement",
        proof_hex="0xdeadbeef",
        public_inputs_hex=["0xcafebabe", "0xfeedface"],
    )
    assert commitment.startswith("0x")
    assert len(commitment) == 2 + 64  # SHA-256 hex


# ----------------------------------------------------------------------
# End-to-end via the stub RPC
# ----------------------------------------------------------------------


def test_run_end_to_end_against_stub_rpc(capsys: pytest.CaptureFixture[str]) -> None:
    with responses.RequestsMock() as rsps:
        _stub_resolve_human(rsps)
        _stub_resolve_machine(rsps)
        # validate + create_zk_proof are matcher-based (any-id)
        _stub_validate_mandate_pair(rsps)
        _stub_create_zk_proof(rsps)

        client = TenzroClient(rpc_url=STUB_RPC)
        rc = sample_main.run(client, offline=False)

    assert rc == 0
    captured = capsys.readouterr().out
    # Spot-check that the four ceilings + commitment were printed
    assert "AP2 IntentMandate constraints" in captured
    assert "AP2 CartMandate consistency" in captured
    assert "TDIP DelegationScope" in captured
    assert "TDIP SpendingPolicy" in captured
    assert re.search(r"commitment \(sha256\)\s+0x[0-9a-f]{64}", captured)
    assert "tenzro:micropayment-channel" in captured


def test_run_offline_mode_skips_rpc(capsys: pytest.CaptureFixture[str]) -> None:
    # No responses fixture: any HTTP call would raise.
    client = TenzroClient(rpc_url="https://invalid.tenzro.test")
    rc = sample_main.run(client, offline=True)
    assert rc == 0
    captured = capsys.readouterr().out
    assert "offline: literal DIDs only" in captured
    assert "offline mode — skipping create_zk_proof RPC" in captured
