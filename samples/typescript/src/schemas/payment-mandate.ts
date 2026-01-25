import { z } from "genkit";
import { shippingAddressSchema } from "./shipping-address.js";

export const paymentMandateSchema = z.object({
  paymentMandateContents: z.object({
    paymentMandateId: z.string(),
    paymentDetailsId: z.string(),
    paymentDetailsTotal: z.object({
      label: z.string(),
      amount: z.object({
        currency: z.string(),
        value: z.number(),
      }),
      pending: z.boolean(),
      refundPeriod: z.number(),
    }),
    paymentResponse: z.object({
      requestId: z.string(),
      methodName: z.string(),
      details: z.object({
        token: z.string(),
      }),
      shippingAddress: shippingAddressSchema,
      payerEmail: z.string(),
    }),
    merchantAgent: z.string(),
    timestamp: z.string(),
  }),
  userAuthorization: z.string().optional(),
});
