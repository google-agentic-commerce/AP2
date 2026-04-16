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

/**
 * Custom JSON-LD context for AP2 payment credential terms.
 *
 * This defines the vocabulary for payment method properties used in
 * PaymentCredential VCs so that JSON-LD expansion/canonicalization
 * can handle them without "safe mode" validation errors.
 */

export const AP2_CONTEXT_URL = 'https://ap2.example/contexts/payment/v1';

/**
 * The AP2 payment context document. Maps AP2-specific terms to a
 * local vocabulary namespace so they are recognized by JSON-LD processors.
 */
export const ap2PaymentContext = {
  '@context': {
    '@vocab': 'https://ap2.example/vocab#',
    PaymentCredential: 'https://ap2.example/vocab#PaymentCredential',
    PaymentMethod: 'https://ap2.example/vocab#PaymentMethod',
    alias: 'https://ap2.example/vocab#alias',
    network: 'https://ap2.example/vocab#network',
    cryptogram: 'https://ap2.example/vocab#cryptogram',
    token: 'https://ap2.example/vocab#token',
    card_holder_name: 'https://ap2.example/vocab#card_holder_name',
    card_expiration: 'https://ap2.example/vocab#card_expiration',
    card_billing_address: 'https://ap2.example/vocab#card_billing_address',
    account_number: 'https://ap2.example/vocab#account_number',
    brand: 'https://ap2.example/vocab#brand',
    account_identifier: 'https://ap2.example/vocab#account_identifier',
    postal_code: 'https://ap2.example/vocab#postal_code',
    country: 'https://ap2.example/vocab#country',
    paymentMandateId: 'https://ap2.example/vocab#paymentMandateId',
  },
};
