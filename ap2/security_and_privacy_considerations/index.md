# Security and Privacy Considerations

## Security Considerations

Agentic commerce introduces numerous potential security risks. Given the current state of agent security, AP2 assumes that preventing prompt injection attacks is infeasible. Therefore, all LLMs and Agents MUST be considered potential attackers and are explicitly included in the threat model.

### Manipulated Checkout

**Threat:**

- An attacker steals a signed and authorized Payment Mandate to use it with an unrelated Checkout.

**Mitigation**

- The Payment Mandate MUST contain a reference to its associated Checkout.
- This is via `transaction_id` for closed Payment Mandates and the `mandate.payment.reference` constraint for open ones.

**Threat:**

- An attacker reuses an open Payment Mandate with a different closed Payment Mandate.
- An attacker reuses an open Payment Mandate to approve a different closed Checkout Mandate.

**Mitigation**

- Closed Mandates MUST contain the `sd_hash` claim to bind them to the presented open Mandate.
- Open Mandates MUST contain the Agent's key (via a `cnf` claim) so that only the agent could create a Closed Mandate with a valid signature.

**Threat:**

- An attacker mismatches a closed Mandate with a different open Mandate.

**Mitigation**

- Closed Mandates MUST contain the `sd_hash` claim to bind them to the presented open Mandate.

**Threat:**

- An attacker uses a closed Checkout Mandate with a different checkout session.

**Mittigation**

- Merchant MUST verify that `checkout_hash` matches the hash of the latest `checkout_jwt`.

### Manipulated Payment

**Threat:**

- A Shopping or Credential Provider Agent manipulates the Payment in transit, or requests payment without (or differing from) the User's approved Mandate. This causes the Credential Provider to execute a Payment not approved by the Trusted Surface.

**Mitigation:**

- The Merchant Payment Processor and Credential Provider MUST verify the User's signature on the Payment Mandate to ensure its integrity.
- The `checkout_hash` embedded in the `transaction_id` securely links the payment to the associated Checkout Mandate.
- Constraint evaluation ensures the payment amounts and payees comply with the authorized limits.

### Payment Credential Theft

**Threat:**

- An attacker steals the User's Payment Credential or Token after its release to perform a payment in an unauthorized context.

**Mitigation:**

- The Payment Credential/Token MUST ONLY be released to the Merchant upon the receipt and verification of a final Payment Mandate. This binds the token to the specific transaction.

### Manipulated Discovery

**Threat:**

- Prompt injection causes the Shopping Agent to select malicious products or make poor purchase decisions.

**Mitigation:**

- The Merchant signature ensures the integrity of the offering.
- Even if the LLM fails to make the optimal choice, constraint enforcement during closed Mandate verification ensures that the worst-case financial and logical impacts are strictly bounded.

### Double Spend

**Threat:**

- A prompt injected, or otherwise malicious Shopping Agent attempts to approve multiple valid Checkouts using the same open Mandate.

**Mitigation:**

- The non-deterministic portion of the Shopping Agent MUST avoid signing multiple, overlapping closed Mandates for the same open Mandate without receiving Receipts rejecting the previously released Mandates.
- These Receipts MUST be integrity protected from the Shopping Agent's LLM.
- Credential Provider, Networks or MPPs MAY reject multiple overlapping Mandates, or invalidate previously issued payment tokens.

## Privacy Considerations

### Open Checkout and Payment Mandate Constraints

Open Checkout and Payment Mandate Constraints MAY contain information that is not applicable to the particular Checkout that would leak unnecessary user intent. Selective Disclosure MUST be used to preserve user privacy.

To enhance user privacy the Trusted Surface MAY insert decoy digests as described in RFC9901 Section 4.2.5.

### Checkout and Payment Data Minimization

To preserve user privacy and the principle of data minimization, Selective Disclosure is used to allow the Checkout Mandate and Payment Mandate to be shared with the relevant parties for securing the Checkout and Payment respectively. The `checkout_hash` links these Mandates allowing them to be joined in the case of a Dispute.

> Note: The information contained within the Mandates, or the Mandates themselves could be shared with other parties if appropriate agreements or channels exist, but that is outside the scope of AP2.

### Rainbow Table Attacks

Digests in SD-JWTs (for Payment and Checkout Mandates as well as Constraints) MUST include a salt with sufficient entropy to prevent guessing the plaintext. See RFC9901 Section 9.1. For more details.

The `checkout_hash` makes use of the entropy already included in the JWT signature to prevent guessing the Checkout contents. If a signing algorithm (e.g. deterministic signature scheme such as `Ed25519`) is used that does not include this then a salt of sufficient entropy MUST be present in the Checkout.
