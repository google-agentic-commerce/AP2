/**
 * An in-memory manager of a user's 'account details'.
 *
 * Each 'account' contains a user's payment methods and shipping address.
 * For demonstration purposes, several accounts are pre-populated with sample data.
 */

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
        card_expiration: "12/2025",
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

const tokens: {
  [token: string]: {
    emailAddress: string;
    paymentMethodAlias: string;
    paymentMandateId: string | null;
  };
} = {};

/**
 * Creates and stores a token for an account.
 *
 * @param emailAddress - The email address of the account.
 * @param paymentMethodAlias - The alias of the payment method.
 * @returns The token for the payment method.
 */
export const createToken = (
  emailAddress: string,
  paymentMethodAlias: string
): string => {
  const token = `fake_payment_credential_token_${Object.keys(tokens).length}`;
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
 * @param token - The token to update.
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
 * Look up an account by token.
 *
 * @param token - The token for look up.
 * @param paymentMandateId - The payment mandate id associated with the token.
 * @returns The account for the given token.
 * @throws Error if the token is not valid.
 */
export const verifyToken = (
  token: string,
  paymentMandateId: string
): PaymentMethod | null => {
  const accountLookup = tokens[token];
  if (!accountLookup) {
    throw new Error("Invalid token");
  }
  if (accountLookup.paymentMandateId !== paymentMandateId) {
    throw new Error("Invalid token");
  }
  const emailAddress = accountLookup.emailAddress;
  const paymentMethodAlias = accountLookup.paymentMethodAlias;
  return getPaymentMethodByAlias(emailAddress, paymentMethodAlias);
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
