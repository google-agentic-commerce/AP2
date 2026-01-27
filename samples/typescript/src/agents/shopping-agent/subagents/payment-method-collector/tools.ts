import type {
  MessageSendParams,
  SendMessageSuccessResponse,
} from "@a2a-js/sdk";
import { ai, z } from "./genkit.js";
import { v4 as uuidv4 } from "uuid";
import { A2AClient } from "@a2a-js/sdk/client";
import { AGENTS } from "../../../index.js";
import { getFirstDataPart } from "../../../../utils/artifact.js";
import { getState, setState } from "../../../../store/state.js";

const PAYMENT_METHOD_DATA_DATA_KEY = "payment_request.PaymentMethodData";

export const getPaymentMethods = ai.defineTool(
  {
    name: "get_payment_methods",
    description:
      "Gets the user's payment methods from the credentials provider.",
    inputSchema: z.object({
      userEmail: z.string(),
    }),
  },
  async (input) => {
    const { userEmail } = input;

    const cartMandate = getState().cartMandate;
    if (!cartMandate) {
      throw new Error("No cart mandate found in tool context state.");
    }

    const sendParams: MessageSendParams = {
      message: {
        messageId: uuidv4(),
        role: "user",
        contextId: getState().shoppingContextId,
        parts: [
          {
            kind: "text",
            text: "Get the user's payment methods.",
          },
          {
            kind: "data",
            data: {
              user_email: userEmail,
            },
          },
        ],
        kind: "message",
      },
    };

    for (const methodData of cartMandate.contents.paymentRequest.methodData) {
      sendParams.message.parts.push({
        kind: "data",
        data: {
          [PAYMENT_METHOD_DATA_DATA_KEY]: methodData,
        },
      });
    }

    const client = await A2AClient.fromCardUrl(AGENTS.CREDENTIALS_PROVIDER);
    const response = await client.sendMessage(sendParams);

    if ("error" in response) {
      console.error(
        "Error in credentials provider agent:",
        response.error.message
      );
      throw new Error(response.error.message);
    } else {
      const result = (response as SendMessageSuccessResponse).result;

      if (result.kind !== "task") {
        throw new Error("Expected task response");
      }

      const paymentMethods = getFirstDataPart(result.artifacts);
      return paymentMethods;
    }
  }
);

export const getPaymentCredentialToken = ai.defineTool(
  {
    name: "get_payment_credential_token",
    description:
      "Gets a payment credential token from the credentials provider.",
    inputSchema: z.object({
      userEmail: z.string(),
      paymentMethodAlias: z.string(),
    }),
  },
  async (input) => {
    const { userEmail, paymentMethodAlias } = input;

    const sendParams: MessageSendParams = {
      message: {
        messageId: uuidv4(),
        role: "user",
        contextId: getState().shoppingContextId,
        parts: [
          {
            kind: "text",
            text: "Get a payment credential token for the user's payment method.",
          },
          {
            kind: "data",
            data: {
              user_email: userEmail,
              payment_method_alias: paymentMethodAlias,
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
    } else {
      const result = (response as SendMessageSuccessResponse).result;

      if (result.kind !== "task") {
        throw new Error("Expected task response");
      }

      const dataParts = result.artifacts.map((artifact) => {
        const dataParts = [];

        for (const part of artifact.parts) {
          if (part.kind === "data") {
            dataParts.push(part.data);
          }
        }

        return dataParts;
      });

      const getFirstDataPart = (
        dataParts: unknown[][]
      ): Record<string, unknown> | null => {
        for (const dataPart of dataParts) {
          for (const item of dataPart) {
            return item as Record<string, unknown>;
          }
        }
        return null;
      };

      const data = getFirstDataPart(dataParts);

      const token = data?.token as string | undefined;
      setState({ paymentCredentialToken: token });

      return {
        status: "success",
        token,
      };
    }
  }
);
