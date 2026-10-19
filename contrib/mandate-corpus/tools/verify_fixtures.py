"""Verification of the generated AP2 fixtures.

A fixture that cannot be verified is not a fixture, it is noise. This script
is the reference: it proves the signatures in `vectors/*.json` are valid, and any
other implementation (Go, TypeScript, PHP) can port the same checks and reach
the same result.

Uses `ap2.sdk.sdjwt.chain.verify_chain`, the supported SDK path that walks the
chain itself: the root is verified with the issuer key, each following hop with
the key from the previous hop's `cnf`.

Usage
-----
    .venv/bin/python contrib/mandate-corpus/tools/verify_fixtures.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ap2.sdk.sdjwt.chain import verify_chain
from ap2.sdk.sdjwt.common import ParsedToken, parse_token
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


class IssuerKeyProvider:
    """Supplies the issuer key for the root token.

    In production this is what `X5cOrKidPublicKeyProvider` does via the certificate in
    `x5c`. Here the key ships with the fixture so the corpus is self-contained
    and verifiable without external infrastructure trust.
    """

    def __init__(self, issuer_public_jwk: dict) -> None:
        self._key = JWK.from_json(json.dumps(issuer_public_jwk))

    def __call__(self, token: ParsedToken) -> JWK:  # noqa: ARG002
        return self._key


def check(path: Path) -> tuple[bool, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    issuance = data["issuance"]

    root = parse_token(data["root_sd_jwt"])
    hop = parse_token(data["kb_sd_jwt"])

    payloads = verify_chain(
        [root, hop],
        IssuerKeyProvider(issuance["issuer_jwk"]),
        expected_aud=issuance["aud"],
        expected_nonce=issuance["nonce"],
    )

    if len(payloads) != 2:
        return False, f"expected 2 payloads, got {len(payloads)}"

    # The root cnf must equal agent_jwk, otherwise the human signed an
    # authorisation that a different key can spend.
    root_payload = payloads[0]
    cnf_jwk = root_payload.get("cnf", {}).get("jwk")
    if cnf_jwk is None:
        return False, "root has no cnf.jwk — the authorisation is unenforceable"
    # cnf arrives as a JsonWebKey model or dict — normalise it to a canonical JWK.
    if isinstance(cnf_jwk, dict):
        cnf_jwk = JWK.from_json(json.dumps(cnf_jwk))
    if json.loads(cnf_jwk.export_public()) != json.loads(
        json.dumps(issuance["agent_jwk"])
    ):
        return False, "root cnf does not match agent_jwk"

    # The decoded mandate must match the reference payload.
    if root_payload.get("payment_amount") != data["plaintext_payload"].get("payment_amount"):
        return False, "payment_amount does not match the reference"

    return True, "chain valid, cnf=agent key, amount matches reference"


def main() -> int:
    # Read index.json rather than the directory: the manifest defines the
    # corpus, and stale files must not silently enter verification.
    index_path = _vectors_dir() / "index.json"
    if not index_path.exists():
        print("  no index.json — run generate_fixtures.py first")
        return 1
    files = [_vectors_dir() / e["file"] for e in json.loads(index_path.read_text(encoding="utf-8"))]
    files = [f for f in files if f.exists()]
    if not files:
        print("  no vectors — run generate_fixtures.py first")
        return 1

    failed = 0
    for f in files:
        try:
            ok, note = check(f)
        except Exception as exc:  # noqa: BLE001 — a failed vector matters, report why
            ok, note = False, f"{type(exc).__name__}: {exc}"
        print(f"  {'OK  ' if ok else 'FAIL'}  {f.name}  — {note}")
        failed += 0 if ok else 1

    print(f"\n  total: {len(files) - failed}/{len(files)} passed verification")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())