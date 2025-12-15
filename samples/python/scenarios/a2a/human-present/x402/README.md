# Agent Payments Protocol Sample: Human Present Purchases with x402

This sample demonstrates the A2A ap2-extension for a human present transaction
using payment methods compatible with the x402 as the payment method.

**Note:** The AP2 compatible x402 extension is coming soon. The current x402
extension will be enhanced to ensure the creation of all key mandates outlined
in AP2. See the current x402 A2A extension repository
[x402 A2A extension repository](https://github.com/google-agentic-commerce/a2a-x402/).

## Scenario

Human-Present flows refer to all commerce flows where the user is present to
confirm the details of what is being purchased, and what payment method is to be
used. The user attesting to the details of the purchase allows all parties to
have high confidence of the transaction.

The IntentMandate is still leveraged to share the appropriate information with
Merchant Agents. This is to maintain consistency across Human-Present and
Human-Not-Present flows.

All Human-Present purchases will have a user-signed PaymentMandate authorizing
the purchase.

## Key Actors

This sample consists of:

* **Shopping Agent:** The main orchestrator that handles user's requests to
    shop and delegates tasks to specialized agents.
* **Merchant Agent:** An agent that handles product queries from the shopping
    agent.
* **Merchant Payment Processor Agent:** An agent that takes payments on behalf
    of the merchant.
* **Credentials Provider Agent:** The credentials provider is the holder of a
    user's payment credentials. As such, it serves two primary roles:
    * It provides the shopping agent the list of payment methods available in
        a user's wallet.
    * It facilitates payment between the shopping agent and a merchant's
        payment processor.

## Key Features

### 1. x402 purchase

* The Merchant Agent will advertise support for x402 purchases through its
    agent card and through the CartMandate once shopping is complete.
* The preferred payment method in the user's wallet will be an x402 compatible
    payment method.

## Executing the Example

### Setup

Ensure you have obtained a Google API key from
[Google AI Studio](https://aistudio.google.com/apikey). Then declare the
GOOGLE_API_KEY variable in one of two ways.

* Option 1: Declare it as an environment variable: `export
    GOOGLE_API_KEY=your_key`
* Option 2: Put it into an .env file at the root of your repository. `echo
    "GOOGLE_API_KEY=your_key" > .env`

### Execution

You can execute the following command to run all of the steps in one terminal:

```sh
samples/python/scenarios/a2a/human-present/cards/run.sh --payment-method x402
```

Or you can run each server in its own terminal (ensure `PAYMENT_METHOD=x402` is set for all processes):

1. Start the Merchant Agent:

    ```sh
    export PAYMENT_METHOD=x402
    uv run --package ap2-samples python -m roles.merchant_agent
    ```

2. Start the Credentials Provider:

    ```sh
    export PAYMENT_METHOD=x402
    uv run --package ap2-samples python -m roles.credentials_provider_agent
    ```

3. Start the Merchant Payment Processor Agent:

    ```sh
    export PAYMENT_METHOD=x402
    uv run --package ap2-samples python -m roles.merchant_payment_processor_agent
    ```

4. Start the Shopping Agent:

    ```sh
    export PAYMENT_METHOD=x402
    uv run --package ap2-samples adk web samples/python/src/roles
    ```

Open a browser and navigate to the shopping agent UI at [http://0.0.0.0:8000](http://0.0.0.0:8000). You
may now begin interacting with the Shopping Agent.

### Interacting with the Shopping Agent

This section walks you through a typical interaction with the sample.

1. **Launching Agent Development Kit UI**: Open a browser on your computer and
    navigate to 0.0.0.0:8000/dev-ui. Select `shopping_agent` from the `Select an
    agent` drop down in the upper left hand corner.
1. **Initial Request**: In the Shopping Agent's terminal, you'll be prompted to
    start a conversation. You can type something like: "I want to buy a coffee
    maker."
1. **Product Search**: The Shopping Agent will delegate to the Merchant Agent,
    which will find products matching your intent and present you with options
    contained in CartMandates.
1. **Cart Creation**: The Merchant Agent will create one or more `CartMandate`s
    and share it with the Shopping Agent. Each CartMandate is signed by the
    Merchant, ensuring the offer to the user is accurate.
1. **Product Selection** The Shopping Agent will present the user with the set
    of products to choose from.
1. **Link Credential Provider**: The Shopping Agent will prompt you to link
    your preferred Credential Provider in order to access you available payment
    methods.
1. **Payment Method Selection**: After you select a cart, the Shopping Agent
    will show you a list of available payment methods from the Credentials
    Provider Agent. You will select a payment method.
1. **PaymentMandate creation**: The Shopping Agent will package the cart and
    transaction information in a PaymentMandate and ask you to sign the
    mandate. It will initiate payment using the PaymentMandate.
1. **Purchase Complete**: The payment will be processed (OTP challenge is skipped for x402 demo), and you'll receive a confirmation message and a digital receipt.
