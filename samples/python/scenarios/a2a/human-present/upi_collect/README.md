# Agent Payments Protocol Sample: Human Present Purchases with UPI COLLECT

This sample demonstrates the A2A ap2-extension for a human present transaction
using UPI COLLECT as the payment method.

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

- **Shopping Agent:** The main orchestrator that handles user's requests to shop
  and delegates tasks to specialized agents.
- **Merchant Agent:** An agent that handles product queries from the shopping
  agent.
- **Merchant Payment Processor Agent:** An agent that takes payments on behalf
  of the merchant.
- **Credentials Provider Agent:** The credentials provider is the holder of a
  user's payment credentials. As such, it serves two primary roles:
    - It provides the shopping agent the list of payment methods available in a
        user's wallet.
    - It facilitates payment between the shopping agent and a merchant's payment
        processor.
- **Mock Bank Server:** A simulated bank backend that handles UPI payment
  approvals and provides a web interface for users to approve/decline
  transactions.

## Key Features

### 1. UPI COLLECT purchase

- The merchant agent will advertise support for UPI COLLECT purchases through
  its agent card and through the CartMandate once shopping is complete.
- The preferred payment method in the user's wallet will be a UPI account (e.g.,
  `bugsbunny@upi`).

### 2. MCA Challenge (Multi-Channel Authentication)

- Unlike card payments that use OTP challenges, UPI payments use MCA where the
  user approves the transaction in their PSP app.
- In this demo, the mock bank server provides a web UI to simulate the PSP app
  approval flow.

### 3. Asynchronous Payment with Status Polling

- UPI payments are asynchronous - the payment processor initiates the payment
  and then polls the bank for status updates.
- The Shopping Agent automatically retries payment sync if it is not in terminal
  state.
- Here, The Shopping Agent is configured to do payment sync every 5 seconds (up
  to 6 times max) until the transaction is approved or declined.

## Executing the Example

### Setup

Ensure you have obtained a Google API key from
[Google AI Studio](https://aistudio.google.com/apikey). Then declare the
GOOGLE_API_KEY variable in one of two ways.

- Option 1: Declare it as an environment variable:
  `export GOOGLE_API_KEY=your_key`
- Option 2: Put it into an .env file at the root of your repository.
  `echo "GOOGLE_API_KEY=your_key" > .env`

### Execution

You can execute the following command to run all of the steps in one terminal:

```sh
bash samples/python/scenarios/a2a/human-present/upi_collect/run.sh
```

Or you can run each server in its own terminal:

1. Start the Mock Bank Server:

   ```sh
   uv run --package ap2-samples python -m mock_bank
   ```

2. Start the Merchant Agent:

   ```sh
   export PAYMENT_METHOD=UPI_COLLECT
   uv run --package ap2-samples python -m roles.merchant_agent
   ```

3. Start the Credentials Provider:

   ```sh
   export PAYMENT_METHOD=UPI_COLLECT
   uv run --package ap2-samples python -m roles.credentials_provider_agent
   ```

4. Start the Merchant Payment Processor Agent:

   ```sh
   export PAYMENT_METHOD=UPI_COLLECT
   uv run --package ap2-samples python -m roles.merchant_payment_processor_agent
   ```

5. Start the Shopping Agent:

   ```sh
   export PAYMENT_METHOD=UPI_COLLECT
   uv run --package ap2-samples adk web samples/python/src/roles
   ```

Open a browser and navigate to the shopping agent UI at <http://0.0.0.0:8000>. You
may now begin interacting with the Shopping Agent.

### Interacting with the Shopping Agent

This section walks you through a typical interaction with the sample.

1. **Launching Agent Development Kit UI**: Open a browser on your computer and
   navigate to 0.0.0.0:8000/dev-ui. Select `shopping_agent` from the
   `Select an agent` drop down in the upper left hand corner.
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
   Provider Agent. You will select a UPI payment method (e.g., "Bugs's BHIM UPI
   account").
1. **PaymentMandate creation**: The Shopping Agent will package the cart and
   transaction information in a PaymentMandate and ask you to sign the mandate.
   It will initiate payment using the PaymentMandate.
1. **MCA Challenge**: The Merchant Payment Processor will create a transaction
   in the mock bank and display a message asking you to approve the payment in
   your PSP app. In this demo, you'll approve it via the mock bank web UI.
1. **Approve Payment in Mock Bank**:
   - Open <http://localhost:8004> in a new browser tab
   - You'll see the pending UPI transaction
   - Click the **APPROVE** button to authorize the payment
   - (Alternatively, click **DECLINE** to reject it)
1. **Automatic Payment Sync**: The Shopping Agent will automatically poll the
   mock bank every 5 seconds to check the payment status. Once you approve the
   payment, the next sync will detect the success.
1. **Purchase Complete**: Once the payment is approved, you'll receive a
   confirmation message and a digital receipt.

## Mock Bank Integration

The mock bank server simulates a real bank backend for UPI payments. It
provides:

- **Transaction Management**: Stores payment transactions with PENDING status
- **Web UI**: A browser-based interface to approve/decline transactions
- **REST API**: Endpoints for creating transactions and checking status
- **Status Polling**: The payment processor polls the bank for status updates

### Accessing the Mock Bank UI

1. Open <http://localhost:8004> in your browser
1. You'll see all pending transactions grouped by payment method
1. For UPI transactions, you'll see:
   - Transaction Id
   - Transaction amount
   - Description
   - Timestamp
   - **APPROVE** and **DECLINE** buttons

### Payment Status Flow

```text
1. Payment Processor → Creates transaction in Mock Bank (PENDING)
2. Mock Bank → Returns transaction ID
3. Payment Processor → Displays MCA challenge to user
4. User → Approves payment in Mock Bank UI
5. Mock Bank → Updates status to SUCCESS
6. Payment Processor → Polls bank, detects SUCCESS
7. Payment Processor → Completes payment and sends receipt
```

## Advanced Engagements with the samples

### Enabling Verbose Engagement with the Shopping Agent

If you want to understand what the agents are doing internally or inspect the
mandate objects they create and share, you can ask the Shopping Agent to run in
**verbose mode**.

Enabling verbose mode will instruct the Shopping Agent, and any agents it
delegates to, to provide detailed explanations of their process, including:

- A description of their current and next steps.
- The JSON representation of all data payloads (such as `IntentMandates`,
  `CartMandates`, or `PaymentMandates`) being created, sent, or received.

#### How to Activate Verbose Mode

To activate this mode, simply include the keyword verbose in your initial prompt
to the Shopping Agent. Example prompt:

_"I'm looking to buy a new pair of shoes. Could you be verbose as we do this,
explaining what you're doing, and display all data payloads?"_

> **💡 TIP: Give elaborate instructions**
> While the word **verbose** is usually sufficient, providing more elaborate
> instruction in your prompt tends to result in more detailed and helpful
> explanations from the agent.
<!-- -->
> **💡 TIP: If the JSON is missing...**
> If the agent is in verbose mode but fails to display the JSON mandate, a quick
> follow-up prompt is often needed. Just say: **"Remember we're in verbose mode,
> please display the JSON."** After this reminder, the agent usually becomes
> more reliable at displaying all data payloads.

### Viewing Agent Communication

To help engineers visualize the exact communication occurring between the agent
servers, a detailed log file is created automatically when the servers start up.

By default, this log file is named `watch.log` and is located in the `.logs`
directory.

#### Log Contents

The watch log is a comprehensive trace that includes three main categories of
data:

| Category              | Details Included                                                                                                                                |
| :-------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------- |
| **Raw HTTP Data**     | The **HTTP method** (e.g., `POST`) and **URL** for each request, the **JSON request body**, and the **JSON response body**.                     |
| **A2A Message Data**  | Any **request instructions** extracted from the Agent-to-Agent (A2A) Message's `TextPart`, and any data found within the Message's `DataParts`. |
| **AP2 Protocol Data** | Any **Mandate objects** (`IntentMandate`, `CartMandate`, `PaymentMandate`) that are identified within a Message's `DataParts`.                  |

## Key Differences from Card Payments

| Feature            | Card Payment                  | UPI COLLECT                         |
| :----------------- | :---------------------------- | :---------------------------------- |
| **Challenge Type** | OTP (user enters code)        | MCA (user approves in PSP app)      |
| **User Action**    | Enter verification code "123" | Approve in mock bank web UI         |
| **Payment Flow**   | Synchronous                   | Asynchronous with status polling    |
| **Extra Service**  | None                          | Mock Bank Server (port 8004)        |
| **Completion**     | Immediate after OTP           | Polls bank every 5s (max 6 retries) |

## Troubleshooting

**Issue**: Payment stays in "pending" state

- **Solution**: Make sure the mock bank server is running on port 8004
- **Solution**: Check that you approved the payment in the mock bank UI
- **Solution**: Wait for the automatic sync (happens every 5 seconds)

**Issue**: Mock bank UI shows no transactions

- **Solution**: Ensure you've reached the payment step in the shopping flow
- **Solution**: Check mock bank logs: `cat .logs/mock_bank.log`

**Issue**: Payment sync fails

- **Solution**: Verify `PAYMENT_METHOD=UPI_COLLECT` is set for all agents
- **Solution**: Check that the transaction ID matches between agents and bank
