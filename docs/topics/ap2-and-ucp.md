# UCP Translates AP2 Requirements into Reality

UCP is fully compatible with Agent Payments Protocol (AP2) via its
[**AP2 Mandates Extension**](https://ucp.dev/specification/ap2-mandates/). When
this extension is enabled, it captures strong cryptographic evidence of the
user’s consent to purchase.

This article aims to help bridge the gap between UCP and AP2 terminology, to
help readers of both protocols understand exactly how UCP is fully
AP2-compliant.

## The Checkout Object: UCP’s Implementation of the AP2 CartMandate

At the center of every UCP checkout session is the
[**Checkout Object**](https://ucp.dev/specification/ap2-mandates/#step-1-checkout-creation-signing),
which serves as the functional equivalent of the **AP2 CartMandate**. Both
structures exist to formalize the merchant’s offer to the user.

Aligning fully with the AP2 protocol, the UCP Checkout object encapsulates:

*   A clear list of the items being purchased.
*   A total price breakdown, including tax and shipping.
*   The merchant’s cryptographic signature ensuring the merchant’s offer remains
    non-repudiable.

## Proof of User Authorization: From Checkout to Payment Mandate

To finalize a purchase, AP2 requires verifiable proof of user authorization for
both the purchase and the payment method. UCP implements this by generating and
signing two distinct cryptographic objects during the checkout flow:

1.  **The CheckoutMandate:** This represents the user's signed authorization of
    the Checkout object. It provides the merchant with non-repudiable proof of
    what the user agreed to buy.
2.  **The PaymentMandate:** This captures the user's authorization of a specific
    Payment Credential. It serves as proof for the payment network, issuer, and
    credential vault that the user has sanctioned the use of their credentials
    for this specific transaction.

Both mandates are provided to the merchant via UCP’s
[`/complete_checkout`](https://ucp.dev/specification/checkout/#complete-checkout)
API, with the expectation that the **PaymentMandate** is passed along by the
merchant to their PSP.
