import type { CartMandate } from "../../types/cart-mandate.js";
import type { IntentMandate } from "../../types/intent-mandate.js";
import type { PaymentMandate } from "../../types/payment-mandate.js";

/**
 * Shipping address information.
 */
export type ShippingAddress = {
  recipient?: string;
  organization?: string;
  address_line?: string[];
  city?: string;
  region?: string;
  postal_code?: string;
  country?: string;
  phone_number?: string;
};

/**
 * Workflow stages for tracking progress through the shopping flow.
 */
export type WorkflowStage =
  | "idle"
  | "intent_created"
  | "products_found"
  | "cart_selected"
  | "shipping_collected"
  | "cart_updated"
  | "payment_method_collected"
  | "payment_mandate_created"
  | "mandate_signed"
  | "payment_initiated"
  | "payment_completed";

/**
 * Payment receipt information.
 */
export type PaymentReceipt = {
  receiptId: string;
  transactionId: string;
  status: "success" | "failed";
  timestamp: string;
  amount?: { value: number; currency: string };
};

/**
 * State object containing all data for the shopping workflow.
 *
 * In the protocol-pure approach, this state:
 * - Flows INTO an agent via Message data parts
 * - Flows OUT of an agent via Task artifacts
 * - Is NOT stored in global variables
 * - Uses AsyncLocalStorage for request-scoped access within one agent
 */
export type State = {
  shoppingContextId?: string;
  intentMandate?: IntentMandate;
  shippingAddress?: ShippingAddress;
  cartMandate?: CartMandate;
  cartMandates?: CartMandate[];
  chosenCartId?: string;
  initiatePaymentTaskId?: string;
  paymentCredentialToken?: string;
  paymentMandate?: PaymentMandate;
  signedPaymentMandate?: PaymentMandate;
  riskData?: string;
  userEmail?: string;
  subagentTaskIds?: Record<string, string>;
  workflowStage?: WorkflowStage;
  paymentReceipt?: PaymentReceipt;
};
