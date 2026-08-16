import { describe, expect, it } from "vitest";
import {
  AmountSchema,
  CheckoutMandateSchema,
  CheckoutReceiptSchema,
  MerchantSchema,
  OpenCheckoutMandateSchema,
  OpenPaymentMandateSchema,
  PaymentInstrumentSchema,
  PaymentMandateSchema,
  PaymentReceiptSchema,
} from "../src/index.js";

// Mirrors the fixture defaults in
// code/sdk/python/ap2/tests/conftest.py::sample_payment_mandate, so the two
// SDKs agree on what a minimal valid mandate looks like.
describe("PaymentMandateSchema", () => {
  it("accepts a minimal valid payment mandate", () => {
    const result = PaymentMandateSchema.safeParse({
      transaction_id: "tx_1",
      payee: { id: "s-1", name: "Shop" },
      payment_amount: { amount: 1000, currency: "USD" },
      payment_instrument: { id: "pi-1", type: "credit" },
    });
    expect(result.success).toBe(true);
  });

  it("applies the vct default", () => {
    const result = PaymentMandateSchema.parse({
      transaction_id: "tx_1",
      payee: { id: "s-1", name: "Shop" },
      payment_amount: { amount: 1000, currency: "USD" },
      payment_instrument: { id: "pi-1", type: "credit" },
    });
    expect(result.vct).toBe("mandate.payment.1");
  });

  it("rejects a mismatched vct literal", () => {
    const result = PaymentMandateSchema.safeParse({
      vct: "mandate.checkout.1",
      transaction_id: "tx_1",
      payee: { id: "s-1", name: "Shop" },
      payment_amount: { amount: 1000, currency: "USD" },
      payment_instrument: { id: "pi-1", type: "credit" },
    });
    expect(result.success).toBe(false);
  });

  it("rejects a missing required field", () => {
    const result = PaymentMandateSchema.safeParse({
      transaction_id: "tx_1",
      payee: { id: "s-1", name: "Shop" },
      payment_instrument: { id: "pi-1", type: "credit" },
    });
    expect(result.success).toBe(false);
  });
});

describe("CheckoutMandateSchema", () => {
  it("accepts a minimal valid checkout mandate", () => {
    const result = CheckoutMandateSchema.safeParse({
      checkout_jwt: "ZmFrZS1qd3Q",
      checkout_hash: "ZmFrZS1oYXNo",
    });
    expect(result.success).toBe(true);
  });

  it("rejects a missing checkout_hash", () => {
    const result = CheckoutMandateSchema.safeParse({
      checkout_jwt: "ZmFrZS1qd3Q",
    });
    expect(result.success).toBe(false);
  });
});

describe("OpenPaymentMandateSchema", () => {
  it("accepts an open payment mandate with an amount_range constraint", () => {
    const result = OpenPaymentMandateSchema.safeParse({
      constraints: [
        { type: "payment.amount_range", currency: "USD", max: 5000 },
      ],
      cnf: { jwk: { kty: "EC", crv: "P-256", x: "x", y: "y" } },
    });
    expect(result.success).toBe(true);
  });

  it("rejects a constraint entry that matches none of the known constraint types", () => {
    const result = OpenPaymentMandateSchema.safeParse({
      constraints: [{ type: "not.a.real.constraint" }],
      cnf: { jwk: { kty: "EC", crv: "P-256", x: "x", y: "y" } },
    });
    expect(result.success).toBe(false);
  });
});

describe("OpenCheckoutMandateSchema", () => {
  it("accepts a minimal valid open checkout mandate", () => {
    const result = OpenCheckoutMandateSchema.safeParse({
      constraints: [
        {
          type: "checkout.line_items",
          items: [
            {
              id: "req-1",
              acceptable_items: [{ id: "sku-1", title: "Widget" }],
              quantity: 1,
            },
          ],
        },
      ],
      cnf: { jwk: { kty: "EC", crv: "P-256", x: "x", y: "y" } },
    });
    expect(result.success).toBe(true);
  });

  it("rejects a missing cnf", () => {
    const result = OpenCheckoutMandateSchema.safeParse({
      constraints: [],
    });
    expect(result.success).toBe(false);
  });
});

describe("PaymentReceiptSchema", () => {
  const base = {
    iss: "issuer",
    iat: 1700000000,
    reference: "ref-hash",
    payment_id: "pay-1",
  };

  it("accepts a Success receipt with confirmation IDs", () => {
    const result = PaymentReceiptSchema.safeParse({
      ...base,
      status: "Success",
      psp_confirmation_id: "psp-1",
      network_confirmation_id: "net-1",
    });
    expect(result.success).toBe(true);
  });

  it("rejects a Success receipt missing confirmation IDs", () => {
    // Regression test for the oneOf-branch-required fix in scripts/generate.ts
    // (materializeSiblingOneOf) — without it this incorrectly validated.
    const result = PaymentReceiptSchema.safeParse({
      ...base,
      status: "Success",
    });
    expect(result.success).toBe(false);
  });

  it("accepts an Error receipt with error details", () => {
    const result = PaymentReceiptSchema.safeParse({
      ...base,
      status: "Error",
      error: "insufficient_funds",
      error_description: "The payment instrument was declined.",
    });
    expect(result.success).toBe(true);
  });

  it("rejects an Error receipt missing error details", () => {
    const result = PaymentReceiptSchema.safeParse({
      ...base,
      status: "Error",
    });
    expect(result.success).toBe(false);
  });
});

describe("CheckoutReceiptSchema", () => {
  const base = { iss: "issuer", iat: 1700000000, reference: "ref-hash" };

  it("accepts a Success receipt with an order_id", () => {
    const result = CheckoutReceiptSchema.safeParse({
      ...base,
      status: "Success",
      order_id: "order-1",
    });
    expect(result.success).toBe(true);
  });

  it("rejects a Success receipt missing order_id", () => {
    const result = CheckoutReceiptSchema.safeParse({
      ...base,
      status: "Success",
    });
    expect(result.success).toBe(false);
  });
});

describe("shared types", () => {
  it("validates a Merchant", () => {
    expect(MerchantSchema.safeParse({ id: "s-1", name: "Shop" }).success).toBe(
      true
    );
  });

  it("validates an Amount", () => {
    expect(
      AmountSchema.safeParse({ amount: 1000, currency: "USD" }).success
    ).toBe(true);
  });

  it("rejects an Amount with a non-integer amount", () => {
    expect(
      AmountSchema.safeParse({ amount: 10.5, currency: "USD" }).success
    ).toBe(false);
  });

  it("validates a PaymentInstrument", () => {
    expect(
      PaymentInstrumentSchema.safeParse({ id: "pi-1", type: "credit" }).success
    ).toBe(true);
  });
});
