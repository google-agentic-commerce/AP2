# Agentic Payment Protocol (v0.2)

The Agentic Payment Protocol (AP2) provides a protocol to secure Agent-performed
payment transactions. It makes use of the
[Agent Authorization model](agent_authorization.md).

This specification describes the following:

-   The different roles of entities within AP2.
-   The verification responsibilities of these roles.
-   A [Checkout Mandate](checkout_mandate.md) and
    [Receipt](checkout_mandate.md#checkout-receipt) for securing *what* is being
    purchased.
-   A linked [Payment Mandate](payment_mandate.md) and
    [Receipt](payment_mandate.md#payment-receipt) for the *payment* of the
    Checkout.
-   How the Checkout and Payment Mandates can be used as evidence at the time of
    dispute.

AP2 operates as a security feature within a Commerce Protocol. The exact details
of the Commerce Protocol (e.g., catalog APIs, checkout updates, and specific
APIs for communication between the different roles) are outside the scope of
AP2. AP2 is designed explicitly to be compatible with the Universal Commerce
Protocol (UCP) and integrates seamlessly.

Illustrative examples are provided for
[Human Present ('direct')](flows.md#human-present) and
[Human Not Present ('autonomous')](flows.md#human-not-present) flows.

## Roles

AP2 considers five roles, who have different responsibilities from a processing
and verification perspective. These are as follows:

-   **Shopping Agent (SA):** The Shopping Agent is the primary agent performing
    product discovery, building the checkout, and executing the purchase.
-   **Credential Provider (CP):** The Credential Provider is the source of
    Payment Credentials for the purchase. They are responsible for verifying
    that this Agent is authorized to access this Payment Credential, and scoping
    the Payment Credential appropriately.
-   **Merchant (M):** The Merchant role is responsible for providing and
    completing the Checkout. They verify that the Shopping Agent is approved to
    purchase these particular items and are responsible for the integrity of the
    inventory, pricing, and any merchant discounts.
-   **Merchant Payment Processor (MPP):** The Merchant Payment Processor role is
    responsible for processing payments for purchases. They are responsible for
    verifying that the Payment Credential shared by the Credential Provider has
    been authorized to pay for this Checkout instance.
-   **Trusted Surface (TS):** The Trusted Surface role is a UI surface that is
    trusted to get informed user consent for an Intent before creating a
    user-signed Mandate.

> Note: While AP2 defines five roles, it is possible for a single entity to play
> multiple (or even all) of the roles. In that case, they would take on all of
> the responsibilities of each role they are playing.

Roles MAY always delegate their responsibilities to another party.

## Agentic vs Non-Agentic

Many of these roles can be considered Agentic or Non-Agentic. A role is Agentic
when:

-   Communication to or from the Role is handled by a non-deterministic LLM.

A role is considered Non-Agentic if:

-   Communication to and from the Role is handled using deterministic code that
    verifies the authenticity and correctness.
-   And if no processing done by the role is delegated to an LLM.

The following roles MAY be agentic or non-agentic:

-   Merchant
-   Merchant Payment Processor
-   Credential Provider

The following role MUST be non-agentic:

-   Trusted Surface

The following role is expected to be agentic:

-   Shopping Agent

When communication happens between two non-agentic Roles, standard web security
is sufficient to ensure integrity. However, when either role is agentic, then
the Agent itself is a potential attacker. As such, additional tamper-evident
mechanisms are needed to ensure secure communication.

AP2 assumes that, at a minimum, the Shopping Agent is agentic. In the case where
the payment journey happens directly between two non-agentic surfaces (such as a
Trusted Surface communicating directly with a non-agentic Merchant), then
existing e-commerce security models are sufficient.

When this document refers to validation or processing for a particular role, it
MUST happen in deterministic code regardless of whether the role is agentic or
not.

## Mandates

Mandates are the core means that AP2 uses to authorize agents. See
[Agent Authorization Framework][agent_authorization.md] for a description of
how this works in the general case.

AP2 defines two
Mandate types: Checkout Mandate and Payment Mandate.

The Checkout and Payment Mandate contents are assembled by the Shopping Agent
after it has determined what task the user wishes it to perform. The exact
details of how this is achieved is outside of the scope of this specification.

The Shopping Agent then uses a Trusted Surface to obtain signed Checkout and
Payment Mandates, which it will use to authorize payment and complete the
Checkout.

### Checkout Mandate

The Checkout Mandate is designed to provide the Merchant cryptographic proof
that the Shopping Agent is authorized to purchase the Checkout that it has
assembled.

The Checkout Mandate is provided by the Shopping Agent and verified by the
Merchant.

The The Merchant MUST provide a merchant-signed JWT containing the Checkout to
the Shopping Agent. The closed Checkout Mandate is bound to this Checkout JWT
using a cryptographic hash.

Once the Merchant has accepted or rejected the Checkout Mandate, it MUST return
a Checkout Receipt.

For the full details of the Checkout Mandate and Receipt structures, see
[Checkout Mandate](checkout_mandate.md).

### Mandate Versioning

Each AP2 Mandate type identifies its schema using the `vct` claim. The `vct`
value includes a numeric suffix that acts as a schema version number (e.g.
`mandate.payment.1`, `mandate.checkout.open.1`). Implementations MUST match the
exact `vct` string, including the version suffix. A future incompatible schema
revision would introduce a new suffix (e.g. `.2`), allowing old and new versions
to be distinguished unambiguously.

### Payment Mandate

The Payment Mandate is designed to provide the Credential Provider, Network, and
Merchant Payment Processor cryptographic proof that the Shopping Agent is
authorized to pay for a particular Checkout.

The Payment Mandate is provided by the Shopping Agent and verified by the
Credential Provider, Network, and Merchant Payment Processor.

The Payment Mandate is bound to a particular Checkout using the cryptographic
hash of the Checkout JWT. To prevent rainbow table attacks, the Checkout JWT
MUST be signed using a digital signature scheme (e.g., ECDSA) and not a
deterministic signature (e.g., Ed25519).

Once the Merchant Payment Processor has accepted or rejected the Payment
Mandate, a signed Payment Receipt MUST be returned to the Shopping Agent,
Credential Provider, and possibly Networks.

For the full details of the Payment Mandate and Receipt structures, see
[Payment Mandate](payment_mandate.md).

## Modes

There are two `modes` that AP2 can consider to operate in.

-   Human Present (Direct): The User directly sees the closed Checkout and
    approves it and its payment explicitly.

-   Human Not Present (Autonomous): The User sees and approves a set of
    constraints over what closed Checkout and Payment would meet their intent.
    The Shopping Agent then assembles and approves a closed Checkout and Payment
    Mandate on their behalf using these open Mandates.

Verifiers of Mandates *always* receive a closed Payment and Checkout Mandate,
regardless of the mode. The difference is only in how the verification of the
Mandate is performed.

In the Direct case, the signature on the closed Mandates is validated as coming
from a User directly, using a User Credential or a trust list of Agent
Providers.

In the Autonomous case, the closed Mandates are signed by an Agent key. Trust in
this key is provided by open Mandates that are signed by the User or a trust
list of Agent Providers. Constraints in these Mandates allow the verifier to
verify that the Checkout and Payment match the User's intent. Only constraints
relevant to the closed Mandates are shared with the verifier.

### Direct (Human Present)

When a Shopping Agent has a Checkout JWT for the closed Checkout from the
Merchant, they construct the Checkout and Payment Mandate Content and pass it to
a Trusted Surface for display to the user and signing.

Upon receiving the Checkout and Payment Mandate, the Shopping Agent forwards the
Payment Mandate to the Credential Provider (and possibly the Network) for
Verification. Upon successful verification, the the Shopping Agent receives a
payment credential.

The payment credential and a Checkout Mandate are then provided to the Merchant.
The The Merchant verifies the Checkout with what it created, and initiates
payment with the Merchant Payment Processor if a Merchant-initiated charge.

In the case that the payment method pushes funds to the Merchant, the Merchant
will instead receive confirmation of funds sent, and confirm the receipt of
those funds.

Upon completion, a Checkout Receipt is returned to the Shopping Agent, and the
Payment Receipt is returned to the Shopping Agent, Credential Provider and, if
applicable, the Network.

See [Human Present](flows.md#human-present) for a detailed example.

> Note: Because the User approves the closed Checkout, this can often be
> replaced with a traditional e-commerce journey where the Merchant and the
> Trusted Surface communicate directly.

### Autonomous (Human Not Present)

When a Shopping Agent needs to operate autonomously, it will create open
Checkout and Payment Mandate Content and have these authorized by the Trusted
Surface. These MUST include the agent's public key as a `cnf` claim. This is
required as it is not yet bound to a particular transaction, and so it needs to
be constrained for use by the Agent. It is RECOMMENDED to set the `exp` claim
for these Mandates to the smallest value that will allow the Shopping Agent to
complete the assigned task.

After the Shopping Agent has created an appropriate Checkout, to authorize the
Checkout, the Shopping Agent MAY now sign it using its Agent Key instead of
getting approval on a Trusted Surface. It then MUST provide both the user-signed
open Mandate and the agent-signed closed Mandate to the Verifying Parties, as
described in the Direct case above.

Shopping Agents MUST NOT present any subsequent open Payment or Checkout
Mandates without receiving a rejection receipt from the previous one. This is to
prevent an Agent approving multiple different Checkouts using the same open
Mandate.

To ensure user privacy, Shopping Agents MUST present only the disclosures from
the open Mandates needed in the evaluation of the closed Mandates.

Upon completion, a Checkout Receipt is returned to the Shopping Agent, and the
Payment Receipt is returned to the Shopping Agent, Credential Provider and, if
applicable, the Network.

See [Human Not Present](flows.md#human-not-present) for a detailed example.

> Note: In the current specification, the Shopping Agent needs to determine the
> applicable Mandates and Disclosures ad-hoc based on the Checkout. In the
> future, utilizing an explicit query language in the commerce protocol can help
> practical interoperability.

#### Agent-to-Agent Delegation

Conceptually, it is possible to use this protocol to support delegation of
Mandates from one Shopping Agent to another. This is outside the scope of the
current specification.

## Dispute Evidence

In the case of a dispute, the Checkout Mandate and Receipt, and Payment Mandate
and Receipt can be brought together to provide a non-repudiable picture of the
transaction. Specific details of how this is used for dispute resolution,
retention, and retrieval requirements are outside the scope of this
specification.

The Checkout Mandate and Receipt MAY be able to be provided by the following
roles:

-   Shopping Agent
-   Merchant

The Payment Mandate and Receipt MAY be able to be provided by the following
roles:

-   Shopping Agent
-   Credential Provider
-   Network
-   Merchant Payment Processor

See [Verification: Dispute](#dispute) for the verification rules.

> Note: Providing an automated method to retrieve the Checkout Mandate, from
> either the Shopping Agent or the Merchant, would provide substantial utility
> to the ecosystem. The exact details are outside the scope of the current
> version, but would be done by using the Payment Mandate `transaction_id` as
> the key to request it.

## Verification

The following verification rules MUST be followed by these roles upon receipt of
the Mandate.

> Note: A particular role can always delegate the responsibilities to a
> technology provider. For example, a Merchant could have their payment
> processor perform verifications on their behalf. In such a case, the delegate
> follows the verification rules for that role instead.

### Merchant

The Merchant MUST receive an appropriate Checkout Mandate from a Shopping Agent
before completing the Checkout.

They MUST verify the Checkout Mandate as follows:

-   Process and verify the Checkout Mandate according to
    [Verification and Processing Rules](agent_authorization.md#verification-and-processing-rules).
-   Verify that the hash of the Checkout JWT sent for approval matches the value
    included for the `checkout_hash` claim.
-   If open Checkout Mandates are included, verify that the closed Checkout
    conforms to all of the Constraints by evaluating each Constraint.

If any step fails, the Merchant MUST return a Checkout Receipt JWT containing
the appropriate error message.

### Credential Provider and Network

The Credential Provider and, if applicable, the Network MUST receive an
appropriate Payment Mandate from the Shopping Agent before returning a payment
credential.

They MUST verify the Payment Mandate as follows:

-   Process and verify the Payment Mandate according to
    [Verification and Processing Rules](agent_authorization.md#verification-and-processing-rules).
-   If open Payment Mandates are included, verify that the closed Payment
    Mandate matches all the Constraints.

If any step fails, they MUST return a Payment Receipt JWT containing the
appropriate error to the Shopping Agent.

### Merchant Payment Processor

The Merchant Payment Processor MUST receive an appropriate Payment Credential
from the Merchant before processing the transaction.

Merchant Payment Processor MUST verify the Payment Credential is appropriately
scoped to the Checkout. One way this can be done is by providing the Closed
Payment Mandate inside the Payment Credential.

### Dispute

When performing verification at the time of dispute, the following steps MUST be
followed to ensure the integrity of the Payment and Checkout Mandate and
Receipts.

-   The Checkout Mandate MUST be verified according to the Merchant Verification
    rules.
-   The hash of the `checkout_jwt` MUST be independently computed from the
    included `checkout_jwt`.
-   The Checkout Receipt `reference` MUST match the hash of the closed Checkout
    Mandate. This is calculated in the same manner as the `sd_hash` would be.
-   The Payment Mandate MUST be verified according to the
    [Merchant Payment Processor](#merchant-payment-processor) section using the
    `checkout_hash` from the Checkout Mandate.
-   The Payment Receipt reference MUST match the hash of the closed Payment
    Mandate. This is calculated in the same manner as the `sd_hash` would be.

After all these steps have been performed successfully, then the information
contained in the Checkout Mandate and Payment Mandate is able to be used as
evidence as to what the user, and each role saw.

## Extension Points

AP2 provides several extension points to allow it to adapt to meet the needs of
Agentic Commerce. These are as follows:

### Mandate Constraints

This extension point is designed to support constraining Agent behavior, while
supporting more complex autonomous use cases. To define a new constraint, the
following MUST be specified:

-   A uniquely defined `type`.
-   A Schema, including which fields are selectively disclosable.
-   The evaluation algorithm.

### Checkout Object

AP2 is agnostic to the contents of the merchant-signed Checkout JWT. It is
created to be compatible with logically represented Checkout Objects, but it
does provide an extension point to be adapted to other Checkout Objects. UCP
itself also provides such extension points within the protocol, which is the
RECOMMENDED way to support new commerce journeys.

### Payment Instrument

AP2 is agnostic to the particular payment instrument used. New Payment
Instruments are supported by defining a unique `type` in the Payment Instrument
JSON object. If necessary, additional properties MAY be defined for that
specific `type`.

### Verifiable Digital Credential Formats (VDCs)

AP2 specifies the use of `SD-JWT`s for securing the Payment and Checkout
Mandates. Payment and Checkout Mandates could be cryptographically secured by
other VDCs as mentioned in
[Agent Authorization](agent_authorization.md).
