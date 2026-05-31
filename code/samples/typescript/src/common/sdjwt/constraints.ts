/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Minimal mandate-constraint checker (amount + merchant allowlist), a TS
 * subset of the Python ap2 constraint engine. The open mandate carries the
 * constraints; this module checks an observed price/merchant against them.
 */

export interface ObservedTransaction {
  /** Observed unit price, in the same units as the constraint cap (USD dollars here). */
  price: number;
  currency?: string;
  /** Merchant identifier/name for the observed offer, if known. */
  merchant?: string;
}

export interface MandateConstraints {
  /** Maximum acceptable price (inclusive), in the same units as the observed price. */
  priceCap?: number;
  currency?: string;
  /** If non-empty, the merchant of the offer must be one of these. */
  allowedMerchants?: string[];
}

export interface ConstraintResult {
  meetsConstraints: boolean;
  violations: string[];
}

/** Check an observed transaction against the open-mandate constraints. */
export function checkConstraints(
  observed: ObservedTransaction,
  constraints: MandateConstraints,
): ConstraintResult {
  const violations: string[] = [];

  // Amount bound (inclusive).
  if (constraints.priceCap !== undefined && observed.price > constraints.priceCap) {
    violations.push(
      `price ${observed.price} exceeds cap ${constraints.priceCap}`,
    );
  }

  // Currency match (only when both sides specify one).
  if (
    constraints.currency &&
    observed.currency &&
    constraints.currency !== observed.currency
  ) {
    violations.push(
      `currency ${observed.currency} != allowed ${constraints.currency}`,
    );
  }

  // Merchant allowlist (only enforced when the mandate restricts merchants).
  if (constraints.allowedMerchants && constraints.allowedMerchants.length > 0) {
    const merchant = observed.merchant;
    if (!merchant) {
      violations.push('merchant unknown but mandate restricts merchants');
    } else if (
      !constraints.allowedMerchants.some(
        (m) => m.toLowerCase() === merchant.toLowerCase(),
      )
    ) {
      violations.push(`merchant ${merchant} not in allowlist`);
    }
  }

  return { meetsConstraints: violations.length === 0, violations };
}
