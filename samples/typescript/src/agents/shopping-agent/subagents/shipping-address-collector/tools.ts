import type {
  Artifact,
  MessageSendParams,
  SendMessageSuccessResponse,
} from "@a2a-js/sdk";
import { ai, z } from "./genkit.js";
import { A2AClient } from "@a2a-js/sdk/client";
import { AGENTS } from "../../../index.js";
import { v4 as uuidv4 } from "uuid";
import { getState, setState } from "../../../../store/state.js";

export const getShippingAddress = ai.defineTool(
  {
    name: "get_shipping_address",
    description:
      "Gets the user's shipping address from the credentials provider.",
    inputSchema: z.object({
      userEmail: z.string(),
    }),
  },
  async (input) => {
    const sendParams: MessageSendParams = {
      message: {
        messageId: uuidv4(),
        role: "user",
        contextId: getState().shoppingContextId,
        parts: [
          {
            kind: "text",
            text: "Get the user's shipping address.",
          },
          {
            kind: "data",
            data: {
              user_email: input.userEmail,
            },
          },
        ],
        kind: "message",
      },
    };

    const client = await A2AClient.fromCardUrl(AGENTS.CREDENTIALS_PROVIDER);
    const response = await client.sendMessage(sendParams);

    if ("error" in response) {
      throw new Error(response.error.message);
    } else {
      const result = (response as SendMessageSuccessResponse).result;
      if (result.kind === "task") {
        if (result.status.state !== "completed") {
          throw new Error(
            `Failed to get shipping address: ${result.status.state}`
          );
        }
        const shippingAddress = parseShippingAddress(result.artifacts)?.[0];
        setState({ shippingAddress, userEmail: input.userEmail });
        return shippingAddress;
      }
    }
  }
);

const parseShippingAddress = (artifacts: Artifact[]) => {
  return artifacts.map((artifact) => {
    return artifact.parts.find((part) => part.kind === "data")?.data;
  });
};
