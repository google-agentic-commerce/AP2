import { ai, z } from "./genkit.js";
import { A2AClient } from "@a2a-js/sdk/client";
import { SUBAGENTS } from "./subagents/index.js";
import type {
  Artifact,
  DataPart,
  MessageSendParams,
  SendMessageSuccessResponse,
  Task,
  TextPart,
} from "@a2a-js/sdk";
import { v4 as uuidv4 } from "uuid";
import { AGENTS } from "../index.js";
import { shippingAddressSchema } from "../../schemas/shipping-address.js";
import type { CartMandate } from "../../types/cart-mandate.js";
import type { PaymentMandate } from "../../types/payment-mandate.js";
import { getState, setState, type State } from "../../store/state.js";
import { DATA_KEYS } from "../../constants/index.js";

export const sendMessageToSubagent = ai.defineTool(
  {
    name: "sendMessageToSubagent",
    description:
      "Send an A2A message to a subagent. Use this to delegate tasks to specialized subagents. If the subagent is still working (not completed), you must continue the conversation with that same subagent until it completes.",
    inputSchema: z.object({
      subagentName: z.enum(Object.keys(SUBAGENTS) as [string, ...string[]]),
      message: z.string(),
    }),
  },
  async (input) => {
    const { subagentName, message: messageText } = input;

    if (!SUBAGENTS[subagentName]) {
      throw new Error(`Subagent ${subagentName} not found`);
    }

    const client = await A2AClient.fromCardUrl(SUBAGENTS[subagentName]);

    const existingSubagentTaskId = getState().subagentTaskIds?.[subagentName];
    const sendParams: MessageSendParams = {
      message: {
        messageId: uuidv4(),
        role: "user",
        taskId: existingSubagentTaskId,
        parts: [{ kind: "text", text: messageText }],
        kind: "message",
      },
    };

    if (subagentName === "PAYMENT_METHOD_COLLECTOR") {
      if (getState().cartMandate) {
        const cart = getState().cartMandate.contents;
        const details = cart.paymentRequest.details;
        const address = getState().shippingAddress;

        const cartSummary = `${messageText}
          Here is the complete CartMandate information for your reference:

          Merchant: ${cart.merchantName}
          Cart ID: ${cart.id}
          Items:
          ${details.displayItems
            ?.map((item) => `  - ${item.label}: $${item.amount.value}`)
            .join("\n")}
          Total: $${details.total.amount.value}
          Cart Expires: ${cart.cartExpiry}
          Refund Period: ${details.displayItems?.[0]?.refundPeriod || "N/A"} days

          Shipping Address:
            ${address?.recipient || "N/A"}
            ${address?.address_line?.join(", ") || ""}
            ${address?.city}, ${address?.region} ${address?.postal_code}
            ${address?.country}
            Phone: ${address?.phone_number}

          IMPORTANT: Use the email address ${
            getState().userEmail || "bugsbunny@gmail.com"
          } when calling the get_payment_methods tool. This is the user's verified email address for payment credentials.

          The CartMandate object is also available in data parts for the get_payment_methods tool.`;

        sendParams.message.parts[0] = {
          kind: "text",
          text: cartSummary,
        };

        sendParams.message.parts.push({
          kind: "data",
          data: { cartMandate: getState().cartMandate },
        });
      }
      if (getState().shoppingContextId) {
        sendParams.message.parts.push({
          kind: "data",
          data: { shoppingContextId: getState().shoppingContextId },
        });
      }
      if (getState().shippingAddress) {
        sendParams.message.parts.push({
          kind: "data",
          data: { shippingAddress: getState().shippingAddress },
        });
      }
    }

    const stream = client.sendMessageStream(sendParams);
    let result: Task | undefined;
    let hasMessage = false;

    for await (const event of stream) {
      if (event.kind === "task") {
        result = event;
        hasMessage = !!event.status?.message;
      } else if (event.kind === "artifact-update") {
        if (!result) {
          result = {
            kind: "task",
            id: event.taskId,
            contextId: event.contextId,
            status: { state: "working", timestamp: new Date().toISOString() },
            history: [],
            artifacts: [event.artifact],
          };
        } else {
          if (!result.artifacts) {
            result.artifacts = [];
          }
          result.artifacts.push(event.artifact);
        }
      } else if (event.kind === "status-update") {
        if (!result) {
          result = {
            kind: "task",
            id: event.taskId,
            contextId: event.contextId,
            status: event.status,
            history: [],
            artifacts: [],
          };
        } else {
          result.status = event.status;
        }

        hasMessage = !!event.status?.message;

        if (hasMessage && event.status.message) {
          const messageText =
            event.status.message.parts?.[0]?.kind === "text"
              ? (event.status.message.parts[0] as TextPart).text
              : "";

          // List of generic "working" status messages to skip
          const workingStatusMessages = [
            "Searching for products that match your needs...",
            "Setting up your delivery details...",
            "Retrieving your available payment methods...",
            "Your personal shopping assistant is working on your request...",
            "The merchant is processing your request...",
          ];
          const isWorkingStatusMessage = workingStatusMessages.some((msg) =>
            messageText.includes(msg)
          );

          if (messageText && !isWorkingStatusMessage) {
            break;
          }
        }
      }
    }

    if (!result) {
      throw new Error("No response received from subagent");
    }

    if (result.kind === "task") {
      const currentTaskIds = getState().subagentTaskIds || {};
      setState({
        subagentTaskIds: { ...currentTaskIds, [subagentName]: result.id },
      });
    }

    const terminalStates = ["completed", "failed", "canceled", "rejected"];
    if (
      result.kind === "task" &&
      terminalStates.includes(result.status.state)
    ) {
      if (result.status.state === "completed") {
        if (subagentName === "SHOPPER" && result.artifacts) {
          for (const artifact of result.artifacts) {
            for (const part of artifact.parts) {
              if (part.kind === "data") {
                const data = (part as DataPart).data as Record<string, unknown>;
                const updates: Partial<State> = {};
                if (data.chosenCartId)
                  updates.chosenCartId = data.chosenCartId as string;
                if (data.cartMandate)
                  updates.cartMandate = data.cartMandate as CartMandate;
                if (data.riskData) updates.riskData = data.riskData as string;
                if (data.shoppingContextId)
                  updates.shoppingContextId = data.shoppingContextId as string;
                if (Object.keys(updates).length > 0) setState(updates);
              }
            }
          }
        }

        if (subagentName === "SHIPPING_ADDRESS_COLLECTOR" && result.artifacts) {
          for (const artifact of result.artifacts) {
            for (const part of artifact.parts) {
              if (part.kind === "data") {
                const data = (part as DataPart).data as Record<string, unknown>;
                const updates: Partial<State> = {};
                if (data.shippingAddress)
                  updates.shippingAddress =
                    data.shippingAddress as State["shippingAddress"];
                if (data.userEmail)
                  updates.userEmail = data.userEmail as string;
                if (data.address_line || data.recipient)
                  updates.shippingAddress = data as State["shippingAddress"];
                if (Object.keys(updates).length > 0) setState(updates);
              }
            }
          }
        }

        if (subagentName === "PAYMENT_METHOD_COLLECTOR" && result.artifacts) {
          for (const artifact of result.artifacts) {
            for (const part of artifact.parts) {
              if (part.kind === "data") {
                const data = (part as DataPart).data as Record<string, unknown>;
                if (data.paymentCredentialToken) {
                  setState({
                    paymentCredentialToken:
                      data.paymentCredentialToken as string,
                  });
                }
              }
            }
          }
        }
      }

      if (getState().subagentTaskIds) {
        delete getState().subagentTaskIds[subagentName];
      }
    }

    if (result.kind === "task" && result.status.message) {
      const message = result.status.message;
      if (message.parts?.length > 0 && message.parts[0].kind === "text") {
        const textPart = message.parts[0] as TextPart;

        if (result.status.state === "completed") {
          return `${subagentName} completed successfully with message: ${textPart.text}`;
        } else if (result.status.state === "working") {
          return `${subagentName} is asking: ${textPart.text}\n\nIMPORTANT: The ${subagentName} subagent is still working on this task. You must relay this message to the user, get their response, and then send it back to the ${subagentName} subagent using sendMessageToSubagent again. Do NOT move to the next step until ${subagentName} returns a completion message.`;
        } else {
          return `${subagentName} returned status ${result.status.state}: ${textPart.text}`;
        }
      }
    }

    return JSON.stringify(result);
  }
);

export const updateCart = ai.defineTool(
  {
    name: "updateCart",
    description:
      "Notifies the merchant agent of a shipping address selection for a cart.",
    inputSchema: z.object({
      shippingAddress: shippingAddressSchema,
    }),
  },
  async (input) => {
    const { shippingAddress } = input;

    const chosenCartId = getState().chosenCartId;
    if (!chosenCartId) {
      throw new Error("No chosen cart mandate found in tool context state.");
    }

    const riskData = getState().riskData;
    if (!riskData) {
      throw new Error("No risk data found in tool context state.");
    }

    const sendParams: MessageSendParams = {
      message: {
        messageId: uuidv4(),
        role: "user",
        contextId: getState().shoppingContextId,
        parts: [
          {
            kind: "text",
            text: "Update the cart with the user's shipping address.",
          },
          {
            kind: "data",
            data: { cartId: chosenCartId },
          },
          {
            kind: "data",
            data: { shippingAddress },
          },
          {
            kind: "data",
            data: { riskData },
          },
          {
            kind: "data",
            data: { shoppingAgentId: "trusted_shopping_agent" },
          },
          {
            kind: "data",
            data: { debugMode: false },
          },
        ],
        kind: "message",
      },
    };
    const client = await A2AClient.fromCardUrl(AGENTS.MERCHANT_AGENT);
    const response = await client.sendMessage(sendParams);

    if ("error" in response) {
      console.error("Error:", response.error.message);
    } else {
      const result = (response as SendMessageSuccessResponse).result;
      if (result.kind === "task") {
        if (result.status.state !== "completed") {
          throw new Error(`Failed to update cart: ${result.status}`);
        }
        const cartMandate = parseCartMandates(result.artifacts)?.[0];

        setState({ cartMandate, shippingAddress });

        return cartMandate;
      }
    }
  }
);

const parseCartMandates = (artifacts: Artifact[]) => {
  const CART_MANDATE_DATA_KEY = "ap2.mandates.CartMandate";
  const cartMandates: CartMandate[] = [];

  for (const artifact of artifacts) {
    for (const part of artifact.parts) {
      if (part.kind === "data") {
        const dataPart = part as DataPart;
        const data = dataPart.data as Record<string, unknown>;
        if (CART_MANDATE_DATA_KEY in data) {
          cartMandates.push(data[CART_MANDATE_DATA_KEY] as CartMandate);
        }
      }
    }
  }

  return cartMandates;
};

export const createPaymentMandate = ai.defineTool(
  {
    name: "createPaymentMandate",
    description: "Creates a payment mandate and stores it in state",
    inputSchema: z.object({
      paymentMethodAlias: z.string(),
      userEmail: z.string(),
    }),
  },
  async (input) => {
    const { userEmail } = input;

    const cartMandate = getState().cartMandate;
    if (!cartMandate)
      throw new Error("No cart mandate found in tool context state.");

    const shippingAddress = getState().shippingAddress;
    if (!shippingAddress)
      throw new Error("No shipping address found in tool context state.");

    const paymentCredentialToken = getState().paymentCredentialToken;
    if (!paymentCredentialToken)
      throw new Error(
        "No payment credential token found in tool context state."
      );

    const paymentRequest = cartMandate.contents.paymentRequest;

    const paymentResponse = {
      requestId: paymentRequest.details.id,
      methodName: "CARD",
      details: {
        token: paymentCredentialToken,
      },
      shippingAddress,
      payerEmail: userEmail,
    };

    const paymentMandate = {
      paymentMandateContents: {
        paymentMandateId: uuidv4(),
        paymentDetailsId: paymentRequest.details.id,
        paymentDetailsTotal: {
          label: paymentRequest.details.total.label,
          amount: paymentRequest.details.total.amount,
          pending: paymentRequest.details.total.pending,
          refundPeriod: paymentRequest.details.total.refundPeriod,
        },
        paymentResponse: {
          requestId: paymentResponse.requestId,
          methodName: paymentResponse.methodName,
          details: paymentResponse.details,
          shippingAddress,
          payerEmail: paymentResponse.payerEmail,
        },
        merchantAgent: cartMandate.contents.merchantName,
        timestamp: new Date().toISOString(),
      },
    };

    setState({ paymentMandate });

    return paymentMandate;
  }
);

export const signMandatesOnUserDevice = ai.defineTool(
  {
    name: "signMandatesOnUserDevice",
    description: `
    Simulates signing the transaction details on a user's secure device.

    This function represents the step where the final transaction details,
    including hashes of the cart and payment mandates, would be sent to a
    secure hardware element on the user's device (e.g., Secure Enclave) to be
    cryptographically signed with the user's private key.

    Note: This is a placeholder implementation. It does not perform any actual
    cryptographic operations. It simulates the creation of a signature by
    concatenating the mandate hashes.
  `,
  },
  async () => {
    const paymentMandate = getState().paymentMandate;
    if (!paymentMandate) {
      throw new Error("No payment mandate found in tool context state.");
    }

    const cartMandate = getState().cartMandate;
    if (!cartMandate) {
      throw new Error("No cart mandate found in tool context state.");
    }

    const paymentMandateHash = generatePaymentMandateHash(paymentMandate);
    const cartMandateHash = generateCartMandateHash(cartMandate);

    paymentMandate.userAuthorization = `${cartMandateHash}_${paymentMandateHash}`;

    setState({ signedPaymentMandate: paymentMandate });

    return paymentMandate.userAuthorization;
  }
);

export const sendSignedPaymentMandateToCredentialsProvider = ai.defineTool(
  {
    name: "sendSignedPaymentMandateToCredentialsProvider",
    description:
      "Sends the signed payment mandate to the credentials provider.",
    inputSchema: z.object({
      debugMode: z.boolean().optional().default(false),
    }),
  },
  async (input) => {
    const { debugMode } = input;

    const paymentMandate = getState().signedPaymentMandate;
    if (!paymentMandate) {
      throw new Error("No signed payment mandate found in tool context state.");
    }

    const riskData = getState().riskData;
    if (!riskData) {
      throw new Error("No risk data found in tool context state.");
    }

    const sendParams: MessageSendParams = {
      message: {
        messageId: uuidv4(),
        role: "user",
        contextId: getState().shoppingContextId,
        parts: [
          {
            kind: "text",
            text: "Please process and validate this signed payment mandate, then confirm receipt.",
          },
          {
            kind: "data",
            data: {
              [DATA_KEYS.PAYMENT_MANDATE]: paymentMandate,
            },
          },
          {
            kind: "data",
            data: { risk_data: riskData },
          },
          {
            kind: "data",
            data: {
              debug_mode: debugMode,
            },
          },
        ],
        kind: "message",
      },
    };

    const client = await A2AClient.fromCardUrl(AGENTS.CREDENTIALS_PROVIDER);
    const response = await client.sendMessage(sendParams);

    if ("error" in response) {
      console.error("Error:", response.error.message);
      throw new Error(response.error.message);
    }

    return response;
  }
);

export const initiatePayment = ai.defineTool(
  {
    name: "initiatePayment",
    description: `
    Initiates a payment using the payment mandate from state.`,
    inputSchema: z.object({
      debugMode: z.boolean().optional().default(false),
    }),
  },
  async (input) => {
    const { debugMode } = input;

    const signedPaymentMandate = getState().signedPaymentMandate;
    if (!signedPaymentMandate) {
      throw new Error("No signed payment mandate found in tool context state.");
    }

    const riskData = getState().riskData;
    if (!riskData) {
      throw new Error("No risk data found in tool context state.");
    }

    const sendParams: MessageSendParams = {
      message: {
        messageId: uuidv4(),
        role: "user",
        contextId: getState().shoppingContextId,
        parts: [
          {
            kind: "text",
            text: "Initiate a payment",
          },
          {
            kind: "data",
            data: {
              [DATA_KEYS.PAYMENT_MANDATE]: signedPaymentMandate,
            },
          },
          {
            kind: "data",
            data: { risk_data: riskData },
          },
          {
            kind: "data",
            data: {
              shopping_agent_id: "trusted_shopping_agent",
            },
          },
          {
            kind: "data",
            data: {
              debug_mode: debugMode,
            },
          },
        ],
        kind: "message",
      },
    };

    const client = await A2AClient.fromCardUrl(AGENTS.MERCHANT_AGENT);
    const response = await client.sendMessage(sendParams);

    if ("error" in response) {
      console.error("Error:", response.error.message);
      throw new Error(response.error.message);
    } else {
      const result = (response as SendMessageSuccessResponse).result;
      if (result.kind === "task") {
        setState({ initiatePaymentTaskId: result.id });

        if (result.status.state === "completed") {
          setState({
            paymentReceipt: {
              receiptId: `receipt_${result.id}`,
              transactionId: result.id,
              status: "success",
              timestamp: new Date().toISOString(),
            },
          });
        }

        return result.status;
      }
    }
  }
);

export const initiatePaymentWithOtp = ai.defineTool(
  {
    name: "initiatePaymentWithOtp",
    description: `
    Initiates a payment using the payment mandate from state and a
    challenge response. In our sample, the challenge response is a one-time
    password (OTP) sent to the user.
  `,
    inputSchema: z.object({
      challengeResponse: z.string(),
      debugMode: z.boolean().optional().default(false),
    }),
  },
  async (input) => {
    const { challengeResponse, debugMode } = input;

    const signedPaymentMandate = getState().signedPaymentMandate;
    if (!signedPaymentMandate) {
      throw new Error("No signed payment mandate found in tool context state.");
    }

    const riskData = getState().riskData;
    if (!riskData) {
      throw new Error("No risk data found in tool context state.");
    }

    const sendParams: MessageSendParams = {
      message: {
        messageId: uuidv4(),
        role: "user",
        contextId: getState().shoppingContextId,
        taskId: getState().initiatePaymentTaskId,
        parts: [
          {
            kind: "text",
            text: "Initiate a payment. Include the challenge response.",
          },
          {
            kind: "data",
            data: {
              [DATA_KEYS.PAYMENT_MANDATE]: signedPaymentMandate,
            },
          },
          {
            kind: "data",
            data: {
              risk_data: riskData,
            },
          },
          {
            kind: "data",
            data: {
              shopping_agent_id: "trusted_shopping_agent",
            },
          },
          {
            kind: "data",
            data: {
              challenge_response: challengeResponse,
            },
          },
          {
            kind: "data",
            data: {
              debug_mode: debugMode,
            },
          },
        ],
        kind: "message",
      },
    };

    const client = await A2AClient.fromCardUrl(AGENTS.MERCHANT_AGENT);
    const response = await client.sendMessage(sendParams);

    if ("error" in response) {
      console.error("Error:", response.error.message);
      throw new Error(response.error.message);
    } else {
      const result = (response as SendMessageSuccessResponse).result;
      if (result.kind === "task") {
        if (result.status.state === "completed") {
          setState({
            paymentReceipt: {
              receiptId: `receipt_${result.id}`,
              transactionId: result.id,
              status: "success",
              timestamp: new Date().toISOString(),
            },
          });
        }

        return result.status;
      }
    }
  }
);

const generateCartMandateHash = (cartMandate: CartMandate) => {
  return `fake_cart_mandate_hash_${cartMandate.contents.id}`;
};

const generatePaymentMandateHash = (paymentMandate: PaymentMandate) => {
  return `fake_payment_mandate_hash_${paymentMandate.paymentMandateContents.paymentMandateId}`;
};
