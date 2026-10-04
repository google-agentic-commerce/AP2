"""Generator for signed AP2 mandate fixtures.

The gap this project closes
---------------------------
google-agentic-commerce/AP2 contains no fixture, corpus, vector or
``fixture`` / ``corpus`` / ``vector`` / ``conformance``. the Python SDK can sign (`sd_jwt.create`, `kb_sd_jwt.create`)
but nobody publishes signed fixtures.

conformance directory. As a result the positive test in
Universal-Commerce-Protocol/conformance is skipped, as stated verbatim in PR #115:
«A real positive needs a signed SD-JWT+kb mandate fixture and a signing
model, which this PR does not attempt».

Why this is needed: the fixtures are not for this SDK but for independent
implementations in other languages (Go, TypeScript, PHP all exist already).
They need a byte-level reference they can be checked against.

An AP2 subtlety that must not be missed
---------------------------------------
The root SD-JWT must carry a `cnf` naming the agent key **before** the human
signs the authorisation, otherwise the human authorises a spending authority
nobody can use. That is exactly the defect described in
`openmobilehub/credentagent` PR #189: «the human signed over a key that was
then discarded and replaced».

Usage
-----
    .venv/bin/python contrib/mandate-corpus/tools/generate_fixtures.py
"""

from __future__ import annotations

import json
from pathlib import Path

from ap2.sdk.disclosure_metadata import DisclosureMetadata
from ap2.sdk.generated.open_payment_mandate import OpenPaymentMandate
from ap2.sdk.sdjwt import kb_sd_jwt, sd_jwt
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


def cnf_of(key: JWK) -> dict:
    """cnf binding to the agent key — this is what makes the authority executable."""
    return {"jwk": json.loads(key.export_public())}


def emit(seed: dict) -> dict:
    issuer_key = make_key(seed["issuer_kid"])
    agent_key = make_key(seed["agent_kid"])

    root_mandate = OpenPaymentMandate(
        constraints=[],
        cnf=cnf_of(agent_key),
        payment_amount={"amount": seed["amount"], "currency": seed["currency"]},
        payee={"id": seed["payee"], "name": seed["payee_name"]},
        payment_instrument={"id": seed["instrument"], "type": seed["instrument_type"]},
        execution_date=seed["expiry"],
    )

    # ``sd_keys=[]`` is essential: cnf must always be visible, otherwise the
    # mandate is signed but unenforceable (defect from credentagent PR #189).
    # DisclosureMetadata.from_model auto-derivation hides everything under _sd.
    public = DisclosureMetadata(sd_keys=[])

    # Hop 0 — root SD-JWT: issued by the wallet, carries the agent cnf.
    root = sd_jwt.create(
        payload=root_mandate, issuer_key=issuer_key, sd=public
    ).sd_jwt_issuance

    # Hop 1 — KB-SD-JWT: signed by the key the agent actually spends with.
    hop = kb_sd_jwt.create(
        prev_token=parse_token(root),
        holder_key=agent_key,
        payload=root_mandate,
        aud=seed["aud"],
        nonce=seed["nonce"],
        sd=public,
    ).sd_jwt_issuance

    return {
        "id": seed["id"],
        "description": seed["description"],
        "expected": seed["expected"],
        "issuance": {
            "issuer_jwk": json.loads(issuer_key.export_public()),
            "agent_jwk": json.loads(agent_key.export_public()),
            "aud": seed["aud"],
            "nonce": seed["nonce"],
        },
        "root_sd_jwt": root,
        "kb_sd_jwt": hop,
        "plaintext_payload": json.loads(root_mandate.model_dump_json()),
    }


SEEDS = [
    {
        "id": "open-payment-mandate-card-basic",
        "description": "Baseline open payment mandate: 100 USD by card, payee Shop.",
        "expected": "Root and KB-hop signatures are valid; root cnf equals agent_jwk.",
        "amount": 100,
        "currency": "USD",
        "payee": "shop-basic",
        "payee_name": "Shop",
        "instrument": "pi-basic-1",
        "instrument_type": "credit",
        "expiry": "2027-01-01T00:00:00Z",
        "aud": "https://merchant.example/ap2",
        "nonce": "fixture-nonce-0001",
        "issuer_kid": "fixture-issuer-1",
        "agent_kid": "fixture-agent-1",
    },
    {
        "id": "open-payment-mandate-debit-large",
        "description": "Large debit-card payment — exercises amount boundaries.",
        "expected": "Amount and currency decode without loss; currency is never silently changed.",
        "amount": 50000,
        "currency": "USD",
        "payee": "shop-large",
        "payee_name": "Shop Large",
        "instrument": "pi-large-1",
        "instrument_type": "debit",
        "expiry": "2027-06-30T00:00:00Z",
        "aud": "https://merchant.example/ap2",
        "nonce": "fixture-nonce-0002",
        "issuer_kid": "fixture-issuer-2",
        "agent_kid": "fixture-agent-2",
    },
    {
        "id": "open-payment-mandate-nonusd",
        "description": "Non-USD currency — catches implementations that silently normalise to dollars.",
        "expected": "Currency in the signature and in the payload match character for character.",
        "amount": 25000,
        "currency": "BRL",
        "payee": "shop-brasil",
        "payee_name": "Loja Brasil",
        "instrument": "pi-brl-1",
        "instrument_type": "credit",
        "expiry": "2027-03-31T00:00:00Z",
        "aud": "https://merchant.example/br/ap2",
        "nonce": "fixture-nonce-0003",
        "issuer_kid": "fixture-issuer-3",
        "agent_kid": "fixture-agent-3",
    },
]


def main() -> None:
    _out_dir().mkdir(exist_ok=True)
    index = []
    for seed in SEEDS:
        built = emit(seed)
        path = _out_dir() / f"{seed['id']}.json"
        path.write_text(json.dumps(built, indent=2, ensure_ascii=False), encoding="utf-8")
        index.append({"id": built["id"], "file": path.name, "expected": built["expected"]})
        print(f"  created  {path.name}  ({path.stat().st_size} bytes)")
    (_out_dir() / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  created  index.json  ({len(index)} vectors)")


if __name__ == "__main__":
    main()