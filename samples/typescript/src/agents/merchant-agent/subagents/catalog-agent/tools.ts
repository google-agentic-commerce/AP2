import { parseCanonicalObject } from "../../../../utils/message.js";
import { ai, z } from "../../genkit.js";
import type { ExecutionEventBus } from "@a2a-js/sdk/server";
import type {
  Task,
  TaskStatusUpdateEvent,
  TaskArtifactUpdateEvent,
} from "@a2a-js/sdk";
import type { PaymentItem } from "../../../../types/payment-item.js";
import type { CartMandate } from "../../../../types/cart-mandate.js";
import { v4 as uuidv4 } from "uuid";
import { setCartMandate, setRiskData } from "../../storage.js";
import { intentMandateSchema } from "../../../../schemas/intent-mandate.js";
import type { IntentMandate } from "../../../../types/intent-mandate.js";

const INTENT_MANDATE_DATA_KEY = "ap2.mandates.IntentMandate";
const CART_MANDATE_DATA_KEY = "ap2.mandates.CartMandate";

// Simple schema for IntentMandate
// const intentMandateSchema = {
//   parse: (data: any) => {
//     if (!data || !data.naturalLanguageDescription) {
//       throw new Error(
//         "Invalid IntentMandate: missing naturalLanguageDescription"
//       );
//     }
//     return data as { naturalLanguageDescription: string };
//   },
// };

const DEBUG_MODE_INSTRUCTIONS = `
Debug mode: Generate realistic, diverse product data. Ensure all prices and details are reasonable.
`;

/**
 * Creates a CartMandate and adds it as an artifact.
 */
async function createAndAddCartMandateArtifact(
  item: PaymentItem,
  itemCount: number,
  currentTime: Date,
  taskId: string,
  contextId: string,
  eventBus: ExecutionEventBus
): Promise<void> {
  const cartExpiryTime = new Date(currentTime.getTime() + 30 * 60 * 1000); // 30 minutes from now

  const cartMandate: CartMandate = {
    contents: {
      id: `cart_${itemCount}`,
      userCartConfirmationRequired: true,
      paymentRequest: {
        methodData: [
          {
            supportedMethods: "CARD",
            data: {
              network: ["mastercard", "paypal", "amex"],
            },
          },
        ],
        details: {
          id: `order_${itemCount}`,
          displayItems: [item],
          shippingOptions: [],
          total: {
            label: "Total",
            amount: item.amount,
            pending: false,
            refundPeriod: item.refundPeriod,
          },
        },
        options: {
          requestShipping: true,
        },
      },
      cartExpiry: cartExpiryTime.toISOString(),
      merchantName: "Generic Merchant",
    },
  };

  // Store the cart mandate
  setCartMandate(cartMandate.contents.id, cartMandate);

  // Publish artifact
  const artifactUpdate: TaskArtifactUpdateEvent = {
    kind: "artifact-update",
    taskId,
    contextId,
    artifact: {
      artifactId: uuidv4(),
      parts: [
        {
          kind: "data",
          data: {
            [CART_MANDATE_DATA_KEY]: cartMandate,
          },
        },
      ],
    },
  };

  eventBus.publish(artifactUpdate);
}

/**
 * Creates fake risk data for demonstration purposes.
 */
function collectRiskData(contextId: string): string {
  const riskData = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...fake_risk_data";
  setRiskData(contextId, riskData);
  return riskData;
}

/**
 * Helper to publish a failed status with a message.
 */
function publishFailedStatus(
  taskId: string,
  contextId: string,
  errorText: string,
  eventBus: ExecutionEventBus
): void {
  const failedUpdate: TaskStatusUpdateEvent = {
    kind: "status-update",
    taskId,
    contextId,
    status: {
      state: "failed",
      message: {
        kind: "message",
        role: "agent",
        messageId: uuidv4(),
        parts: [{ kind: "text", text: errorText }],
        taskId,
        contextId,
      },
      timestamp: new Date().toISOString(),
    },
    final: true,
  };
  eventBus.publish(failedUpdate);
}

/**
 * Helper to sleep for a specified number of milliseconds.
 */
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export const findItemsWorkflow = ai.defineTool(
  {
    name: "findItemsWorkflow",
    description: "Finds products that match the user's IntentMandate.",
    inputSchema: z.object({
      dataParts: z.array(z.record(z.unknown())),
      eventBus: z.custom<ExecutionEventBus>(),
      currentTask: z.custom<Task>().optional(),
    }),
  },
  async (input) => {
    const { dataParts, eventBus, currentTask } = input;

    // Generate task IDs if currentTask is not provided
    const taskId = currentTask?.id || uuidv4();
    const contextId = currentTask?.contextId || uuidv4();

    // Parse the IntentMandate
    let intentMandate: IntentMandate;
    try {
      intentMandate = parseCanonicalObject(
        INTENT_MANDATE_DATA_KEY,
        dataParts,
        intentMandateSchema
      );
    } catch (error) {
      publishFailedStatus(
        taskId,
        contextId,
        "No IntentMandate found in data parts.",
        eventBus
      );
      throw error;
    }

    const intent = intentMandate.naturalLanguageDescription;
    const prompt = `
Based on the user's request for '${intent}', your task is to generate 3
complete, unique and realistic PaymentItem JSON objects.

You MUST exclude all branding from the PaymentItem \`label\` field.

${DEBUG_MODE_INSTRUCTIONS}
    `;

    // Retry mechanism for Gemini API calls
    const maxRetries = 3;
    const retryDelay = 1000; // milliseconds

    let items: PaymentItem[] = [];

    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        // Use Genkit to generate the items
        const response = await ai.generate({
          prompt,
          output: {
            schema: z.array(
              z.object({
                label: z.string(),
                amount: z.object({
                  currency: z.string(),
                  value: z.number(),
                }),
                pending: z.boolean().optional(),
                refundPeriod: z.number(),
              })
            ),
          },
        });

        items = response.output as PaymentItem[];
        break; // Success, exit retry loop
      } catch (error) {
        if (attempt === maxRetries - 1) {
          // Last attempt failed
          const errorMessage = `Unable to generate products after ${maxRetries} attempts due to server error: ${
            error instanceof Error ? error.message : String(error)
          }. Please try again later.`;
          publishFailedStatus(taskId, contextId, errorMessage, eventBus);
          throw new Error(errorMessage);
        } else {
          // Wait before retrying with exponential backoff
          await sleep(retryDelay * (attempt + 1));
        }
      }
    }

    // Validate items
    if (!items || items.length === 0) {
      const errorMessage =
        "No products were generated. Please try with different search criteria.";
      publishFailedStatus(taskId, contextId, errorMessage, eventBus);
      throw new Error(errorMessage);
    }

    try {
      const currentTime = new Date();
      let itemCount = 0;

      // Create cart mandates for each item
      for (const item of items) {
        itemCount++;
        await createAndAddCartMandateArtifact(
          item,
          itemCount,
          currentTime,
          taskId,
          contextId,
          eventBus
        );
      }

      // Add risk data artifact
      const riskData = collectRiskData(contextId);
      const riskDataArtifact: TaskArtifactUpdateEvent = {
        kind: "artifact-update",
        taskId: taskId,
        contextId: contextId,
        artifact: {
          artifactId: uuidv4(),
          parts: [
            {
              kind: "data",
              data: { risk_data: riskData },
            },
          ],
        },
      };
      eventBus.publish(riskDataArtifact);

      // Publish completed status
      const completedUpdate: TaskStatusUpdateEvent = {
        kind: "status-update",
        taskId: taskId,
        contextId: contextId,
        status: {
          state: "completed",
          message: {
            kind: "message",
            role: "agent",
            messageId: uuidv4(),
            parts: [
              {
                kind: "text",
                text: `Generated ${itemCount} product(s) matching your request.`,
              },
            ],
            taskId: taskId,
            contextId: contextId,
          },
          timestamp: new Date().toISOString(),
        },
        final: true,
      };
      eventBus.publish(completedUpdate);

      return { status: "success", itemCount };
    } catch (error) {
      const errorMessage = `Unexpected error processing products: ${
        error instanceof Error ? error.message : String(error)
      }. Please try again.`;
      publishFailedStatus(taskId, contextId, errorMessage, eventBus);
      throw error;
    }
  }
);
