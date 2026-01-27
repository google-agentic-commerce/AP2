import { ai, z } from "./genkit.js";
import type { Task } from "@a2a-js/sdk";
import { v4 as uuidv4 } from "uuid";
import type { ExecutionEventBus } from "@a2a-js/sdk/server";
import {
  findDataPart,
  findDataParts,
  parseCanonicalObject,
} from "../../utils/message.js";
import * as accountManager from "./account-manager.js";
import { paymentMandateSchema } from "../../schemas/payment-mandate.js";

const PAYMENT_MANDATE_DATA_KEY = "ap2.mandates.PaymentMandate";
const PAYMENT_METHOD_DATA_DATA_KEY = "payment_request.PaymentMethodData";

export const handleCreatePaymentCredentialToken = ai.defineTool(
  {
    name: "handleCreatePaymentCredentialToken",
    description: `Handles a request to get a payment credential token.
Updates a task with the payment credential token.`,
    inputSchema: z.object({
      dataParts: z
        .array(z.record(z.unknown()))
        .describe(
          "DataPart contents. Should contain the user_email and payment_method_alias."
        ),
      eventBus: z.custom<ExecutionEventBus>().describe("The event bus."),
      currentTask: z
        .custom<Task>()
        .optional()
        .describe("The current task if there is one."),
    }),
  },
  async (input) => {
    const { dataParts, eventBus, currentTask } = input;

    const userEmail = findDataPart("user_email", dataParts) as string | null;
    const paymentMethodAlias = findDataPart(
      "payment_method_alias",
      dataParts
    ) as string | null;

    if (!userEmail || !paymentMethodAlias) {
      throw new Error("user_email and payment_method_alias are required");
    }

    const tokenizedPaymentMethod = accountManager.createToken(
      userEmail,
      paymentMethodAlias
    );

    eventBus.publish({
      kind: "artifact-update",
      taskId: currentTask?.id,
      contextId: currentTask?.contextId,
      artifact: {
        artifactId: uuidv4(),
        parts: [{ kind: "data", data: { token: tokenizedPaymentMethod } }],
      },
    });

    return { tokenizedPaymentMethod };
  }
);

export const handleGetPaymentMethodRawCredentials = ai.defineTool(
  {
    name: "handleGetPaymentMethodRawCredentials",
    description: `Handles a request to get the raw credentials for a payment method.
Updates a task with the payment method's raw credentials.`,
    inputSchema: z.object({
      dataParts: z
        .array(z.record(z.unknown()))
        .describe("DataPart contents. Should contain a single PaymentMandate."),
      eventBus: z.custom<ExecutionEventBus>().describe("The event bus."),
      currentTask: z
        .custom<Task>()
        .optional()
        .describe("The current task if there is one."),
    }),
  },
  async (input) => {
    const { dataParts, eventBus, currentTask } = input;

    const paymentMandateContents = parseCanonicalObject(
      PAYMENT_MANDATE_DATA_KEY,
      dataParts,
      paymentMandateSchema
    ).paymentMandateContents;

    const token = paymentMandateContents.paymentResponse.details.token;
    const paymentMandateId = paymentMandateContents.paymentMandateId;

    const paymentMethod = accountManager.verifyToken(token, paymentMandateId);

    if (!paymentMethod) {
      throw new Error("Payment method not found");
    }

    eventBus.publish({
      kind: "artifact-update",
      taskId: currentTask?.id,
      contextId: currentTask?.contextId,
      artifact: {
        artifactId: uuidv4(),
        parts: [{ kind: "data", data: paymentMethod }],
      },
    });

    return { paymentMethod };
  }
);

export const handleGetShippingAddress = ai.defineTool(
  {
    name: "handleGetShippingAddress",
    description: `Handles a request to get the user's shipping address.
Updates a task with the user's shipping address.`,
    inputSchema: z.object({
      dataParts: z
        .array(z.record(z.unknown()))
        .describe("DataPart contents. Should contain a single user_email."),
      eventBus: z.custom<ExecutionEventBus>().describe("The event bus."),
      currentTask: z
        .custom<Task>()
        .optional()
        .describe("The current task if there is one."),
    }),
  },
  async (input) => {
    const { dataParts, eventBus, currentTask } = input;

    const userEmail = findDataPart("user_email", dataParts) as string | null;
    if (!userEmail) {
      throw new Error("user_email is required");
    }

    const shippingAddress = accountManager.getAccountShippingAddress(userEmail);
    if (!shippingAddress) {
      throw new Error("Shipping address not found");
    }

    eventBus.publish({
      kind: "artifact-update",
      taskId: currentTask?.id,
      contextId: currentTask?.contextId,
      artifact: {
        artifactId: uuidv4(),
        parts: [{ kind: "data", data: shippingAddress }],
      },
    });

    return { shippingAddress };
  }
);

export const handleSearchPaymentMethods = ai.defineTool(
  {
    name: "handleSearchPaymentMethods",
    description: `Returns the user's payment methods that match what the merchant accepts.

The merchant's accepted payment methods are provided in the data_parts as a
list of PaymentMethodData objects.  The user's account is identified by the
user_email provided in the data_parts.

This tool finds and returns all the payment methods associated with the user's
account that match the merchant's accepted payment methods.`,
    inputSchema: z.object({
      dataParts: z
        .array(z.record(z.unknown()))
        .describe(
          "DataPart contents. Should contain a single user_email and a list of PaymentMethodData objects."
        ),
      eventBus: z.custom<ExecutionEventBus>().describe("The event bus."),
      currentTask: z
        .custom<Task>()
        .optional()
        .describe("The current task if there is one."),
    }),
  },
  async (input) => {
    const { dataParts, eventBus, currentTask } = input;

    const userEmail = findDataPart("user_email", dataParts) as string | null;
    const methodData = findDataParts(PAYMENT_METHOD_DATA_DATA_KEY, dataParts);

    if (!userEmail) {
      throw new Error("user_email is required for search_payment_methods");
    }
    if (!methodData || methodData.length === 0) {
      throw new Error("method_data is required for search_payment_methods");
    }

    const merchantMethodDataList = methodData.map(
      (data) => data as PaymentMethodData
    );

    const eligibleAliases = getEligiblePaymentMethodAliases(
      userEmail,
      merchantMethodDataList
    );

    eventBus.publish({
      kind: "artifact-update",
      taskId: currentTask?.id,
      contextId: currentTask?.contextId,
      artifact: {
        artifactId: uuidv4(),
        parts: [{ kind: "data", data: eligibleAliases }],
      },
    });

    return { eligibleAliases };
  }
);

export const handleSignedPaymentMandate = ai.defineTool(
  {
    name: "handleSignedPaymentMandate",
    description: `Handles a signed payment mandate.

Adds the payment mandate id to the token in storage and then completes the task.`,
    inputSchema: z.object({
      dataParts: z
        .array(z.record(z.unknown()))
        .describe("DataPart contents. Should contain a single PaymentMandate."),
      eventBus: z.custom<ExecutionEventBus>().describe("The event bus."),
      currentTask: z
        .custom<Task>()
        .optional()
        .describe("The current task if there is one."),
    }),
  },
  async (input) => {
    const { dataParts, eventBus, currentTask } = input;

    const paymentMandate = parseCanonicalObject(
      PAYMENT_MANDATE_DATA_KEY,
      dataParts,
      paymentMandateSchema
    );

    const token =
      paymentMandate.paymentMandateContents.paymentResponse.details.token;
    const paymentMandateId =
      paymentMandate.paymentMandateContents.paymentMandateId;

    accountManager.updateToken(token, paymentMandateId);

    eventBus.publish({
      kind: "artifact-update",
      taskId: currentTask?.id,
      contextId: currentTask?.contextId,
      artifact: {
        artifactId: uuidv4(),
        parts: [
          {
            kind: "data",
            data: {
              status: "signed_payment_mandate_received",
              paymentMandateId: paymentMandateId,
            },
          },
        ],
      },
    });

    return {
      success: true,
      message: "Signed payment mandate validated and stored successfully.",
    };
  }
);

interface PaymentMethodData {
  supportedMethods: string; // Changed to match actual data structure (camelCase)
  data: {
    network?: string[];
  } & Record<string, unknown>;
}

function getPaymentMethodAliases(
  paymentMethods: accountManager.PaymentMethod[]
): (string | undefined)[] {
  return paymentMethods.map((paymentMethod) => paymentMethod.alias);
}

function getEligiblePaymentMethodAliases(
  userEmail: string,
  merchantAcceptedPaymentMethods: PaymentMethodData[]
): { payment_method_aliases: (string | undefined)[] } {
  const paymentMethods = accountManager.getAccountPaymentMethods(userEmail);
  const eligiblePaymentMethods: accountManager.PaymentMethod[] = [];

  for (const paymentMethod of paymentMethods) {
    for (const criteria of merchantAcceptedPaymentMethods) {
      if (paymentMethodIsEligible(paymentMethod, criteria)) {
        eligiblePaymentMethods.push(paymentMethod);
        break;
      }
    }
  }

  return {
    payment_method_aliases: getPaymentMethodAliases(eligiblePaymentMethods),
  };
}

function paymentMethodIsEligible(
  paymentMethod: accountManager.PaymentMethod,
  merchantCriteria: PaymentMethodData
): boolean {
  if (paymentMethod.type !== merchantCriteria.supportedMethods) {
    return false;
  }

  const merchantSupportedNetworks = (merchantCriteria.data?.network || []).map(
    (network) => network.toLowerCase()
  );

  if (merchantSupportedNetworks.length === 0) {
    return false;
  }

  const paymentCardNetworks = paymentMethod.network || [];
  for (const networkInfo of paymentCardNetworks) {
    for (const supportedNetwork of merchantSupportedNetworks) {
      if (networkInfo.name?.toLowerCase() === supportedNetwork) {
        return true;
      }
    }
  }

  return false;
}
