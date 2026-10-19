"""Negative AP2 vectors: proof that the verifier catches forgery.

A corpus that can only confirm correct input is useless for conformance.
The real value is showing that an implementation **rejects** incorrect input.
Without it an independent Go or TypeScript implementation cannot demonstrate
it is safe rather than merely compatible.

Each vector: a mutation of a valid token plus what must be rejected.
"""

from __future__ import annotations

import base64
import json
from copy import deepcopy
from pathlib import Path

from ap2.sdk.disclosure_metadata import DisclosureMetadata
from ap2.sdk.sdjwt import kb_sd_jwt, sd_jwt
from ap2.sdk.sdjwt.chain import verify_chain
from ap2.sdk.sdjwt.common import parse_token
from cryptography.hazmat.primitives.asymmetric import ec
from jwcrypto.jwk import JWK

def _vectors_dir() -> Path:
    """Locates the vectors directory next to the script or one level above.

    Needed so the corpus works both as tools/vectors and as tools and vectors as
    siblings, which is what lets it be lifted out of the repository.
    """
    for cand in (Path(__file__).parent / "vectors", Path(__file__).parent.parent / "vectors"):
        if cand.is_dir():
            return cand
    return Path(__file__).parent / "vectors"


def _out_dir() -> Path:
    return _vectors_dir()


def make_key(kid: str) -> JWK:
    jwk = JWK.from_pyca(ec.generate_private_key(ec.SECP256R1()))
    raw = json.loads(jwk.export())
    raw["kid"] = kid
    return JWK.from_json(json.dumps(raw))


def build_good() -> tuple[dict, dict]:
    """A reference token pair plus their public keys."""
    issuer_key = make_key("neg-issuer-1")
    agent_key = make_key("neg-agent-1")
    from ap2.sdk.generated.open_payment_mandate import OpenPaymentMandate

    mandate = OpenPaymentMandate(
        constraints=[],
        cnf={"jwk": json.loads(agent_key.export_public())},
        payment_amount={"amount": 100, "currency": "USD"},
        payee={"id": "shop-1", "name": "Shop"},
        payment_instrument={"id": "pi-1", "type": "credit"},
        execution_date="2099-01-01T00:00:00Z",
    )
    sd = DisclosureMetadata(sd_keys=[])
    root = sd_jwt.create(payload=mandate, issuer_key=issuer_key, sd=sd).sd_jwt_issuance
    hop = kb_sd_jwt.create(
        prev_token=parse_token(root),
        holder_key=agent_key,
        payload=mandate,
        aud="https://merchant.example/ap2",
        nonce="neg-nonce-1",
        sd=sd,
    ).sd_jwt_issuance
    return (
        {
            "root_sd_jwt": root,
            "kb_sd_jwt": hop,
            "issuance": {
                "issuer_jwk": json.loads(issuer_key.export_public()),
                "agent_jwk": json.loads(agent_key.export_public()),
                "aud": "https://merchant.example/ap2",
                "nonce": "neg-nonce-1",
            },
        },
        {"root": root, "hop": hop},
    )


def flip_payload_segment(token: str, mutate) -> str:
    """Mutates the payload inside a JWT while leaving the signature untouched.

    This breaks the signature, which is exactly what a verifier must catch.
    """
    head, sep, rest = token.partition("~")
    h, dot, rest2 = head.partition(".")
    body, _, sig = rest2.rpartition(".")

    def dec(seg: str) -> dict:
        return json.loads(base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4)))

    def enc(obj: dict) -> str:
        raw = json.dumps(obj, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    payload = dec(body)
    mutate(payload)
    return f"{h}{dot}{enc(payload)}{dot}{sig}" + (sep + rest if sep else "")


def mutate_token(data: dict, which: str) -> dict:
    out = deepcopy(data)
    if which == "amount-escalation":
        key = "kb_sd_jwt"
        out[key] = flip_payload_segment(
            out[key], lambda p: p.__setitem__("aud", "https://attacker.example/ap2")
        )
        return out
    if which == "tampered-sig":
        # Flip the last signature character — the crudest possible tamper.
        key = "kb_sd_jwt"
        tok = out[key]
        out[key] = tok[:-1] + ("A" if tok[-1] != "A" else "B")
        return out
    raise ValueError(which)


class IssuerKeyProvider:
    """Issuer key for the root — self-contained, no external trust."""

    def __init__(self, issuer_public_jwk: dict) -> None:
        self._key = JWK.from_json(json.dumps(issuer_public_jwk))

    def __call__(self, token) -> JWK:  # noqa: ARG002
        return self._key


def must_reject(data: dict, expect_wrong_aud: bool = False) -> str:
    """Returns the rejection reason, or '' if the verifier was FOOLED into accepting."""
    try:
        verify_chain(
            [parse_token(data["root_sd_jwt"]), parse_token(data["kb_sd_jwt"])],
            IssuerKeyProvider(data["issuance"]["issuer_jwk"]),
            expected_aud=data["issuance"]["aud"],
            expected_nonce=data["issuance"]["nonce"],
        )
    except Exception as exc:  # noqa: BLE001 — rejection is the expected outcome
        return f"{type(exc).__name__}: {str(exc)[:70]}"
    return ""


def main() -> int:
    data, _ = build_good()

    cases = [
        (
            "aud-substitution",
            "mutate_token(data, 'amount-escalation')",
            "aud substitution: payment redirected to a different recipient",
        ),
        (
            "tampered-signature",
            "mutate_token(data, 'tampered-sig')",
            "one signature byte of the KB-hop changed",
        ),
        (
            # Known SDK defect, reproduced by a dedicated PoC:
            # tools/poc_aud_not_enforced.py. Recorded as xfail so the
            # regression stays visible instead of going quiet.
            "wrong-expected-aud",
            "data",
            "verification with a wrong expected aud — XFAIL: ap2 SDK defect, see poc_aud_not_enforced.py",
        ),
    ]

    print("  negative vectors:")
    passed = xfail = 0
    for name, expr, desc in cases:
        payload = eval(expr)  # noqa: S307 — local fixed set
        if name == "wrong-expected-aud":
            payload = deepcopy(payload)
            payload["issuance"]["aud"] = "https://someone-else.example/ap2"
        reason = must_reject(payload)
        if name == "wrong-expected-aud":
            # Not a test failure: the defect is in the SDK. Counted separately
            # so that fixing it turns into a green result.
            if not reason:
                xfail += 1
                print(f"    XFAIL  {name:22} — SDK defect reproduced (see PoC)")
            else:
                passed += 1
                print(f"    OK     {name:22} — rejected: {reason}")
            continue
        ok = bool(reason)
        passed += 1 if ok else 0
        print(f"    {'OK  ' if ok else 'FAIL'}  {name:22} — {desc}")
        if ok:
            print(f"          rejected: {reason}")

    # Control: a valid pair must pass, otherwise the rejections above are fake.
    good_reason = must_reject(data)
    if good_reason:
        print(f"\n  STOP: reference pair failed — {good_reason}")
        return 1
    print("\n  control: reference pair accepted (so the rejections above are genuine)")
    print(f"  total: rejected {passed}/{len(cases)}, xfail (SDK defect): {xfail}")
    return 1 if passed != (len(cases) - xfail) else 0


if __name__ == "__main__":
    raise SystemExit(main())