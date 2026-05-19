# Aggregate Constraint: Cross-Merchant Budget Reservation

This document defines the protocol pattern that the
[`cross_merchant_budget.py`](./cross_merchant_budget.py) sample
implements. It is normative for any AP2 deployment that wishes to
enforce a budget across multiple Checkouts under a single open
Mandate.

Status: **Draft**. Reference implementation: this sample.
Vocabulary alignment: [`aeoess/agent-governance-vocabulary`
crosswalk/budget_reservation.yaml][vocab].

[vocab]: https://github.com/aeoess/agent-governance-vocabulary/blob/main/crosswalk/budget_reservation.yaml

---

## 1. Scope

AP2 defines per-Checkout authorization. An open Checkout Mandate
authorizes the Shopping Agent to assemble closed Mandates under a
set of Constraints (§166 Modes). When the same open Mandate
authorizes purchases at more than one Merchant, each Merchant
evaluates Constraints against its own transaction history only.
Cumulative-spend Constraints (`BudgetEvaluator` and equivalents)
therefore admit a budget-overflow class of error: each Merchant
returns ALLOW independently while the sum of approved Checkouts
exceeds the Mandate's stated cap.

This document specifies an **Aggregate Constraint** evaluation
mode that closes the gap by routing the cumulative-spend check
through an external Budget Authority that holds a single ledger
across all Merchants bound by the same Mandate.

This document does **not**:

- modify any AP2 wire format, JWT claim, or Mandate signature
  scheme
- redefine the roles, Modes, or Verification rules of AP2 §30, §166,
  §292
- mandate a specific Budget Authority implementation, deployment
  topology, or settlement currency
- specify cross-Mandate aggregation; each Aggregate Constraint
  scope is a single `mandate_id`

It extends AP2's Mandate Constraints extension point (§371) with
a new Constraint `type` whose evaluation is non-local.

---

## 2. Definitions

**Aggregate Constraint** — a Mandate Constraint whose evaluation
requires state from more than one Checkout. Distinguished from a
Local Constraint, which evaluates against the closed Mandate alone.

**Budget Authority** — a service that holds the canonical ledger
for one or more Mandates' aggregate state. Reachable by every
Verifying Party (§292) bound to those Mandates. Identified to AP2
Verifiers by a `budget_authority` field inside the Aggregate
Constraint's evaluation parameters.

**Reservation** — an atomic claim of budget capacity recorded by
the Budget Authority before a Merchant returns a Checkout Receipt.
Has a `reservation_id`, a `mandate_id`, an `amount`, and a status
in `{HELD, COMMITTED, RELEASED}`. Reservations in `HELD` reduce
remaining budget but do not contribute to `spent`.

**Commitment** — the transition of a Reservation from `HELD` to
`COMMITTED`. Executed by the Verifying Party after the payment has
been confirmed by the Credential Provider (§319) or the Merchant
Payment Processor (§335).

**Release** — the transition of a Reservation from `HELD` to
`RELEASED`. Executed by the Verifying Party if the payment fails
or the Shopping Agent withdraws the Checkout before commit.
Distinct from Refund.

**Refund** — a reversal of a previously `COMMITTED` Reservation
that restores some or all of its amount to remaining budget. Out
of scope for this sample; defined by `crosswalk/budget_reservation.yaml`
for completeness.

**Idempotency key** — a unique value chosen by the Verifying Party
when calling `reserve`. The Budget Authority MUST return the same
`ReserveResult` for any subsequent call carrying the same
`idempotency_key` within the lifetime of the underlying
Reservation, regardless of `amount` re-presentation.

---

## 3. Protocol-Level Requirements

### 3.1 The Budget Authority MUST

1. Maintain a single ledger keyed by `mandate_id`. State per
   Mandate consists of `budget`, `spent`, and `held` totals plus
   a Reservation table.
2. Make `reserve` atomic with respect to budget evaluation: the
   check that `amount ≤ remaining` and the insertion of the
   Reservation into the ledger happen in one logical step. No
   pair of concurrent `reserve` calls under the same `mandate_id`
   MAY both succeed if their combined `amount` exceeds remaining.
3. Persist Reservations across restarts. A Reservation in `HELD`
   that is lost would re-enable double-spend.
4. Deduplicate `reserve` calls by `idempotency_key`. A repeated
   `idempotency_key` MUST return the same Reservation, not a new
   one. This is required because Verifying Parties retry on
   timeouts and partial network errors.
5. Reject `commit` and `release` calls against any Reservation
   not in `HELD` status. State transitions are strictly
   `HELD → COMMITTED` or `HELD → RELEASED`; no other transitions
   are valid in this protocol.
6. Expose `query_budget(mandate_id)` returning current `budget`,
   `spent`, `held`, and `remaining = budget − spent − held`.
   `remaining` is the value an evaluator SHOULD treat as the
   cap on the next `reserve`.

### 3.2 Verifying Parties MUST

A Verifying Party in the sense of AP2 §292 (Merchant, Credential
Provider, Network, Merchant Payment Processor) that processes a
Mandate carrying an Aggregate Constraint of `type =
"budget_reservation_v1"` MUST:

1. Identify the Budget Authority from the Constraint's
   `budget_authority` parameter and verify that the URI resolves
   to a service whose key material is known to the deployment.
   This document does not specify discovery; consult the
   deployment's trust policy.
2. Call `reserve(mandate_id, amount_cents, idempotency_key)`
   before completing its own Verification (§302, §319, §335).
3. Return a Checkout Receipt or Payment Receipt with the
   appropriate error if `reserve` returns `DENY`.
4. Call `commit(reservation_id)` after the underlying payment has
   been confirmed by the Credential Provider or the Merchant
   Payment Processor.
5. Call `release(reservation_id)` if the underlying payment fails
   or the Shopping Agent withdraws the Checkout before commit.
6. Treat a `reserve` response of `ALLOW_WITH_CAPS` as `DENY`
   unless the Verifying Party's deployment is explicitly designed
   to handle partial fulfillment (see §4.3).
7. Use a fresh `idempotency_key` per logical Checkout, not per
   retry. Retries against the same logical Checkout MUST present
   the same `idempotency_key`.

### 3.3 Shopping Agents MUST

When assembling a Checkout under an open Mandate carrying an
Aggregate Constraint of `type = "budget_reservation_v1"`:

1. Treat any Verifying Party error referencing the Aggregate
   Constraint as terminal for the current Checkout. The Shopping
   Agent MUST NOT retry the Checkout with a different
   `idempotency_key` to obtain a fresh Reservation attempt.
2. Be prepared to receive `DENY` even if a recent `query_budget`
   indicated sufficient `remaining`, because another Verifying
   Party may have committed in the interval.
3. Make no assumption that `release` is automatic. Withdrawn
   Checkouts SHOULD be communicated to the originating Verifying
   Party so that party can issue a `release` against its
   Reservation.

---

## 4. Verb Interface

Canonical six verbs. The signatures below are non-binding —
this document specifies behavior, not transport. The sample
implements four; `refund` and `query_reservation` are normative
in `crosswalk/budget_reservation.yaml` but out of scope here.

### 4.1 `reserve(mandate_id, amount_cents, idempotency_key) → ReserveResult`

Atomically check budget and place a Reservation. See §3.1 for
authority requirements. Returns a `ReserveResult` whose
`decision` is one of `ALLOW`, `ALLOW_WITH_CAPS`, or `DENY` (§5).

### 4.2 `commit(reservation_id) → bool`

Transition a `HELD` Reservation to `COMMITTED`. Idempotent:
re-calling `commit` on an already-`COMMITTED` Reservation MUST
return `True` without side effect.

### 4.3 `release(reservation_id) → bool`

Transition a `HELD` Reservation to `RELEASED`. Returns budget
capacity to `remaining`. Idempotent under the same rule as
`commit`. `release` is pre-commit only; reversal of a committed
amount requires `refund` (out of scope).

### 4.4 `query_budget(mandate_id) → BudgetState`

Return current `budget`, `spent`, `held`, `remaining`. Strictly
informational. A Shopping Agent SHOULD NOT use `query_budget` to
gate its own decisions, because the value is racy with respect
to other Verifying Parties' `reserve` calls.

---

## 5. Decision Shape

The `decision` field returned by `reserve` is one of three
canonical values, aligned with
`crosswalk/budget_reservation.yaml`:

| Decision | Meaning |
|---|---|
| `ALLOW` | Full requested amount approved. The `allowed_amount` field equals the `requested_amount`. |
| `ALLOW_WITH_CAPS` | Partial budget remains. The `allowed_amount` is strictly less than `requested_amount` and strictly greater than zero. |
| `DENY` | No budget remains, or another error blocks the reservation. `reason` carries the explanation. |

`ALLOW_WITH_CAPS` is meaningful for divisible budgets (API
credits, streaming, stablecoin micropayments). A retail Checkout
that cannot be partially fulfilled MUST treat `ALLOW_WITH_CAPS`
as `DENY`. The safe default is `DENY` — Verifying Parties that
have not implemented partial fulfillment MUST take the safe
default (§3.2.6).

The reference implementation in this sample emits `ALLOW` or
`DENY` only, because a retail Checkout at fixed price is
indivisible. See [Cycles][cycles] for a Budget Authority that
emits `ALLOW_WITH_CAPS` against metered API credits.

[cycles]: https://runcycles.io

---

## 6. Composition with AP2 Mandate Constraints

AP2 specification.md §371 defines Mandate Constraints as the
extension point for new authorization rules. A new Constraint
type is registered by specifying:

> - A uniquely defined `type`.
> - A Schema, including which fields are selectively disclosable.
> - The evaluation algorithm.

This document registers `type = "budget_reservation_v1"` with the
following schema and evaluation:

**Schema** (informative; format-binding deferred to deployment):

```
{
  "type": "budget_reservation_v1",
  "budget_authority": "<URI of Authority>",
  "mandate_id": "<binding key for Authority's ledger>",
  "max_amount": <integer, minor units>,
  "currency": "<ISO 4217 code or stablecoin asset id>"
}
```

`budget_authority` and `mandate_id` are NOT selectively
disclosable. Both are required for any Verifying Party to perform
the cumulative check. `max_amount` and `currency` MAY be
selectively disclosable per deployment policy.

**Evaluation algorithm:** the Verifying Party MUST call
`reserve(mandate_id, amount_cents, idempotency_key)` on the
identified Budget Authority as part of its Verification (§3.2).
The Constraint evaluates to `pass` if `reserve` returns `ALLOW`,
or if `reserve` returns `ALLOW_WITH_CAPS` and the Verifying Party
is a deployment that handles partial fulfillment per §3.2.6.
The Constraint evaluates to `fail` otherwise, including the case
where the Authority is unreachable.

This is a non-local Constraint: it cannot be evaluated by the
closed Mandate alone. Verifying Parties that do not have network
access to the named Budget Authority MUST treat the Constraint as
`fail` (safe default).

---

## 7. Reference Implementations

| Implementation | Verbs | Decision values |
|---|---|---|
| This sample (`cross_merchant_budget.py`) | reserve, commit, release, query_budget | ALLOW, DENY |
| [Cycles][cycles] | reserve, commit, release, refund, query_budget, query_reservation | ALLOW, ALLOW_WITH_CAPS, DENY |
| [aeoess/agent-governance-vocabulary][vocab] crosswalk/budget_reservation.yaml | Canonical six-verb interface, three-value Decision | — |

---

## 8. Open Questions

The following are deliberately unresolved in this draft. Each
admits multiple defensible answers and the right answer is likely
deployment-specific.

1. **Discovery and trust.** This document does not specify how a
   Verifying Party learns the public key of a `budget_authority`
   URI. Deployments using Trusted Surfaces (§166) may distribute
   keys via the same surface; deployments using DID-based identity
   may resolve the URI as a `did:web` document. The mechanism is
   out of scope.
2. **Dispute integration.** Where does a Reservation surface in
   §262 Dispute Evidence? The `reservation_id`, the Authority's
   signed log of state transitions, and the `commit` timestamp
   are candidates. This document does not commit to a shape.
3. **Cross-rail composition.** A Mandate may carry both an AP2
   Aggregate Constraint and an x402/MPP equivalent against the
   same conceptual budget. Whether the Authority is shared or two
   Authorities reconcile out of band is a deployment choice.
4. **Multi-asset budgets.** This document defines `max_amount` and
   `currency` per Constraint, implying one Constraint per asset.
   A composite-budget shape (e.g., `total_usd_equivalent` across
   stablecoin and fiat) requires additional rules and is not
   specified here.
5. **Reservation expiry.** The sample's `HELD` state has no
   timeout. Production Authorities will need expiry to recover
   capacity abandoned by failed Verifying Parties. The expiry
   policy (fixed, exponential, Authority-configurable) is out of
   scope.
6. **Signed reservation attestations.** Whether a Reservation
   itself should be a signed artifact (so that a Verifying Party
   can present it as evidence) is unresolved. The reference
   implementation returns plain `ReserveResult`; production may
   want JWT or SD-JWT shape.

---

## 9. Relationship to existing AP2 issues and external work

- [AP2 #207][207] — original gap discussion. This document and
  sample address the gap directly.
- [AP2 #252][252] — the PR carrying this sample and document.
- [ACP #231][acp231] — three-layer model (passport / budget
  reservation / payment rail) accepted by `aeoess` and folded
  into `crosswalk/budget_reservation.yaml`.
- [Cycles][cycles] — independent production implementation of
  `reserve / commit / release` with `ALLOW_WITH_CAPS` exercised.

[207]: https://github.com/google-agentic-commerce/AP2/issues/207
[252]: https://github.com/google-agentic-commerce/AP2/pull/252
[acp231]: https://github.com/agentic-commerce-protocol/agentic-commerce-protocol/issues/231
