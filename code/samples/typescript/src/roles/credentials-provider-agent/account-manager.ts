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
 * An in-memory manager of a user's 'account details'.
 *
 * Each 'account' contains a user's payment methods and shipping address.
 * For demonstration purposes, several accounts are pre-populated with sample data.
 *
 * Token creation issues SD-JWT payment credentials signed with the
 * credentials-provider's ES256 key (AP2 v0.2). Sensitive payment method
 * fields are made selectively disclosable.
 */
import {
  issueOpenMandate,
  verifyMandate,
  generateKeyPair,
  type Es256KeyPair,
} from '../../common/sdjwt/index.js';

export type PaymentMethod = {
  type: string;
  alias: string;
  network?: { name?: string; formats?: string[] }[];
  cryptogram?: string;
  token?: string;
  card_holder_name?: string;
  card_expiration?: string;
  card_billing_address?: { country?: string; postal_code?: string };
  account_number?: string;
  brand?: string;
  account_identifier?: string;
};

type Account = {
  shipping_address?: {
    recipient: string;
    organization?: string;
    address_line: string[];
    city: string;
    region: string;
    postal_code: string;
    country: string;
    phone_number: string;
  };
  payment_methods: {
    [key: string]: PaymentMethod;
  };
};

const accountDb: { [email: string]: Account } = {
  // Default demo account used when no user email has been collected.
  "user@example.com": {
    shipping_address: {
      recipient: "Demo User",
      address_line: ["123 Main St"],
      city: "San Francisco",
      region: "CA",
      postal_code: "94105",
      country: "US",
      phone_number: "+14155551234",
    },
    payment_methods: {
      card1: {
        type: "CARD",
        alias: "Visa ending in 4242",
        network: [{ name: "visa", formats: ["DPAN"] }],
        cryptogram: "fake_cryptogram_demo",
        token: "4242000000004242",
        card_holder_name: "Demo User",
        card_expiration: "12/2030",
        card_billing_address: {
          country: "US",
          postal_code: "94105",
        },
      },
    },
  },
  "bugsbunny@gmail.com": {
    shipping_address: {
      recipient: "Bugs Bunny",
      organization: "Sample Organization",
      address_line: ["123 Main St"],
      city: "Sample City",
      region: "ST",
      postal_code: "00000",
      country: "US",
      phone_number: "+1-000-000-0000",
    },
    payment_methods: {
      card1: {
        type: "CARD",
        alias: "American Express ending in 4444",
        network: [{ name: "amex", formats: ["DPAN"] }],
        cryptogram: "fake_cryptogram_abc123",
        token: "1111000000000000",
        card_holder_name: "John Doe",
        card_expiration: "12/2028",
        card_billing_address: {
          country: "US",
          postal_code: "00000",
        },
      },
      card2: {
        type: "CARD",
        alias: "American Express ending in 8888",
        network: [{ name: "amex", formats: ["DPAN"] }],
        cryptogram: "fake_cryptogram_ghi789",
        token: "2222000000000000",
        card_holder_name: "Bugs Bunny",
        card_expiration: "10/2027",
        card_billing_address: {
          country: "US",
          postal_code: "00000",
        },
      },
      bank_account1: {
        type: "BANK_ACCOUNT",
        account_number: "111",
        alias: "Primary bank account",
      },
      digital_wallet1: {
        type: "DIGITAL_WALLET",
        brand: "PayPal",
        account_identifier: "foo@bar.com",
        alias: "Bugs's PayPal account",
      },
    },
  },
  "daffyduck@gmail.com": {
    payment_methods: {
      bank_account1: {
        type: "BANK_ACCOUNT",
        brand: "Bank of Money",
        account_number: "789",
        alias: "Main checking account",
      },
    },
  },
  "elmerfudd@gmail.com": {
    payment_methods: {
      digital_wallet1: {
        type: "DIGITAL_WALLET",
        brand: "PayPal",
        account_identifier: "elmerfudd@gmail.com",
        alias: "Fudd's PayPal",
      },
    },
  },
};

/**
 * Token store: maps a serialized SD-JWT (the "token" string) to its metadata.
 * The SD-JWT itself is the token — it cryptographically binds the payment
 * method to the issuer. The store tracks the mandate association.
 */
const tokens: {
  [token: string]: {
    emailAddress: string;
    paymentMethodAlias: string;
    paymentMandateId: string | null;
  };
} = {};

/**
 * The credentials-provider's ES256 issuer keypair. Used to sign payment
 * credential SD-JWTs and to verify them on the way back. The same keypair's
 * public key is also bound into `cnf.jwk` as the holder key for these demo
 * tokens (no separate holder key is involved at issuance time).
 */
let issuerKey: Es256KeyPair | null = null;

/**
 * Initializes the issuer ES256 keypair. Idempotent — repeated calls after the
 * first are no-ops, so it is safe to invoke during server boot.
 */
export async function initIssuerKey(): Promise<void> {
  if (issuerKey) {
    return;
  }
  issuerKey = await generateKeyPair();
}

/**
 * Returns the initialized issuer keypair.
 *
 * @throws Error if {@link initIssuerKey} has not been called yet.
 */
function getIssuerKey(): Es256KeyPair {
  if (!issuerKey) {
    throw new Error('Issuer key not initialized. Call initIssuerKey() first.');
  }
  return issuerKey;
}

/**
 * Payment method fields that carry sensitive data and should be made
 * selectively disclosable in the issued SD-JWT.
 */
const DISCLOSABLE_FIELDS = [
  'cryptogram',
  'token',
  'card_holder_name',
  'card_expiration',
  'card_billing_address',
  'account_number',
  'account_identifier',
];

/**
 * Creates a token for an account by issuing an SD-JWT payment credential.
 *
 * The SD-JWT embeds the payment method data as claims and is signed with the
 * credentials-provider's ES256 issuer key. Sensitive payment method fields are
 * made selectively disclosable. The serialized SD-JWT string serves as the
 * token.
 *
 * @param emailAddress - The email address of the account.
 * @param paymentMethodAlias - The alias of the payment method.
 * @returns The serialized SD-JWT token for the payment method.
 */
export const createToken = async (
  emailAddress: string,
  paymentMethodAlias: string
): Promise<string> => {
  const paymentMethod = getPaymentMethodByAlias(emailAddress, paymentMethodAlias);
  if (!paymentMethod) {
    throw new Error(
      `Payment method "${paymentMethodAlias}" not found for ${emailAddress}`
    );
  }

  const key = getIssuerKey();

  // Build the claim set from the payment method fields plus credential
  // metadata. The credential `type` claim ("PaymentCredential") shadows the
  // payment method's own `type` field (e.g. "CARD"), so the latter is
  // preserved under `payment_method_type` and restored on verification.
  const claims: Record<string, unknown> = {
    ...(paymentMethod as unknown as Record<string, unknown>),
    payment_method_type: paymentMethod.type,
    sub: `mailto:${emailAddress}`,
    payment_method_alias: paymentMethodAlias,
    type: 'PaymentCredential',
    iat: Math.floor(Date.now() / 1000),
  };

  // Only the sensitive fields actually present on this payment method are
  // declared as selectively disclosable.
  const disclosable = DISCLOSABLE_FIELDS.filter((field) => field in claims);

  // Issue an SD-JWT payment credential signed by the issuer key. The issuer's
  // public key is also bound as the holder key (cnf.jwk).
  const token = await issueOpenMandate({
    claims,
    disclosable,
    issuerPrivateJwk: key.privateKey,
    holderPublicJwk: key.publicKey,
  });

  tokens[token] = {
    emailAddress,
    paymentMethodAlias,
    paymentMandateId: null,
  };

  return token;
};

/**
 * Updates the token with the payment mandate id.
 *
 * @param token - The token (serialized VC) to update.
 * @param paymentMandateId - The payment mandate id to associate with the token.
 */
export const updateToken = (token: string, paymentMandateId: string): void => {
  if (!(token in tokens)) {
    throw new Error(`Token ${token} not found`);
  }
  if (tokens[token].paymentMandateId) {
    // Do not overwrite the payment mandate id if it is already set.
    return;
  }
  tokens[token].paymentMandateId = paymentMandateId;
};

/**
 * Verify a token (serialized SD-JWT) and return the payment method.
 *
 * Performs cryptographic verification of the SD-JWT issuer signature, checks
 * the in-memory mandate binding, and reconstructs the payment method from the
 * verified claims.
 *
 * @param token - The serialized SD-JWT token.
 * @param paymentMandateId - The payment mandate id associated with the token.
 * @returns The payment method extracted from the verified SD-JWT.
 * @throws Error if the token is invalid or the mandate doesn't match.
 */
export const verifyToken = async (
  token: string,
  paymentMandateId: string
): Promise<PaymentMethod | null> => {
  // Check the token store for mandate binding
  const accountLookup = tokens[token];
  if (!accountLookup) {
    throw new Error("Invalid token");
  }
  if (accountLookup.paymentMandateId !== paymentMandateId) {
    throw new Error("Invalid token");
  }

  const key = getIssuerKey();

  // Cryptographically verify the SD-JWT issuer signature.
  const { payload } = await verifyMandate({
    mandateSdJwt: token,
    issuerPublicJwk: key.publicKey,
  });

  // Reconstruct the PaymentMethod from the verified claims. Strip the
  // credential metadata (sub, payment_method_alias, type, iat) and the
  // holder-binding `cnf` claim. The credential `type` ("PaymentCredential")
  // is dropped; the payment method's own `type` (e.g. "CARD") was stashed in
  // `payment_method_type` at issuance and is restored here.
  const {
    sub: _sub,
    payment_method_alias: _alias,
    type: _credentialType,
    iat: _iat,
    cnf: _cnf,
    payment_method_type: paymentMethodType,
    ...rest
  } = payload;
  const paymentMethodData: Record<string, unknown> = { ...rest };
  if (paymentMethodType !== undefined) {
    paymentMethodData.type = paymentMethodType;
  }
  return paymentMethodData as unknown as PaymentMethod;
};

/**
 * Returns a list of the payment methods for the given account email address.
 *
 * @param emailAddress - The account's email address.
 * @returns A list of the user's payment_methods.
 */
export const getAccountPaymentMethods = (
  emailAddress: string
): PaymentMethod[] => {
  const account = accountDb[emailAddress];
  if (!account || !account.payment_methods) {
    return [];
  }
  return Object.values(account.payment_methods);
};

/**
 * Gets the shipping address associated for the given account email address.
 *
 * @param emailAddress - The account's email address.
 * @returns The account's shipping address.
 */
export const getAccountShippingAddress = (
  emailAddress: string
): Account["shipping_address"] | null => {
  const account = accountDb[emailAddress];
  return account?.shipping_address || null;
};

/**
 * Returns the payment method for a given account and alias.
 *
 * @param emailAddress - The account's email address.
 * @param alias - The alias of the payment method to retrieve.
 * @returns The payment method for the given account and alias, or null if not found.
 */
export const getPaymentMethodByAlias = (
  emailAddress: string,
  alias: string
): PaymentMethod | null => {
  const paymentMethods = getAccountPaymentMethods(emailAddress).filter(
    (paymentMethod) => paymentMethod.alias.toLowerCase() === alias.toLowerCase()
  );

  if (paymentMethods.length === 0) {
    return null;
  }

  return paymentMethods[0];
};
