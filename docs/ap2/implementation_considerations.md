# Implementation Considerations

## Roles

Below describes what each role needs to care about and examples of how
this role might be implemented in the payment ecosystem.

### Merchant

The Merchant needs to implement the following:

  - Provide a Catalog and Checkout endpoints to the Shopping Agent to allow it
    to perform a commerce protocol, for example as described by the 
    [Universal Commerce Protocol](https://ucp.dev/).
  - Generate a signed Checkout JWT. 
  - Verify the [Checkout Mandate](checkout_mandate.md)
    - Or delegate this to a technology provider (such as the MPP).
  - Complete the Checkout with the Merchant Payment Processor using the Checkout
    Mandate hash and `payment_token` (scoped to the Payment Mandate).
    - Or implement this MPP role themselves.
  - Generate a signed [Checkout Receipt](checkout_mandate.md#checkout-receipt)
    with appropriate status and return it to the Shopping Agent.

Some examples of how the Merchant role could be structured:

  - Merchant with UCP endpoints.
  - A Merchant Agent that communicates over agent-to-agent (a2a) with the Shopping Agent, and
    then to the Merchant backend via UCP.
  - Combined Merchant and Merchant Payment Processor. 
  - A Merchant with delegated Checkout Mandate verification. 
    - Here the Merchant would provide the Checkout Mandate to a technology
      provider for verification, and proceed if verification passes.

### Merchant Payment Processor

The Merchant Payment Processor needs to implement the following:

  - Receive the payment token from the Merchant
  - Verify the [Payment Mandate](payment_mandate.md) in the payment token.
  - Generate a signed [Payment Receipt](payment_mandate.md#payment-receipt),
    which is made available to the Shopping Agent, Credential Provider and Network.
  - Process or verify payment

### Shopping Agent

The Shopping Agent needs to implement the following: 

  - Agentic Shopping to determine user intent.
  - Selecting a payment instrument from a Credential Provider.
  - Creation of Checkout and Payment Mandate Content.
  - Obtaining signed Checkout and Payment Mandates via a Trusted Surface.
  - Present the [Payment Mandate](payment_mandate.md) to the Credential
    Provider to get the payment token. This involves:
    - Selecting the appropriate Mandate from storage.
    - Key-binding with an Agent key (as needed).
    - Data minimization through Selective Disclosure.
    - Preventing double spend and handling receipt management. 
  - Presenting the [Checkout Mandate](checkout_mandate.md) to the Merchant as part of
    completing the Checkout. This involves:
    - Selecting the appropriate Mandate from storage.
    - Key-binding with an Agent key (as needed).
    - Data minimization through Selective Disclosure.
    - Preventing double spend and handling receipt management.
  - Receiving Receipts and handling success and error.

### Credential Provider

The Credential Provider needs to implement the following:

  - Providing payment instruments to the Shopping Agent.
  - Verify the [Payment Mandate](payment_mandate.md).
  - Obtaining the payment token from the network using the Payment Mandate, or initiate sending of funds to the merchant.
  - Releasing the payment token or funding reference number.
  - Receiving and storing the
    [Payment Receipt](payment_mandate.md#payment-receipt).

Examples of how the Credential Provider role can be implemented: 

  - A user's digital Wallet, or payment network that the Shopping Agent links with.
  - A store of payment instruments provided by the Shopping Agent directly.
  - A store of Payment instruments provided by the Merchant.

### Trusted Surface

The Trusted Surface represents UI that is trusted by all parties to obtain
authorization and consent from the end user. It is responsible for: 

  - Displaying Checkout and Payment Mandate Content to the User.
  - Obtaining user authorization and consent. 
  - Creating signed Checkout and Payment Mandates and delegating them to the
    Shopping Agent. 

This role can be played by a lot of different entities. Some examples include:

  - A deterministic part of the Shopping Agent application.
  - A standalone User Wallet, or Issuer application.
  - Trusted User Agents (such as mobile Platforms or Browsers).

## Agent Identification

AP2 is designed to constrain Agent behaviors without them having to be inherently
trustworthy. As part of implementing a Commerce Protocol, Merchants or Trusted
Surfaces MAY wish to only work with trusted Agents. These details are left to
the Commerce Protocol layer.

## Hashes

When calculating hashes it is important that the same representation is used.
This is typically achieved by providing the base64url encoded representation of
JSON structures. For dispute resolution this will mean storing the SD-JWTs,
along with their disclosures, for the Mandates in their compact serialization.
This is to allow easy computation of the `sd_hash`, `checkout_hash`, and Receipt
`reference`.

For consistency, the same hashing algorithm is required for both the SD-JWT
digests and `checkout_hash`.

## Agent Key

One important portion of the Autonomous flows is the Agent's key. This is used
to transaction-bind the open Mandates and prevent their re-use. It is also used
to prevent double spend by preventing the release of overlapping closed Mandates.

One way to implement this is through tool calling, where deterministic code
verifies the closed Mandate being created before being signed. This
responsibility could also be delegated by the Shopping Agent to a technology
provider.

## Mandate Management

As Mandates are long-lived, the Shopping Agent SHOULD provide a mechanism to
manage active Mandates (along with the tasks they are being used in).
Limiting the duration of active Mandates, and providing
notifications to the User, even when executing autonomously, is important to
keep the User in control of their Shopping Agent.

In the case of external Trusted Surfaces it could make sense
to allow for management of delegated Mandates but that is outside the scope of
this specification.
