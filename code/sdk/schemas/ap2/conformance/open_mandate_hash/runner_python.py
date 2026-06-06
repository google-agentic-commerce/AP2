#!/usr/bin/env python
"""
runner_python.py — reference JCS runner for AP2 open_mandate_hash v0 vectors.

Reads ap2-omh-v0.json, recomputes JCS(RFC 8785)(mandate_body) + SHA-256 for
each vector, and verifies:

  1. recomputed SHA-256 == expected_open_mandate_hash
  2. base64(JCS bytes) == expected_jcs_bytes_b64
  3. pair expectations (same_hash_as / different_hash_from)

Usage:
    pip install rfc8785==0.1.4
    python runner_python.py ap2-omh-v0.json
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

import rfc8785


def hash_vector(body: dict) -> tuple[str, str]:
    """Return (jcs_bytes_b64, sha256_hex) for the canonical form of body."""
    jcs = rfc8785.dumps(body)
    return base64.b64encode(jcs).decode("ascii"), hashlib.sha256(jcs).hexdigest()


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: runner_python.py ap2-omh-v0.json", file=sys.stderr)
        return 2

    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    vectors = data["vectors"]
    by_id = {v["vector_id"]: v for v in vectors}

    pass_, fail = 0, 0
    computed: dict[str, str] = {}

    for v in vectors:
        bytes_b64, sha = hash_vector(v["mandate_body"])
        computed[v["vector_id"]] = sha
        expected_sha = v["expected_open_mandate_hash"].removeprefix("sha256:")
        bytes_ok = bytes_b64 == v["expected_jcs_bytes_b64"]
        sha_ok = sha == expected_sha
        ok = bytes_ok and sha_ok
        mark = "OK " if ok else "FAIL"
        print(f"  {mark}  {v['vector_id']:<34}  sha256:{sha}")
        if not ok:
            if not bytes_ok:
                print(f"        bytes mismatch")
            if not sha_ok:
                print(f"        expected sha256:{expected_sha}")
        pass_ += int(ok)
        fail += int(not ok)

    # Pair-invariant verification
    print("\n--- pair invariants ---")
    pair_fail = 0
    for v in vectors:
        exp = v.get("expectation", "")
        if exp.startswith("same_hash_as:"):
            other = exp.split(":", 1)[1]
            ok = computed[v["vector_id"]] == computed[other]
            mark = "OK " if ok else "FAIL"
            print(f"  {mark}  {v['vector_id']} == {other}")
            if not ok:
                pair_fail += 1
        elif exp.startswith("different_hash_from:"):
            other = exp.split(":", 1)[1]
            ok = computed[v["vector_id"]] != computed[other]
            mark = "OK " if ok else "FAIL"
            print(f"  {mark}  {v['vector_id']} != {other}")
            if not ok:
                pair_fail += 1

    print(f"\n{pass_}/{pass_ + fail} vectors match (rfc8785@0.1.4)")
    print(f"{pair_fail} pair-invariant failures")
    return 0 if (fail == 0 and pair_fail == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
