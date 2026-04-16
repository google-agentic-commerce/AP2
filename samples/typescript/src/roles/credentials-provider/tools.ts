/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import { FunctionTool } from '@google/adk';
import { z } from 'zod';
import { v4 as uuidv4 } from 'uuid';
import {
  findDataPart,
  findDataParts,
  parseCanonicalObject,
} from '../../common/utils/message.js';
import * as accountManager from './account-manager.js';
import { paymentMandateSchema } from '../../common/schemas/payment-mandate.js';
import { getA2AContextFromTool } from '../../common/server/a2a-context.js';
import { DATA_KEYS, A2A_DATA_KEYS } from '../../common/constants/index.js';

const PAYMENT_MANDATE_DATA_KEY = DATA_KEYS.PAYMENT_MANDATE;
const PAYMENT_METHOD_DATA_DATA_KEY = A2A_DATA_KEYS.PAYMENT_METHOD_DATA;

interface PaymentMethodData {
  supportedMethods: string;
  data: {
    network?: string[];
  } & Record<string, unknown>;
}

// Helper functions
function getPaymentMethodAliases(
  paymentMethods: accountManager.PaymentMethod[]
): (string | undefined)[] {
  return paymentMethods.map((paymentMethod) => paymentMethod.alias);
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

/**
 * ADK Tools for Credentials Provider Agent
 *
 * Note: These tools are designed to work within the A2A protocol.
 * The dataParts, eventBus, and currentTask are stored in session state
 * by the AgentExecutor before calling the agent.
 */

export const handleCreatePaymentCredentialToken = new FunctionTool({
  name: 'handleCreatePaymentCredentialToken',
  description: 'Handles a request to get a payment credential token. Updates a task with the payment credential token.',
  parameters: z.object({
    // Dummy parameter since ADK FunctionTool requires at least one parameter
    _trigger: z.boolean().optional().describe('Tool trigger'),
  }),
  execute: async (input, context) => {
    if (!context) throw new Error('Missing execution context');
    const { dataParts, eventBus, currentTask } = getA2AContextFromTool(context);

    const userEmail = findDataPart("user_email", dataParts) as string | null;
    const paymentMethodAlias = findDataPart(
      "payment_method_alias",
      dataParts
    ) as string | null;

    if (!userEmail || !paymentMethodAlias) {
      return { error: "user_email and payment_method_alias are required but were not found in the request data. Report this error to the caller." };
    }

    const tokenizedPaymentMethod = await accountManager.createToken(
      userEmail,
      paymentMethodAlias
    );

    // Publish artifact via A2A eventBus
    if (eventBus) {
      eventBus.publish({
        kind: "artifact-update",
        taskId: currentTask?.id,
        contextId: currentTask?.contextId,
        artifact: {
          artifactId: uuidv4(),
          parts: [{ kind: "data", data: { token: tokenizedPaymentMethod } }],
        },
      });
    }

    return { tokenizedPaymentMethod };
  },
});

export const handleGetPaymentMethodRawCredentials = new FunctionTool({
  name: 'handleGetPaymentMethodRawCredentials',
  description: 'Handles a request to get the raw credentials for a payment method. Updates a task with the payment method\'s raw credentials.',
  parameters: z.object({
    _trigger: z.boolean().optional().describe('Tool trigger'),
  }),
  execute: async (input, context) => {
    if (!context) throw new Error('Missing execution context');
    const { dataParts, eventBus, currentTask } = getA2AContextFromTool(context);

    let paymentMandate;
    try {
      paymentMandate = parseCanonicalObject(
        PAYMENT_MANDATE_DATA_KEY,
        dataParts,
        paymentMandateSchema
      );
    } catch {
      return { error: "PaymentMandate not found in request data. Report this error to the caller." };
    }
    const paymentMandateContents = paymentMandate.paymentMandateContents;

    // Extract token value from nested {value, url} structure
    const tokenObj = paymentMandateContents.paymentResponse.details?.token as
      | { value?: string; url?: string }
      | string
      | undefined;
    const token = typeof tokenObj === 'object' ? (tokenObj?.value ?? '') : (tokenObj ?? '');
    const paymentMandateId = paymentMandateContents.paymentMandateId;

    const paymentMethod = await accountManager.verifyToken(token, paymentMandateId);

    if (!paymentMethod) {
      return { error: "Payment method not found for the given token. Report this error to the caller." };
    }

    if (eventBus) {
      eventBus.publish({
        kind: "artifact-update",
        taskId: currentTask?.id,
        contextId: currentTask?.contextId,
        artifact: {
          artifactId: uuidv4(),
          parts: [{ kind: "data", data: paymentMethod }],
        },
      });
    }

    return { paymentMethod };
  },
});

export const handleGetShippingAddress = new FunctionTool({
  name: 'handleGetShippingAddress',
  description: 'Handles a request to get the user\'s shipping address. Updates a task with the user\'s shipping address.',
  parameters: z.object({
    _trigger: z.boolean().optional().describe('Tool trigger'),
  }),
  execute: async (input, context) => {
    if (!context) throw new Error('Missing execution context');
    const { dataParts, eventBus, currentTask } = getA2AContextFromTool(context);

    const userEmail = findDataPart("user_email", dataParts) as string | null;
    if (!userEmail) {
      return { error: "user_email is required but was not found in the request data. Report this error to the caller." };
    }

    const shippingAddress = accountManager.getAccountShippingAddress(userEmail);
    if (!shippingAddress) {
      return { error: `Shipping address not found for user ${userEmail}. Report this error to the caller.` };
    }

    if (eventBus) {
      eventBus.publish({
        kind: "artifact-update",
        taskId: currentTask?.id,
        contextId: currentTask?.contextId,
        artifact: {
          artifactId: uuidv4(),
          parts: [{ kind: "data", data: { [DATA_KEYS.CONTACT_ADDRESS]: shippingAddress } }],
        },
      });
    }

    return { shippingAddress };
  },
});

export const handleSearchPaymentMethods = new FunctionTool({
  name: 'handleSearchPaymentMethods',
  description: `Returns the user's payment methods that match what the merchant accepts.

The merchant's accepted payment methods are provided in the data_parts as a
list of PaymentMethodData objects. The user's account is identified by the
user_email provided in the data_parts.

This tool finds and returns all the payment methods associated with the user's
account that match the merchant's accepted payment methods.`,
  parameters: z.object({
    _trigger: z.boolean().optional().describe('Tool trigger'),
  }),
  execute: async (input, context) => {
    if (!context) throw new Error('Missing execution context');
    const { dataParts, eventBus, currentTask } = getA2AContextFromTool(context);

    const userEmail = findDataPart("user_email", dataParts) as string | null;
    const methodData = findDataParts(PAYMENT_METHOD_DATA_DATA_KEY, dataParts);

    if (!userEmail) {
      return { error: "user_email is required for search_payment_methods but was not found in the request data. Report this error to the caller." };
    }
    if (!methodData || methodData.length === 0) {
      return { error: "method_data is required for search_payment_methods but was not found in the request data. Report this error to the caller." };
    }

    const merchantMethodDataList = methodData.map(
      (data) => data as PaymentMethodData
    );

    const eligibleAliases = getEligiblePaymentMethodAliases(
      userEmail,
      merchantMethodDataList
    );

    if (eventBus) {
      eventBus.publish({
        kind: "artifact-update",
        taskId: currentTask?.id,
        contextId: currentTask?.contextId,
        artifact: {
          artifactId: uuidv4(),
          parts: [{ kind: "data", data: eligibleAliases }],
        },
      });
    }

    return { eligibleAliases };
  },
});

export const handleSignedPaymentMandate = new FunctionTool({
  name: 'handleSignedPaymentMandate',
  description: 'Handles a signed payment mandate. Adds the payment mandate id to the token in storage and then completes the task.',
  parameters: z.object({
    _trigger: z.boolean().optional().describe('Tool trigger'),
  }),
  execute: async (input, context) => {
    if (!context) throw new Error('Missing execution context');
    const { dataParts, eventBus, currentTask } = getA2AContextFromTool(context);

    let paymentMandate;
    try {
      paymentMandate = parseCanonicalObject(
        PAYMENT_MANDATE_DATA_KEY,
        dataParts,
        paymentMandateSchema
      );
    } catch {
      return { error: "PaymentMandate not found in request data. Report this error to the caller." };
    }

    // x402 short-circuit: no token processing needed
    const methodName = paymentMandate.paymentMandateContents.paymentResponse.methodName;
    if (methodName === 'https://www.x402.org/') {
      return { success: true, message: 'x402 payment mandate received, no token update needed.' };
    }

    // Extract token value from nested {value, url} structure
    const tokenObj = paymentMandate.paymentMandateContents.paymentResponse.details?.token as
      | { value?: string; url?: string }
      | string
      | undefined;
    const token = typeof tokenObj === 'object' ? (tokenObj?.value ?? '') : (tokenObj ?? '');
    const paymentMandateId = paymentMandate.paymentMandateContents.paymentMandateId;

    accountManager.updateToken(token, paymentMandateId);

    if (eventBus) {
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
    }

    return {
      success: true,
      message: "Signed payment mandate validated and stored successfully.",
    };
  },
});

export const handlePaymentReceipt = new FunctionTool({
  name: 'handlePaymentReceipt',
  description: 'Handles a payment receipt. This is a placeholder that completes the task without any action.',
  parameters: z.object({
    _trigger: z.boolean().optional().describe('Tool trigger'),
  }),
  execute: async () => {
    return { success: true, message: 'Payment receipt acknowledged.' };
  },
});
