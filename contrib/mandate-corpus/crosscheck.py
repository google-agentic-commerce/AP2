#!/usr/bin/env python3
"""Cross-validation: the Go reference verifier against the Python one.

Why this file exists. The corpus claims it is usable by independent implementations
in other languages. That is only a claim. This script turns it into an enforced
contract: two independent implementations must reach the same verdict on every
vector or the build fails.

On 2026-10-04 no independent implementation existed: the Go sample in this very
repository has 2258 lines, zero cryptography and a hardcoded FakeJWT.

    python contrib/mandate-corpus/crosscheck.py

Expected output:

    agreements: 3/3, divergences: 0
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
GO_DIR = HERE / "go"
VECTORS = HERE / "vectors"

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code" / "sdk" / "python"))
from ap2.sdk.sdjwt.chain import verify_chain  # noqa: E402
from ap2.sdk.sdjwt.common import parse_token  # noqa: E402
from jwcrypto.jwk import JWK  # noqa: E402


class IssuerProvider:
    """Issuer key for the root token."""

    def __init__(self, jwk: dict) -> None:
        self._k = JWK.from_json(json.dumps(jwk))

    def __call__(self, _token) -> JWK:
        return self._k


def python_verdict(path: Path) -> str:
    d = json.loads(path.read_text(encoding="utf-8"))
    iss = d["issuance"]
    try:
        payloads = verify_chain(
            [parse_token(d["root_sd_jwt"]), parse_token(d["kb_sd_jwt"])],
            IssuerProvider(iss["issuer_jwk"]),
            expected_aud=iss["aud"],
            expected_nonce=iss["nonce"],
        )
    except Exception:  # noqa: BLE001 — a rejection is the verdict
        return "REJECT"
    return "ACCEPT" if payloads else "REJECT"


def go_verdict(name: str) -> str:
    go_bin = os.environ.get("GO_BIN", "go")
    r = subprocess.run(
        [go_bin, "run", "./cmd/verify", str(VECTORS)],
        capture_output=True,
        text=True,
        cwd=GO_DIR,
        timeout=600,
    )
    for line in r.stdout.splitlines():
        if line.strip().startswith(("OK", "FAIL")) and name in line:
            return "ACCEPT" if line.strip().startswith("OK") else "REJECT"
    return "ERROR"


def main() -> int:
    files = sorted(p for p in VECTORS.glob("*.json") if p.name != "index.json")
    if not files:
        print("  no vectors found")
        return 1

    agree = 0
    print(f"{'vector':<44}{'python':<9}{'go':<9}agree")
    print("─" * 71)
    for f in files:
        pv = python_verdict(f)
        gv = go_verdict(f.stem)
        same = pv == gv and pv == "ACCEPT"
        agree += same
        print(f"{f.stem[:43]:<44}{pv:<9}{gv:<9}{'yes' if same else 'NO'}")
        if not same:
            print(f"    python={pv} go={gv}")
    print("─" * 71)
    print(f"  agreements: {agree}/{len(files)}, divergences: {len(files) - agree}")
    return 0 if agree == len(files) else 1


if __name__ == "__main__":
    raise SystemExit(main())
