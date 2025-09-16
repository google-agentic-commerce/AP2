# Life of a Transaction

The Agent Payments Protocol (AP2) defines clear flows for different user
scenarios. The two primary modalities are "Human Present" and "Human Not
Present."

## Human Present Transaction

This journey applies when a user delegates a task to an agent and is available
to authorize the final payment.

The typical flow is as follows:

1. **Setup**: The user may establish a connection between their preferred
   Shopping Agent and a supported Credentials Provider (e.g., their digital
   wallet).
2. **Discovery & Negotiation**: The user gives a shopping task to their agent.
   The agent interacts with one or more merchants to assemble a cart that
   satisfies the request.
3. **Merchant Validates Cart**: The user authorizes a set of items for purchase.
   The merchant signs the final cart, signaling their commitment to fulfill it.
4. **Provide Payment Methods**: The Shopping Agent requests an applicable
   payment method from the Credentials Provider.
5. **Show Cart**: The agent presents the final, merchant-signed cart and the
   selected payment method to the user in a trusted interface.
6. **Sign & Pay**: The user's approval generates a cryptographically signed
   **Cart Mandate**, which contains the explicit details of the purchase. This
   mandate is shared with the merchant as evidence. A separate **Payment
   Mandate** is prepared for the payment network.
7. **Payment Execution**: The payment details are conveyed to the Credentials
   Provider and Merchant to complete the transaction.
8. **Send to Issuer**: The merchant or their processor routes the transaction to
   the payment network and issuer, appending the Payment Mandate to provide
   visibility into the agentic nature of the transaction.
9. **Challenge (If Necessary)**: Any party (issuer, merchant, etc.) can issue a
   challenge (like 3D Secure). The user must complete the challenge on a trusted
   surface.
10. **Authorization**: The issuer approves the payment, and the confirmation is
    sent to the user and merchant so the order can be fulfilled.

## Human Not Present Transaction

This journey is for scenarios where the user wants the agent to proceed with a
payment in their absence (e.g., "buy these shoes when the price drops below
$100").

The key differences from the Human Present flow are:

1. **Intent is Captured**: Instead of approving a final cart, the user approves
   the agent's _understanding_ of their intent. The user's in-session
   authentication (e.g., biometric) creates a signed **Intent Mandate**.
2. **Intent Mandate is Used**: This mandate, which includes the natural language
   description of the user's goal, is shared with the merchant, who can then
   decide if they can fulfill the request.
3. **Merchant Can Force User Confirmation**: If the merchant is unsure about
   their ability to fulfill the request based on the Intent Mandate, they can
   require the user to return to the session to confirm details. This might
   involve the user selecting from a set of final options (creating a Cart
   Mandate) or providing more information (updating the Intent Mandate).

This ensures merchants have confidence in the user's intent while still allowing
for autonomous execution of tasks.
