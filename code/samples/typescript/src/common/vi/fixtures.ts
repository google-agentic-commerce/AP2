/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Scenario fixtures for the Verifiable Intent flow — a direct port of the
 * `verifiable_intent` Python reference examples (python/examples/helpers.py):
 * a tennis-racket purchase across two acceptable merchants. These define the
 * canonical catalog, merchant allowlist, acceptable items and payment
 * instrument used by the autonomous (3-layer) and immediate (2-layer) flows.
 */

import type { Dict } from '@verifiable-intent/core';

/** Merchant allowlist — carried into the open mandate constraints + disclosures. */
export const MERCHANTS: Dict[] = [
  { id: 'merchant-uuid-1', name: 'Tennis Warehouse', website: 'https://tennis-warehouse.com' },
  { id: 'merchant-uuid-2', name: 'Babolat', website: 'https://babolat.com' },
];

/** Acceptable items — the user's line-item constraint references these by id. */
export const ACCEPTABLE_ITEMS: Dict[] = [
  { id: 'BAB86345', title: 'Babolat Pure Aero Tennis Racket' },
  { id: 'HEA23102', title: 'Head Graphene 360 Speed' },
];

export interface Product {
  sku: string;
  name: string;
  /** Price in minor units (cents). */
  price: number;
  currency: string;
  brand: string;
  model: string;
  color: string;
  size: number;
  sizeLabel: string;
  category: string;
}

export const PRODUCTS: Product[] = [
  {
    sku: 'BAB86345',
    name: 'Babolat Pure Aero Tennis Racket',
    price: 27999,
    currency: 'USD',
    brand: 'Babolat',
    model: 'Pure Aero',
    color: 'white',
    size: 3,
    sizeLabel: '4 3/8',
    category: 'racket',
  },
  {
    sku: 'HEA23102',
    name: 'Head Graphene 360 Speed Tennis Racket',
    price: 24999,
    currency: 'USD',
    brand: 'HEAD',
    model: 'Speed Pro',
    color: 'black',
    size: 3,
    sizeLabel: '4 3/8',
    category: 'racket',
  },
];

/** Mastercard digital card payment instrument (matches the Python reference). */
export const PAYMENT_INSTRUMENT: Dict = {
  type: 'mastercard.srcDigitalCard',
  id: 'f199c3dd-7106-478b-9b5f-7af9ca725170',
  description: 'Mastercard **** 1234',
};

export function getCatalog(): Product[] {
  return PRODUCTS;
}

export function findProduct(sku: string): Product | undefined {
  return PRODUCTS.find((p) => p.sku === sku);
}
