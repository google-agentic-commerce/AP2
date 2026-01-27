import { ai, z } from "./genkit.js";
import { A2AClient } from "@a2a-js/sdk/client";
import { AGENTS } from "../../../index.js";
import { v4 as uuidv4 } from "uuid";
import type {
  Artifact,
  DataPart,
  MessageSendParams,
  SendMessageSuccessResponse,
} from "@a2a-js/sdk";
import { getState, setState } from "../../../../store/state.js";

const INTENT_MANDATE_DATA_KEY = "ap2.mandates.IntentMandate";
export const createIntentMandate = ai.defineTool(
  {
    name: "create_intent_mandate",
    description: "Create an IntentMandate",
    inputSchema: z.object({
      naturalLanguageDescription: z
        .string()
        .describe("The description of the user's intent."),
      userCartConfirmationRequired: z
        .boolean()
        .describe("If the user must confirm the cart."),
      merchants: z.array(z.string()).describe("A list of allowed merchants."),
      skus: z.array(z.string()).describe("A list of allowed SKUs."),
      requiresRefundability: z
        .boolean()
        .describe("If the items must be refundable."),
    }),
  },
  async (input) => {
    const {
      naturalLanguageDescription,
      userCartConfirmationRequired,
      merchants,
      skus,
      requiresRefundability,
    } = input;

    const intentMandate = {
      naturalLanguageDescription,
      userCartConfirmationRequired,
      merchants,
      skus,
      requiresRefundability,
      intentExpiry: new Date(Date.now() + 1000 * 60 * 60 * 24).toISOString(),
    };

    setState({ intentMandate });

    return intentMandate;
  }
);

export const findProducts = ai.defineTool(
  {
    name: "find_products",
    description:
      "Calls the merchant agent to find products matching the user's intent.",
    inputSchema: z.object({
      debugMode: z
        .boolean()
        .optional()
        .default(false)
        .describe("If the agent is in debug mode."),
    }),
  },
  async (input) => {
    const intentMandate = getState().intentMandate;
    if (!intentMandate) {
      throw new Error("No IntentMandate found in tool context state.");
    }

    const riskData = collectRiskData();
    if (!riskData) {
      throw new Error("No risk data found in tool context state.");
    }

    const client = await A2AClient.fromCardUrl(AGENTS.MERCHANT_AGENT);
    const sendParams: MessageSendParams = {
      message: {
        messageId: uuidv4(),
        role: "user",
        parts: [
          {
            kind: "text",
            text: "Find products that match the user's IntentMandate.",
          },
          {
            kind: "data",
            data: {
              [INTENT_MANDATE_DATA_KEY]: intentMandate,
            },
          },
          {
            kind: "data",
            data: {
              riskData,
            },
          },
          {
            kind: "data",
            data: {
              debugMode: input.debugMode,
            },
          },
          {
            kind: "data",
            data: {
              shoppingAgentId: "trusted_shopping_agent",
            },
          },
        ],
        kind: "message",
      },
    };
    const response = await client.sendMessage(sendParams);

    if ("error" in response) {
      console.error("Error:", response.error.message);
      throw new Error(response.error.message);
    } else {
      const result = (response as SendMessageSuccessResponse).result;
      if (result.kind === "task") {
        if (result.status.state !== "completed") {
          throw new Error(`Failed to find products: ${result.status}`);
        }
        const cartMandates = parseCartMandates(result.artifacts);
        setState({ shoppingContextId: result.contextId, cartMandates });

        return { cartMandates };
      }
    }
  }
);

export const updateChosenCartMandate = ai.defineTool(
  {
    name: "update_chosen_cart_mandate",
    description:
      "Updates the chosen CartMandate in the tool context state. Use the item number (1, 2, or 3) from the list shown to the user.",
    inputSchema: z.object({
      itemNumber: z
        .number()
        .int()
        .min(1)
        .max(3)
        .describe("The item number from the list (1, 2, or 3)."),
    }),
  },
  async (input) => {
    const { itemNumber } = input;
    const cartMandates = getState().cartMandates || [];

    if (cartMandates.length === 0) {
      return "No products available. Please search for products first.";
    }

    if (itemNumber > cartMandates.length) {
      return `Invalid item number. Please choose a number between 1 and ${cartMandates.length}.`;
    }

    const selectedCart = cartMandates[itemNumber - 1];
    const cartId = selectedCart.contents.id;

    setState({ chosenCartId: cartId, cartMandate: selectedCart });
    return `Item ${itemNumber} selected successfully.`;
  }
);

const parseCartMandates = (artifacts: Artifact[]) => {
  const CART_MANDATE_DATA_KEY = "ap2.mandates.CartMandate";
  const cartMandates: Record<string, unknown>[] = [];

  for (const artifact of artifacts) {
    for (const part of artifact.parts) {
      if (part.kind === "data") {
        const dataPart = part as DataPart;
        const data = dataPart.data as Record<string, unknown>;
        if (CART_MANDATE_DATA_KEY in data) {
          cartMandates.push(
            data[CART_MANDATE_DATA_KEY] as Record<string, unknown>
          );
        }
      }
    }
  }

  return cartMandates;
};

const collectRiskData = () => {
  const riskData = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...fake_risk_data";
  setState({ riskData });
  return { riskData };
};
