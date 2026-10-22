"""Resolve a post-transaction AP2 dispute from the mandate chain.

Standalone (stdlib only, no LLM, no network). Reads a dispute record whose
evidence is exactly the AP2 artifacts a completed flow leaves behind -- the
closed Checkout Mandate's `checkout_hash`, the Payment Mandate
(`transaction_id`, `payee`, `payment_amount`, `iat`/`exp`), the Checkout
Receipt and Payment Receipt (`status`, `reference`, `order_id`/`payment_id`)
-- plus the merchant's order record, and produces a signed-shape
determination under a published policy (ATDRP-0.1).

Why this sample exists: AP2's audit trail is "aiding in dispute resolution"
(docs) but the protocol names no resolver. This shows a third party --
independent of user, agent, merchant, credentials provider and processor --
resolving scope and performance disputes from the trail alone. Fraud (a
chain that does not bind) is out of scope and is routed to the network,
which is where the protocol already sends it.

    python resolve_dispute.py dispute_record.json  # prints determination JSON
    python resolve_dispute.py dispute_record.json --now 2025-10-24

Decision rule (deterministic; a competing implementation must reproduce it):
  1. completed refund/credit >= line amount   -> uphold (moot)
  2. charged > mandated; executed after exp;
     mandate reuse                            -> overturn (excess / whole line)
  3. order canceled w/o refund; unfulfilled
     after the merchant's own est. delivery   -> overturn (unfulfilled share)
  4. instruction/cart conflict                -> recorded against the
                                                  AGENT PLATFORM; merchant's
                                                  charge stands
  5. otherwise                                -> uphold
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys

from pathlib import Path


POLICY = "ATDRP-0.1"


def chain_problems(rec: dict) -> list[str]:
    """Return binding problems between the checkout mandate and its receipts."""
    p: list[str] = []
    ch = rec["checkout_hash"]
    if rec["payment_mandate"].get("transaction_id") != ch:
        p.append("payment_mandate.transaction_id != checkout_hash")
    for name in ("checkout_receipt", "payment_receipt"):
        r = rec.get(name)
        if r is not None and r.get("reference") != ch:
            p.append(f"{name}.reference does not bind to the checkout mandate")
    return p


def _date_epoch(s: str) -> int:
    return int(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def _completed_adjustment(order: dict, line: dict) -> int:
    """Sum completed refund/credit adjustments that count against this line.

    Line-labelled adjustments count in full; order-level ones (no
    line_item_id) are allocated pro rata by line total so one refund
    cannot moot several lines.
    """

    def _ok(a) -> bool:
        status_ok = a.get("status", "completed") == "completed"
        return status_ok and a.get("type") in ("refund", "credit", "return")

    adjustments = [a for a in order.get("adjustments", []) if _ok(a)]
    line_id = line["id"]
    labelled = sum(
        int(a.get("amount", 0))
        for a in adjustments
        if a.get("line_item_id") == line_id
    )
    unlabelled = sum(
        int(a.get("amount", 0))
        for a in adjustments
        if a.get("line_item_id") is None
    )
    total = sum(int(ln.get("total", 0)) for ln in order.get("line_items", []))
    line_total = int(line.get("total", 0))
    share = round(unlabelled * line_total / total) if total > 0 else 0
    return labelled + share


def decide_line(rec: dict, line: dict, now_epoch: int) -> dict:  # noqa: PLR0915
    """Apply the ATDRP rule to one order line and return its outcome."""
    pm = rec["payment_mandate"]
    order = rec.get("order") or {}
    mandated = int(pm["payment_amount"]["amount"])
    pr = rec.get("payment_receipt") or {}
    charged = int(pr.get("charged_amount", mandated))
    line_amt = int(line.get("total", 0))
    q = line.get("quantity", {"ordered": 1, "current": 1, "fulfilled": 0})
    factors: dict[str, str] = {}
    reasons: list[str] = []

    adj = _completed_adjustment(order, line)
    factors["adjustments_already_made"] = (
        f"{adj} minor units already refunded/credited"
        if adj
        else "no completed adjustment on record"
    )
    if line_amt and adj >= line_amt:
        reasons.append(
            "claim is moot: a completed adjustment already covers the "
            "line amount"
        )
        factors.update(
            mandate_scope="not reached", merchant_performance="not reached"
        )
        return _out(line, "uphold", 0, reasons, factors, rec)

    scope: list[str] = []
    if charged > mandated:
        currency = pm["payment_amount"]["currency"]
        scope.append(
            f"charged {charged} exceeds mandated payment_amount "
            f"{mandated} {currency}"
        )
    exec_epoch = (
        _date_epoch(pm["execution_date"])
        if pm.get("execution_date")
        else int(pr.get("iat", pm["iat"]))
    )
    if pm.get("exp") is not None and exec_epoch > int(pm["exp"]):
        exp = pm["exp"]
        scope.append(
            f"payment executed at {exec_epoch}, after the mandate's exp {exp}"
        )
    reuse = int(rec.get("mandate_reuse_count", 1))
    if reuse > 1:
        scope.append(f"one payment mandate was used for {reuse} payments")
    factors["mandate_scope"] = (
        "within mandate" if not scope else "; ".join(scope)
    )
    if scope:
        dead = any("after the mandate" in s or "used for" in s for s in scope)
        amount = line_amt if dead else min(max(charged - mandated, 0), line_amt)
        reasons.extend(scope)
        factors["merchant_performance"] = "not reached"
        return _out(line, "overturn", amount, reasons, factors, rec)

    if order:
        unfulfilled = max(
            int(q.get("current", 1)) - int(q.get("fulfilled", 0)), 0
        )
        est = order.get("estimated_delivery") or {}
        latest = est.get("latest") or est.get("earliest")
        delivery_passed = bool(latest) and now_epoch > _date_epoch(
            latest + "T23:59:59+00:00"
        )
        if order.get("status") == "canceled" and adj < line_amt:
            factors["merchant_performance"] = (
                "order canceled by merchant; charge not returned"
            )
            reasons.append(
                "merchant canceled the order and no completed adjustment "
                "returned the charge"
            )
            return _out(line, "overturn", line_amt - adj, reasons, factors, rec)
        if unfulfilled > 0 and delivery_passed:
            current_qty = max(int(q.get("current", 1)), 1)
            share = round(line_amt * unfulfilled / current_qty) - adj
            fulfillment_events = sum(
                len(f.get("events", [])) for f in order.get("fulfillments", [])
            )
            factors["merchant_performance"] = (
                f"{unfulfilled} of {q.get('current')} units unfulfilled "
                f"after the merchant's estimated_delivery ({latest}); "
                f"{fulfillment_events} fulfillment events on record"
            )
            reasons.append(
                "merchant did not fulfill by its own estimated delivery date"
            )
            return _out(line, "overturn", max(share, 0), reasons, factors, rec)
        factors["merchant_performance"] = (
            f"status={order.get('status')}; {q.get('fulfilled', 0)}/"
            f"{q.get('current', 1)} fulfilled"
        )
    else:
        factors["merchant_performance"] = (
            "no order record supplied; performance unassessable"
        )

    if rec.get("user_instruction") and rec.get("confirmed_cart"):
        factors["intent_fidelity"] = (
            "instruction and confirmed cart both on record (compared by "
            "reviewer)"
        )
        factors["agent_platform_conduct"] = (
            "see intent_fidelity; any conflict is the platform's, not the "
            "merchant's"
        )
    else:
        factors["intent_fidelity"] = (
            "unassessable: agent platform did not retain the user's instruction"
        )
        risk_keys = sorted((pm.get("risk_data") or {}).keys()) or "none"
        factors["agent_platform_conduct"] = (
            f"risk_data keys: {risk_keys}; mandate used {reuse}x"
        )
    reasons.append(
        "payment within mandate scope and merchant performance on record: "
        "charge stands"
    )
    return _out(line, "uphold", 0, reasons, factors, rec)


def _out(line, outcome, amount, reasons, factors, rec) -> dict:  # noqa: PLR0913
    cur = rec["payment_mandate"]["payment_amount"]["currency"]
    return {
        "line_id": line["id"],
        "outcome": outcome,
        "amount": {"currency": cur, "amount": int(amount)},
        "reasons": reasons,
        "factors": factors,
    }


def resolve(rec: dict, now_epoch: int) -> dict:
    """Resolve a dispute record into a signed-shape determination document."""
    problems = chain_problems(rec)
    if problems:
        return {
            "dispute_id": rec["dispute_id"],
            "not_eligible": {
                "reason": "authorization_chain_broken",
                "detail": "; ".join(problems),
                "route": "network fraud process",
            },
        }
    if (rec.get("payment_receipt") or {}).get("status") != "Success":
        return {
            "dispute_id": rec["dispute_id"],
            "not_eligible": {"reason": "payment_not_successful"},
        }
    lines = (rec.get("order") or {}).get("line_items") or [
        {
            "id": "whole-transaction",
            "total": rec["payment_mandate"]["payment_amount"]["amount"],
            "quantity": {"ordered": 1, "current": 1, "fulfilled": 0},
        }
    ]
    claimed = set(
        rec.get("claim", {}).get("line_ids") or [ln["id"] for ln in lines]
    )
    per_line = [
        decide_line(rec, ln, now_epoch) for ln in lines if ln["id"] in claimed
    ]
    factors = per_line[0]["factors"] if per_line else {}
    body = {
        "determination_id": "det_"
        + hashlib.sha256(rec["dispute_id"].encode()).hexdigest()[:10],
        "dispute_id": rec["dispute_id"],
        "policy_version": POLICY,
        "per_line": [
            {k: v for k, v in d.items() if k != "factors"} for d in per_line
        ],
        "factors": factors,
        "prohibited_screened": True,
        "signer": {
            "name": "[human signer of record]",
            "credential": "[published credential]",
            "ai_assisted": False,
        },
        "issued_at": dt.datetime.fromtimestamp(now_epoch, dt.UTC)
        .isoformat()
        .replace("+00:00", "Z"),
        "fee_disposition": {
            "paid_by": "merchant"
            if any(d["outcome"] == "overturn" for d in per_line)
            else "payer",
            "amount": {
                "currency": rec["payment_mandate"]["payment_amount"][
                    "currency"
                ],
                "amount": 500,
            },
        },
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    body["seal"] = {
        "record_hash": "sha256:" + hashlib.sha256(canonical).hexdigest(),
        "chain_head": "sha256:"
        + hashlib.sha256(b"genesis" + canonical).hexdigest(),
        "verify_url": "https://example-neutral.invalid/verify/"
        + body["determination_id"],
    }
    return body


def main(argv=None) -> int:
    """Parse CLI args, resolve the dispute, and print the determination."""
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("record")
    ap.add_argument(
        "--now",
        default=None,
        help="ISO date to evaluate delivery windows against (default: today)",
    )
    a = ap.parse_args(argv)
    with Path(a.record).open(encoding="utf-8") as f:
        rec = json.load(f)
    now_epoch = (
        _date_epoch(a.now + "T12:00:00+00:00")
        if a.now
        else int(dt.datetime.now(dt.UTC).timestamp())
    )
    print(json.dumps(resolve(rec, now_epoch), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
