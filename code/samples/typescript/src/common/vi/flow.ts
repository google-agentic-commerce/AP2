/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Verifiable Intent flow — per-role facade over `verifiable-intent-js`.
 *
 * This is the TypeScript replication of the official Python integration
 * (verifiable_intent: python/examples/autonomous_flow.py + immediate_flow.py),
 * sliced along the AP2 role boundaries so each agent/MCP server calls exactly
 * the one layer it owns:
 *
 *   Issuer  (credentials-provider) → issueIssuerCredential        (L1)
 *   User    (shopping-agent-v2)    → createUserMandate{Autonomous,Immediate}  (L2)
 *   Agent   (shopping-agent-v2)    → createAgentFulfillment       (L3a + L3b + presentations)
 *   Merchant(merchant-agent-mcp)   → verifyCheckoutChain          (verify L3b)
 *   Network (merchant-pp-mcp)      → verifyPaymentChainAndConstraints  (verify L3a + constraints)
 *
 * All values that cross a process boundary are serialized SD-JWT strings.
 */

import { randomUUID } from 'node:crypto';
import {
  AllowedMerchantConstraint,
  AllowedPayeeConstraint,
  ChainVerificationResult,
  CheckoutL3Mandate,
  CheckoutLineItemsConstraint,
  CheckoutMandate,
  type Constraint,
  ConstraintCheckResult,
  createLayer1,
  createLayer2Autonomous,
  createLayer2Immediate,
  createLayer3Checkout,
  createLayer3Payment,
  type Dict,
  decodeSdJwt,
  type Es256Jwk,
  FinalCheckoutMandate,
  FinalPaymentMandate,
  hashAscii,
  hashDisclosure,
  IssuerCredential,
  MandateMode,
  PaymentAmountConstraint,
  PaymentL3Mandate,
  PaymentMandate,
  PaymentRecurrenceConstraint,
  resolveDisclosures,
  type SdJwt,
  StrictnessMode,
  buildSelectivePresentation,
  checkConstraints,
  UserMandate,
  verifyChain,
} from 'verifiable-intent-js';

import { checkoutHashFromJwt } from './checkout-jwt.js';
import { MERCHANT_AUD, NETWORK_AUD } from './fixtures.js';
import type { ViKeyPair } from './keys.js';

const nowSeconds = (): number => Math.floor(Date.now() / 1000);
const asJwk = (jwk: Es256Jwk): Dict => ({ ...(jwk as unknown as Dict) });

// ---------------------------------------------------------------------------
// L1 — Issuer credential (Credentials Provider)
// ---------------------------------------------------------------------------

export interface IssueCredentialParams {
  /** User device public key bound into the credential via cnf.jwk. */
  userPublicJwk: Es256Jwk;
  /** Issuer (Credentials Provider) signing keypair. */
  issuer: ViKeyPair;
  /** Subject (cardholder) identifier. */
  sub: string;
  iss?: string;
  aud?: string | null;
  iat?: number;
  ttlSeconds?: number;
  email?: string | null;
  panLastFour?: string;
  scheme?: string;
}

/** Issue the Layer 1 issuer credential (binds the user's key). Returns serialized SD-JWT. */
export async function issueIssuerCredential(params: IssueCredentialParams): Promise<string> {
  const iat = params.iat ?? nowSeconds();
  const credential = new IssuerCredential({
    iss: params.iss ?? 'https://www.mastercard.com',
    sub: params.sub,
    iat,
    exp: iat + (params.ttlSeconds ?? 86400),
    aud: params.aud ?? 'https://wallet.example.com',
    cnfJwk: asJwk(params.userPublicJwk),
    email: params.email ?? null,
    panLastFour: params.panLastFour ?? '',
    scheme: params.scheme ?? 'Mastercard',
  });
  const l1 = await createLayer1(credential, params.issuer.privateKey, { kid: params.issuer.kid });
  return l1.serialize();
}

// ---------------------------------------------------------------------------
// L2 — User mandate, autonomous (human-not-present)
// ---------------------------------------------------------------------------

export interface AutonomousMandateParams {
  l1Serialized: string;
  user: ViKeyPair;
  /** Agent public key the user delegates to (bound via cnf.jwk). */
  agentPublicJwk: Es256Jwk;
  /** Agent kid — MUST equal the agent's L3 header kid. */
  agentKid: string;
  promptSummary: string;
  nonce?: string;
  aud?: string;
  iss?: string;
  iat?: number;
  ttlSeconds?: number;
  merchants: Dict[];
  acceptableItems: Dict[];
  paymentInstrument: Dict;
  riskData?: Dict | null;
  /** Amount range in minor units (cents). */
  amountMin: number;
  amountMax: number;
  currency?: string;
  /** Override the line-items constraint; defaults to one line of acceptableItems. */
  lineItems?: Dict[];
  recurrence?: { frequency: string; startDate: string; endDate?: string | null; number?: number | null };
}

/** Create the Layer 2 autonomous user mandate (open mandates + agent delegation). */
export async function createUserMandateAutonomous(params: AutonomousMandateParams): Promise<string> {
  const iat = params.iat ?? nowSeconds();
  const currency = params.currency ?? 'USD';

  const checkoutConstraints = [
    new AllowedMerchantConstraint({ allowed: params.merchants }),
    new CheckoutLineItemsConstraint({
      items: params.lineItems ?? [{ id: 'line-item-1', acceptable_items: params.acceptableItems, quantity: 1 }],
    }),
  ];

  const paymentConstraints: Constraint[] = [
    new PaymentAmountConstraint({ currency, min: params.amountMin, max: params.amountMax }),
    new AllowedPayeeConstraint({ allowed: params.merchants }),
  ];
  if (params.recurrence) {
    paymentConstraints.push(
      new PaymentRecurrenceConstraint({
        frequency: params.recurrence.frequency,
        startDate: params.recurrence.startDate,
        endDate: params.recurrence.endDate ?? null,
        number: params.recurrence.number ?? null,
      }),
    );
  }

  const mandate = new UserMandate({
    nonce: params.nonce ?? randomUUID(),
    aud: params.aud ?? 'https://agent.verifiable-intent.example',
    iat,
    iss: params.iss ?? 'https://wallet.example.com',
    exp: iat + (params.ttlSeconds ?? 86400),
    mode: MandateMode.AUTONOMOUS,
    sdHash: await hashAscii(params.l1Serialized),
    promptSummary: params.promptSummary,
    checkoutMandate: new CheckoutMandate({
      vct: 'mandate.checkout.open.1',
      cnfJwk: asJwk(params.agentPublicJwk),
      cnfKid: params.agentKid,
      constraints: checkoutConstraints,
    }),
    paymentMandate: new PaymentMandate({
      vct: 'mandate.payment.open.1',
      cnfJwk: asJwk(params.agentPublicJwk),
      cnfKid: params.agentKid,
      paymentInstrument: params.paymentInstrument,
      riskData: params.riskData ?? null,
      constraints: paymentConstraints,
    }),
    merchants: params.merchants,
    acceptableItems: params.acceptableItems,
  });

  const l2 = await createLayer2Autonomous(mandate, params.user.privateKey, { kid: params.user.kid });
  return l2.serialize();
}

// ---------------------------------------------------------------------------
// L2 — User mandate, immediate (human-present)
// ---------------------------------------------------------------------------

export interface ImmediateMandateParams {
  l1Serialized: string;
  user: ViKeyPair;
  checkoutJwt: string;
  paymentInstrument: Dict;
  payee: Dict;
  /** Amount in minor units (cents). */
  amount: number;
  currency?: string;
  nonce?: string;
  aud?: string;
  iss?: string;
  iat?: number;
  ttlSeconds?: number;
  promptSummary?: string | null;
}

/** Create the Layer 2 immediate user mandate (final values, no delegation, no L3). */
export async function createUserMandateImmediate(params: ImmediateMandateParams): Promise<string> {
  const iat = params.iat ?? nowSeconds();
  const checkoutHash = await checkoutHashFromJwt(params.checkoutJwt);

  const mandate = new UserMandate({
    nonce: params.nonce ?? randomUUID(),
    aud: params.aud ?? 'https://agent.verifiable-intent.example',
    iat,
    iss: params.iss ?? 'https://wallet.example.com',
    exp: iat + (params.ttlSeconds ?? 900),
    mode: MandateMode.IMMEDIATE,
    sdHash: await hashAscii(params.l1Serialized),
    promptSummary: params.promptSummary ?? null,
    checkoutMandate: new CheckoutMandate({
      vct: 'mandate.checkout.1',
      checkoutJwt: params.checkoutJwt,
      checkoutHash,
    }),
    paymentMandate: new PaymentMandate({
      vct: 'mandate.payment.1',
      paymentInstrument: params.paymentInstrument,
      payee: params.payee,
      currency: params.currency ?? 'USD',
      amount: params.amount,
      transactionId: checkoutHash,
    }),
  });

  const result = await createLayer2Immediate(mandate, params.user.privateKey, { kid: params.user.kid });
  return result.serialize();
}

// ---------------------------------------------------------------------------
// v1 human-present bridge — the userAuthorization envelope
// ---------------------------------------------------------------------------
//
// The v1 (human-present) AP2 flow has no L3: the shopping agent signs an
// immediate (2-layer) chain on the "user device" and carries it inline in the
// PaymentMandate's `userAuthorization` string; the merchant payment processor
// verifies it before the OTP challenge / payment execution. The envelope is a
// plain JSON string `{ l1, l2 }` of serialized SD-JWTs.
//
// AP2 amounts are MAJOR units (e.g. dollars); the VI mandate carries MINOR
// units (cents) — conversion happens here, at the AP2 boundary, mirroring the
// `Math.round(v * 100)` convention used by shopping-agent-v2.

export interface ImmediateUserAuthorizationParams {
  /** Issuer (Credentials Provider) signing keypair — L1. */
  issuer: ViKeyPair;
  /** User device signing keypair — L2. */
  user: ViKeyPair;
  /** Subject (cardholder) identifier for the L1 credential. */
  sub: string;
  /**
   * Merchant commitment to the cart the user saw (cartMandate.merchantAuthorization).
   * Bound into the L2 via the checkout hash (also the payment transaction id).
   */
  checkoutJwt: string;
  paymentInstrument: Dict;
  payee: Dict;
  /** AP2 amount in MAJOR units; converted to minor units for the VI mandate. */
  amountMajor: number;
  currency?: string;
  /** L2 audience — the payment network/PSP that verifies. Defaults to NETWORK_AUD. */
  aud?: string;
  nonce?: string;
  iat?: number;
  ttlSeconds?: number;
  promptSummary?: string | null;
}

/**
 * Sign a v1 human-present purchase: L1 issuer credential (binds the user key)
 * + L2 immediate user mandate (final amount/payee, bound to the checkout hash),
 * serialized as the `userAuthorization` envelope.
 */
export async function createImmediateUserAuthorization(
  params: ImmediateUserAuthorizationParams,
): Promise<string> {
  const l1 = await issueIssuerCredential({
    userPublicJwk: params.user.publicKey,
    issuer: params.issuer,
    sub: params.sub,
    iat: params.iat,
  });
  const l2 = await createUserMandateImmediate({
    l1Serialized: l1,
    user: params.user,
    checkoutJwt: params.checkoutJwt,
    paymentInstrument: params.paymentInstrument,
    payee: params.payee,
    amount: Math.round(params.amountMajor * 100),
    currency: params.currency,
    aud: params.aud ?? NETWORK_AUD,
    nonce: params.nonce,
    iat: params.iat,
    ttlSeconds: params.ttlSeconds,
    promptSummary: params.promptSummary,
  });
  return JSON.stringify({ l1, l2 });
}

export interface VerifyImmediateUserAuthorizationParams {
  /** The `userAuthorization` string from the AP2 PaymentMandate. */
  userAuthorization: string;
  issuerPublicJwk: Es256Jwk;
  /** Expected total from the AP2 PaymentMandate, in MAJOR units. */
  expectedAmountMajor?: number;
  expectedCurrency?: string;
  expectedPayeeName?: string;
  /**
   * base64url checkout hash of the cart the user saw
   * (checkoutHashFromJwt(merchantAuthorization)). When provided, the L2's bound
   * transaction id MUST equal it, so a swapped/tampered cart is rejected even
   * when amount and payee still match. Omit only when the verifier genuinely has
   * no access to the cart (in which case the cart binding is NOT enforced).
   */
  expectedCheckoutHash?: string;
  /** Pin the L2 audience; defaults to NETWORK_AUD (the signer stamps it). */
  expectedL2Aud?: string;
  expectedL2Nonce?: string;
  currentTime?: number;
}

export interface ImmediateVerificationOutcome {
  valid: boolean;
  errors: string[];
  /** Null when the envelope / SD-JWTs could not even be decoded. */
  result: ChainVerificationResult | null;
}

/**
 * Verify a v1 human-present `userAuthorization`: parse the envelope, verify the
 * immediate chain (L1 issuer signature, L2->L1 binding, L2 expiry, aud/nonce
 * pinning), then cross-check the L2's final payment values against the AP2
 * PaymentMandate (amount, currency, payee name) so a chain signed over a
 * different amount is rejected.
 */
export async function verifyImmediateUserAuthorization(
  params: VerifyImmediateUserAuthorizationParams,
): Promise<ImmediateVerificationOutcome> {
  let envelope: { l1?: unknown; l2?: unknown };
  try {
    envelope = JSON.parse(params.userAuthorization) as { l1?: unknown; l2?: unknown };
  } catch {
    return { valid: false, errors: ['userAuthorization is not a Verifiable Intent envelope'], result: null };
  }
  if (typeof envelope.l1 !== 'string' || typeof envelope.l2 !== 'string') {
    return { valid: false, errors: ['userAuthorization envelope missing l1/l2 credentials'], result: null };
  }

  let l1: SdJwt;
  let l2: SdJwt;
  try {
    l1 = decodeSdJwt(envelope.l1);
    l2 = decodeSdJwt(envelope.l2);
  } catch (e) {
    return { valid: false, errors: [`userAuthorization SD-JWT decode failed: ${String(e)}`], result: null };
  }

  // Fail closed: verifyChain and the disclosure/cross-check steps below can
  // throw (e.g. hashAscii on a non-ASCII checkout claim). A malicious shopping
  // agent holds the user key in this sample, so an escaping exception would be
  // an attacker-reachable framework crash instead of a structured rejection.
  let result: ChainVerificationResult;
  try {
    result = await verifyChain(l1, l2, {
      issuerPublicJwk: params.issuerPublicJwk,
      l1Serialized: envelope.l1,
      currentTime: params.currentTime,
      expectedL2Aud: params.expectedL2Aud ?? NETWORK_AUD,
      expectedL2Nonce: params.expectedL2Nonce,
    });
    if (!result.valid) {
      return { valid: false, errors: result.errors, result };
    }

    // Cross-check the L2's final payment values against the AP2 PaymentMandate.
    const l2Claims = await resolveDisclosures(l2);
    const delegates = (l2Claims.delegate_payload as Dict[] | undefined) ?? [];
    const payment = delegates.find(
      (d) => d && typeof d === 'object' && d.vct === 'mandate.payment.1',
    );
    if (!payment) {
      return { valid: false, errors: ['L2 carries no final payment mandate (mandate.payment.1)'], result };
    }

    const errors: string[] = [];
    const paymentAmount = payment.payment_amount as Dict | undefined;
    if (params.expectedAmountMajor !== undefined) {
      const expectedMinor = Math.round(params.expectedAmountMajor * 100);
      if (paymentAmount?.amount !== expectedMinor) {
        errors.push(
          `amount mismatch: user mandate authorizes ${String(paymentAmount?.amount)} minor units, ` +
            `payment mandate requests ${expectedMinor}`,
        );
      }
    }
    if (params.expectedCurrency !== undefined && paymentAmount?.currency !== params.expectedCurrency) {
      errors.push(
        `currency mismatch: user mandate authorizes ${String(paymentAmount?.currency)}, ` +
          `payment mandate requests ${params.expectedCurrency}`,
      );
    }
    if (params.expectedPayeeName !== undefined) {
      const payeeName = (payment.payee as Dict | undefined)?.name;
      // Compare case-insensitively: the signer canonicalizes merchant names
      // case-insensitively (resolvePayee), so a strict compare would reject
      // legitimately-signed mandates whose payee only differs in case.
      if (String(payeeName).toLowerCase() !== params.expectedPayeeName.toLowerCase()) {
        errors.push(
          `payee mismatch: user mandate authorizes '${String(payeeName)}', ` +
            `payment mandate requests '${params.expectedPayeeName}'`,
        );
      }
    }
    // Bind the authorization to the exact cart the user saw: the L2 payment
    // mandate's transaction id is checkoutHashFromJwt(merchantAuthorization).
    if (params.expectedCheckoutHash !== undefined) {
      const txnId = payment.transaction_id;
      if (txnId !== params.expectedCheckoutHash) {
        errors.push(
          `checkout hash mismatch: user mandate is bound to '${String(txnId)}', ` +
            `expected '${params.expectedCheckoutHash}'`,
        );
      }
    }

    return { valid: errors.length === 0, errors, result };
  } catch (e) {
    return {
      valid: false,
      errors: [`user authorization verification failed: ${String(e)}`],
      result: null,
    };
  }
}

// ---------------------------------------------------------------------------
// L3 — Agent fulfillment (split L3a payment + L3b checkout) + selective routing
// ---------------------------------------------------------------------------

/** Find the disclosure string in an L2 whose resolved object value matches `predicate`. */
function findDisclosure(l2: SdJwt, predicate: (value: Dict) => boolean): string | null {
  for (let i = 0; i < l2.disclosures.length; i++) {
    const dv = l2.disclosureValues[i];
    const value = dv.length ? dv[dv.length - 1] : null;
    if (value && typeof value === 'object' && !Array.isArray(value) && predicate(value as Dict)) {
      return l2.disclosures[i];
    }
  }
  return null;
}

export interface AgentFulfillmentParams {
  l2Serialized: string;
  agent: ViKeyPair;
  checkoutJwt: string;
  checkoutHash: string;
  /** The chosen merchant (must be one of the mandate's merchants). */
  payee: Dict;
  /** The chosen item id / sku (must be an acceptable item). */
  itemId: string;
  /** Amount in minor units (cents). */
  amount: number;
  currency?: string;
  paymentInstrument: Dict;
  networkAud?: string;
  merchantAud?: string;
  nonce?: string;
  iat?: number;
  ttlSeconds?: number;
}

export interface AgentFulfillment {
  /** L3a — payment fulfillment for the network. */
  l3PaymentSerialized: string;
  /** L3b — checkout fulfillment for the merchant. */
  l3CheckoutSerialized: string;
  /** L2 presentation the network sees (payment + merchant disclosures). */
  l2PaymentSerialized: string;
  /** L2 presentation the merchant sees (checkout + item disclosures). */
  l2CheckoutSerialized: string;
}

/** Agent builds the split L3 credentials and the per-recipient L2 presentations. */
export async function createAgentFulfillment(params: AgentFulfillmentParams): Promise<AgentFulfillment> {
  const iat = params.iat ?? nowSeconds();
  const exp = iat + (params.ttlSeconds ?? 300);
  const nonce = params.nonce ?? randomUUID();

  const l2 = decodeSdJwt(params.l2Serialized);
  const l2BaseJwt = params.l2Serialized.split('~')[0];

  const paymentDisc = findDisclosure(l2, (v) => v.vct === 'mandate.payment.open.1');
  const checkoutDisc = findDisclosure(l2, (v) => v.vct === 'mandate.checkout.open.1');
  const merchantDisc = findDisclosure(l2, (v) =>
    Boolean(v.website) && (params.payee.id ? v.id === params.payee.id : v.name === params.payee.name),
  );
  const itemDisc = findDisclosure(l2, (v) => v.id === params.itemId || v.sku === params.itemId);

  if (!paymentDisc || !checkoutDisc || !merchantDisc || !itemDisc) {
    throw new Error(
      `Missing L2 disclosures (payment=${Boolean(paymentDisc)} checkout=${Boolean(checkoutDisc)} ` +
        `merchant=${Boolean(merchantDisc)} item=${Boolean(itemDisc)})`,
    );
  }

  // L3a — payment, for the network.
  const l3aMandate = new PaymentL3Mandate({
    nonce,
    aud: params.networkAud ?? NETWORK_AUD,
    iat,
    iss: 'https://agent.example.com',
    exp,
    finalPayment: new FinalPaymentMandate({
      transactionId: params.checkoutHash,
      payee: params.payee,
      paymentAmount: { currency: params.currency ?? 'USD', amount: params.amount },
      paymentInstrument: params.paymentInstrument,
    }),
    finalMerchant: params.payee,
  });
  const l3a = await createLayer3Payment(
    l3aMandate,
    params.agent.privateKey,
    { l2BaseJwt, paymentDisclosure: paymentDisc, merchantDisclosure: merchantDisc },
    { kid: params.agent.kid },
  );

  // L3b — checkout, for the merchant.
  const l3bMandate = new CheckoutL3Mandate({
    nonce,
    aud: params.merchantAud ?? MERCHANT_AUD,
    iat,
    iss: 'https://agent.example.com',
    exp,
    finalCheckout: new FinalCheckoutMandate({ checkoutJwt: params.checkoutJwt, checkoutHash: params.checkoutHash }),
  });
  const l3b = await createLayer3Checkout(
    l3bMandate,
    params.agent.privateKey,
    { l2BaseJwt, checkoutDisclosure: checkoutDisc, itemDisclosure: itemDisc },
    { kid: params.agent.kid },
  );

  const l2PaymentSerialized = buildSelectivePresentation(l2BaseJwt, [paymentDisc, merchantDisc]);
  const l2CheckoutSerialized = buildSelectivePresentation(l2BaseJwt, [checkoutDisc, itemDisc]);

  return {
    l3PaymentSerialized: l3a.serialize(),
    l3CheckoutSerialized: l3b.serialize(),
    l2PaymentSerialized,
    l2CheckoutSerialized,
  };
}

// ---------------------------------------------------------------------------
// Verification — Merchant (checkout side)
// ---------------------------------------------------------------------------

export interface VerifyCheckoutParams {
  l1Serialized: string;
  /** L2 presentation the merchant received (checkout + item disclosures). */
  l2CheckoutSerialized: string;
  l3CheckoutSerialized: string;
  issuerPublicJwk: Es256Jwk;
  /** Full L2 serialization (for pairing); defaults to the checkout presentation. */
  l2Serialized?: string;
  currentTime?: number;
  expectedL3CheckoutAud?: string;
  expectedL3CheckoutNonce?: string;
}

/** Merchant verifies the checkout-side chain (L1 → L2 → L3b). */
export async function verifyCheckoutChain(params: VerifyCheckoutParams): Promise<ChainVerificationResult> {
  const l1 = decodeSdJwt(params.l1Serialized);
  const l2 = decodeSdJwt(params.l2CheckoutSerialized);
  const l3Checkout = decodeSdJwt(params.l3CheckoutSerialized);
  return verifyChain(l1, l2, {
    l3Checkout,
    issuerPublicJwk: params.issuerPublicJwk,
    l1Serialized: params.l1Serialized,
    l2Serialized: params.l2Serialized ?? params.l2CheckoutSerialized,
    l2CheckoutSerialized: params.l2CheckoutSerialized,
    currentTime: params.currentTime,
    expectedL3CheckoutAud: params.expectedL3CheckoutAud,
    expectedL3CheckoutNonce: params.expectedL3CheckoutNonce,
  });
}

// ---------------------------------------------------------------------------
// Verification — Network / PSP (payment side) + constraint enforcement
// ---------------------------------------------------------------------------

export interface VerifyPaymentParams {
  l1Serialized: string;
  /** L2 presentation the network received (payment + merchant disclosures). */
  l2PaymentSerialized: string;
  l3PaymentSerialized: string;
  issuerPublicJwk: Es256Jwk;
  /** Full L2 serialization (for pairing); defaults to the payment presentation. */
  l2Serialized?: string;
  currentTime?: number;
  expectedL3PaymentAud?: string;
  expectedL3PaymentNonce?: string;
}

export interface PaymentVerificationOutcome {
  valid: boolean;
  errors: string[];
  result: ChainVerificationResult;
  constraints: ConstraintCheckResult | null;
}

/** Network verifies the payment-side chain (L1 → L2 → L3a) and enforces constraints (STRICT). */
export async function verifyPaymentChainAndConstraints(
  params: VerifyPaymentParams,
): Promise<PaymentVerificationOutcome> {
  const l1 = decodeSdJwt(params.l1Serialized);
  const l2 = decodeSdJwt(params.l2Serialized ?? params.l2PaymentSerialized);
  const l3Payment = decodeSdJwt(params.l3PaymentSerialized);

  const result = await verifyChain(l1, l2, {
    l3Payment,
    issuerPublicJwk: params.issuerPublicJwk,
    l1Serialized: params.l1Serialized,
    l2Serialized: params.l2Serialized ?? params.l2PaymentSerialized,
    l2PaymentSerialized: params.l2PaymentSerialized,
    currentTime: params.currentTime,
    expectedL3PaymentAud: params.expectedL3PaymentAud,
    expectedL3PaymentNonce: params.expectedL3PaymentNonce,
  });

  if (!result.valid) {
    return { valid: false, errors: result.errors, result, constraints: null };
  }

  const constraints = await enforcePaymentConstraints(l2, result);
  if (constraints === null) {
    // No payment constraints present (e.g. immediate mode) — chain validity stands.
    return { valid: true, errors: [], result, constraints: null };
  }
  return {
    valid: constraints.satisfied,
    errors: constraints.satisfied ? [] : constraints.violations,
    result,
    constraints,
  };
}

/**
 * Resolve L2 payment constraints + L3 fulfillment and run the constraint checker
 * in STRICT mode (payment networks MUST treat unknown constraints as violations).
 * Port of python/examples/helpers.py `validate_intent` / autonomous_flow step 8.
 * Returns null when the L2 carries no payment constraints.
 */
async function enforcePaymentConstraints(l2: SdJwt, result: ChainVerificationResult): Promise<ConstraintCheckResult | null> {
  const l2Claims = await resolveDisclosures(l2);
  const delegates = (l2Claims.delegate_payload as Dict[] | undefined) ?? [];

  let paymentConstraints: Dict[] = [];
  for (const delegate of delegates) {
    if (
      delegate &&
      typeof delegate === 'object' &&
      (delegate.vct === 'mandate.payment.open.1' || delegate.vct === 'mandate.payment.1')
    ) {
      paymentConstraints = (delegate.constraints as Dict[] | undefined) ?? [];
      break;
    }
  }
  if (paymentConstraints.length === 0) {
    return null;
  }

  let fulfillment: Dict = {};
  for (const delegate of (result.l3PaymentClaims.delegate_payload as Dict[] | undefined) ?? []) {
    if (delegate && typeof delegate === 'object' && delegate.vct === 'mandate.payment.1') {
      fulfillment = { ...delegate };
      break;
    }
  }

  // Resolve allowed_payees SD-refs into concrete merchant objects for the checker.
  const discByHash = new Map<string, unknown[]>();
  for (let i = 0; i < l2.disclosures.length; i++) {
    discByHash.set(await hashDisclosure(l2.disclosures[i]), l2.disclosureValues[i]);
  }
  for (const constraint of paymentConstraints) {
    if (constraint.type === 'mandate.payment.allowed_payees') {
      const resolved: unknown[] = [];
      for (const ref of (constraint.allowed as unknown[] | undefined) ?? []) {
        const refHash = ref && typeof ref === 'object' ? ((ref as Dict)['...'] as string) : '';
        if (refHash && discByHash.has(refHash)) {
          const dv = discByHash.get(refHash)!;
          resolved.push(dv[dv.length - 1]);
        }
      }
      fulfillment.allowed_merchants = resolved;
      break;
    }
  }

  return checkConstraints(paymentConstraints, fulfillment, { mode: StrictnessMode.STRICT });
}
