# Life of a Negotiation

The [AP2-Haggle extension](../haggle-extension.md) introduces a multi-round
bargaining phase between a Shopping Agent and a Merchant Agent that sits
between the base AP2 steps of *Discovery* and *Merchant Validates Cart*. The
output of a successful negotiation is a standard AP2 `CartMandate`, so
everything that happens after — payment method selection, payment mandate
creation, issuer authorization — is identical to the baseline AP2 flow.

## When to negotiate

The Shopping Agent opts into negotiation on a per-task basis. The trigger is
purely additive: when sending the opening `IntentMandate` Message, the
Shopping Agent attaches an extra DataPart keyed
`ap2.haggle.NegotiationConstraints`. Its absence means the merchant should
respond with one or more CartMandates as in the baseline AP2 flow.

Typical reasons to negotiate:

- Price is discretionary (retail, services, contracts).
- The buyer has leverage worth exchanging — loyalty history, bulk volume,
  competitor quotes, flexible delivery windows.
- The deal has multiple trade-off axes (price vs. warranty, delivery speed
  vs. cost, contract length vs. per-month rate).

## Flow summary

1. **User intent**. The user delegates a shopping task to the Shopping
   Agent and optionally supplies bargaining hints (budget ceiling,
   preferred price, must-have terms, urgency cues).
2. **Constraints assembly**. The Shopping Agent distils those hints into a
   `NegotiationConstraints` object: `max_rounds`, `deadline`,
   `target_terms`, `walk_away_terms`, `required_terms`, `strategy_hint`,
   `style`.
3. **Open negotiation**. The Shopping Agent sends an A2A Message to the
   Merchant Agent carrying **both** the `IntentMandate` and the
   `NegotiationConstraints` DataParts.
4. **Opening offer**. The Merchant Agent recognises the constraints DataPart
   and delegates to its seller-strategist (an LLM sub-agent with access to
   inventory, cost floors and loyalty data). The merchant responds with an
   `Offer` (round 0), unsigned, embedding a plain `CartContents` and a list
   of structured `Argument`s.
5. **Round loop**. For each subsequent round:
   1. The receiving agent's negotiator sub-agent evaluates the incoming
      Offer against its own side's constraints and strategy.
   2. It decides one of three actions: **accept**, **counter**, or **walk
      away**.
   3. On **counter**, it constructs a new `Offer` with an incremented
      `round_number` and `parent_offer_id` pointing to the offer it is
      responding to, then sends it over A2A.
6. **Termination**. The loop ends when one of:
   - Both sides agree (`status="accepted"`).
   - `max_rounds` is reached without convergence (`status="rejected"`).
   - `deadline` is crossed (`status="expired"`).
   - Either side walks away (`status="abandoned"`).
7. **Signed CartMandate on acceptance**. On `accepted`, the merchant
   re-wraps the winning Offer's `cart_contents` as a standard AP2
   `CartMandate`, applying its normal `merchant_authorization` JWT. The
   `NegotiationOutcome` message carries this CartMandate both in its
   `final_cart_mandate` field and as a top-level `ap2.mandates.CartMandate`
   DataPart.
8. **Baseline AP2 resumes**. The Shopping Agent treats the returned
   CartMandate exactly as it would in the non-negotiation flow: it collects
   a shipping address, re-signs via `update_cart`, gathers a payment
   method, creates a PaymentMandate, signs on the user's device, and
   initiates payment. No downstream agent sees anything protocol-new.

## Decision rules inside a negotiator

Each negotiator LLM sub-agent receives three inputs per round:

- **Its side's constraints.** Cost floors + inventory for the merchant;
  `NegotiationConstraints` for the shopper.
- **Offer history.** The complete ordered list of Offers so far in this
  `contextId`.
- **The latest incoming Offer.** The one it must respond to.

Recommended evaluation order:

1. Check `required_terms` (shopper side) or hard floors (merchant side).
   If violated and un-negotiable, emit walk away.
2. Check `walk_away_terms` — can the offer be moved toward acceptability
   within the remaining rounds?
3. Compare to `target_terms`. If close enough, emit accept.
4. Otherwise, generate a counter-offer:
   - Select which axes to concede on (price, warranty, delivery…).
   - Select which arguments to deploy (loyalty, bulk, competitor quote,
     SLA upgrade, urgency).
   - Size the concession so that convergence is plausible within
     `max_rounds - round_number` remaining rounds.

## What each side sees and stores

| Party | Input | Retained state |
|---|---|---|
| Shopper | Own `NegotiationConstraints`, full offer history, latest merchant Offer | Offer history, walk-away rationale |
| Merchant | Inventory + cost floor + loyalty record, full offer history, latest shopper Offer | Offer history, proposed CartContents drafts |
| Credentials Provider | Nothing until acceptance | — |
| Payment Processor | Nothing until acceptance | — |

## Failure modes and how to surface them

- **Timeout / expired**: the Shopping Agent presents the user with the
  final unaccepted Offer and the `NegotiationOutcome.summary`.
- **Walk-away**: the user sees the reason (e.g. *"Merchant would not go
  below $980; your cap was $900."*) and may relax constraints for a retry.
- **Rejected (rounds exhausted)**: same UX as walk-away — show the final
  positions and the summary narrative.
- **Accepted**: the user sees the final cart and the negotiation summary,
  then proceeds with the standard AP2 confirmation surface.

## Relationship to AP2 primary mandates

- The `IntentMandate` still describes what the user wants — it is unchanged.
  Negotiation preferences live in the separate `NegotiationConstraints`
  DataPart so that an intent survives a failed negotiation and can be
  replayed with different constraints.
- The `CartMandate` is created exactly once per negotiation, at the
  acceptance moment. This is structurally identical to the baseline AP2
  flow, just produced later in the conversation.
- The `PaymentMandate` path is completely untouched. The
  credentials-provider and payment-processor see a standard AP2 handoff.
