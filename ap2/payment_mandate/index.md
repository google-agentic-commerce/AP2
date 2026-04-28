# Payment Mandate

The Payment Mandate is a Mandate used for authorizing the payment for a particular checkout.

## Usage

The Payment Mandate Content is created by the Shopping Agent, rendered to the User by the Trusted Surface and verified by the Credential Provider, Network, and Merchant Payment Processor.

## Type

A closed Payment Mandate MUST use the value `mandate.payment.1` for the `vct` claim, and an open Payment Mandate MUST use the value `mandate.payment.open.1`.

See [Mandate Versioning](../specification/#mandate-versioning) for how the version suffix works.

## Mandate Schema

The closed Payment Mandate conforms to the following schema:

| Name               | Type                                    | Required | Description                                                                                                                                                                                                         |
| ------------------ | --------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| vct                | string                                  | **Yes**  | Verifiable Credential Type claim as defined in SD-JWT. MUST be 'mandate.payment'.                                                                                                                                   |
| transaction_id     | string                                  | **Yes**  | base64url-encoded hash of the checkout_jwt field value, uniquely identifying the checkout associated with this. The hash algorithm used MUST be the same as the sd_hash field for this sd-jwt, or sha256 if absent. |
| payee              | [Merchant](#merchant)                   | **Yes**  | The merchant receiving the payment.                                                                                                                                                                                 |
| pisp               | [Pisp](#pisp)                           | No       | The Payment Initiation Service Provider.                                                                                                                                                                            |
| payment_amount     | [Amount](#amount)                       | **Yes**  | Transaction amount object containing currency (ISO 4217 code, e.g., "USD") and amount (integer minor units per ISO 4217, e.g., 27999 = $279.99). Final value confirmed by the user.                                 |
| payment_instrument | [PaymentInstrument](#paymentinstrument) | **Yes**  | The payment instrument used.                                                                                                                                                                                        |
| execution_date     | string                                  | No       | ISO8601 date of execution of payment. When absent indicates immediate execution.                                                                                                                                    |
| risk_data          | object                                  | No       | An map of relevant risk signals collected by the trusted surface at time of mandate creation.                                                                                                                       |
| iat                | integer                                 | No       | The creation timestamp as a Unix epoch.                                                                                                                                                                             |
| exp                | integer                                 | No       | The expiration timestamp as a Unix epoch.                                                                                                                                                                           |

The open Payment Mandate MAY optionally include any property from the closed Payment Mandate.

### Payment Mandate Constraints

The following constraints are defined for Payment Mandates in this document:

- **Agent Recurrence:** Provides conditions for the agent reusing this Payment Mandate multiple times.
- **Allowed Payee:** Constrains the payee to one of a set of possible Merchants.
- **Allowed Payment Instrument:** Constrains the payment instrument to one of a set of possible payment instruments.
- **Allowed Payment Initiation Service Provider (PISP):** Constrains the PISP to one of a set of possible PISPs.
- **Amount Range:** Constrains the amount to be within a range.
- **Budget:** Provides a total amount limit. To be used with the Agent Recurrence constraint.
- **Reference:** Constraints the Payment Mandate to its associated open Checkout Mandate, and Checkout Mandates chained from it.
- **Execution Date:** Constrains the execution date to a specific range.

### Agent Recurrence

**Type**: `payment.agent_recurrence`

**Description**: Provides conditions for the agent to reuse this Payment Mandate multiple times.

**Properties**:

| Name            | Type    | Required | Description                                                                                                                |
| --------------- | ------- | -------- | -------------------------------------------------------------------------------------------------------------------------- |
| type            | string  | **Yes**  | Constraint type identifier.                                                                                                |
| frequency       | string  | **Yes**  | Frequency of allowed recurrences. **Enum:** `ON_DEMAND`, `DAILY`, `WEEKLY`, `BIWEEKLY`, `MONTHLY`, `QUARTERLY`, `ANNUALLY` |
| max_occurrences | integer | No       | Maximum number of allowed occurrences.                                                                                     |

**Evaluation**: Evaluating the budget requires tracking the previous presentations of Payment Mandates associated with this open one. This constraint evaluates as true if the current Payment Mandate is sufficiently separated in time from the previous presentation to meet the `frequency` definition, and the `max_occurrences` limit is greater than or equal to the current occurrences.

**Example**

```json
{
  "type": "payment.agent_recurrence",
  "frequency": "MONTHLY",
  "max_occurrences": 12
}
```

### Allowed Payees

**Type**: `payment.allowed_payees`

**Description**: Defines the set of possible payees for this Payment Mandate.

**Properties**:

| Name    | Type                           | Required | Selectively Disclosable | Description                        |
| ------- | ------------------------------ | -------- | ----------------------- | ---------------------------------- |
| type    | string                         | **Yes**  | No                      | Constraint type identifier.        |
| allowed | Array\[[Merchant](#merchant)\] | **Yes**  | Yes                     | Array of allowed Merchant objects. |

**Evaluation**: The `payee` property of the Payment Mandate MUST be present in the `allowed` array.

**Example**

```json
{
  "type": "payment.allowed_payees",
  "allowed": [
    {
      "name": "Merchant Choice",
      "website": "https://merchant-choice.com"
    }
  ]
}
```

### Allowed Payment Instruments

**Type**: `payment.allowed_payment_instruments`

**Description**: Defines the set of possible payment instruments for this Payment Mandate.

**Properties**:

| Name    | Type                                             | Required | Selectively Disclosable | Description                           |
| ------- | ------------------------------------------------ | -------- | ----------------------- | ------------------------------------- |
| type    | string                                           | **Yes**  | No                      | Constraint type identifier.           |
| allowed | Array\[[PaymentInstrument](#paymentinstrument)\] | **Yes**  | Yes                     | Array of allowed payment instruments. |

**Evaluation**: The `payment_instrument` property of the Payment Mandate MUST be present in the `allowed` array.

**Example**

```json
{
  "type": "payment.allowed_payment_instruments",
  "allowed": [
    {
      "id": "abe3c...",
      "type": "card",
      "description": "network ··· 1234"
    },
    {
      "id": "zde4d...",
      "type": "UPI",
      "description": "user****@bankname"
    },
  ]
}
```

### Allowed Payment Initiation Service Providers (PISPs)

**Type**: `payment.allowed_pisps`

**Description**: Defines the set of Payment Initiation Service Providers (PISPs) authorized to facilitate the transaction.

**Properties**:

| Name    | Type                   | Required | Description                 |
| ------- | ---------------------- | -------- | --------------------------- |
| type    | string                 | **Yes**  | Constraint type identifier. |
| allowed | Array\[[Pisp](#pisp)\] | **Yes**  | Array of allowed PISPs.     |

**Evaluation**: The PISP facilitating the transaction MUST be present in the `allowed` array.

**Example**

```json
{
  "type": "payment.allowed_pisps",
  "allowed": [
    {
      "legal_name": "Example Payment Services Ltd.",
      "brand_name": "ExamplePay",
      "domain_name": "examplepay.com"
    }
  ]
}
```

### Amount Range

**Type**: `payment.amount_range`

**Description**: Defines the valid range for the final amount to be within.

**Properties**:

| Name     | Type    | Required | Description                                                                       |
| -------- | ------- | -------- | --------------------------------------------------------------------------------- |
| type     | string  | **Yes**  | Constraint type identifier.                                                       |
| currency | string  | **Yes**  | ISO4217 Alpha-3 currency code.                                                    |
| max      | integer | **Yes**  | Maximum allowed amount in minor (cents) unit of currency.                         |
| min      | integer | No       | Minimal amount in minor (cents) unit of currency. If absent, there is no minimum. |

**Evaluation**:

The `payment_amount` property of the Payment Mandate MUST be within the range defined by `min` and `max`. The `currency` property of the Payment Mandate MUST match the `currency` property of this constraint.

**Example**

```json
{
  "type": "payment.amount_range",
  "max": 100.50,
  "min": 10.00,
  "currency": "USD"
}
```

### Budget

**Type**: `payment.budget`

**Description**: Defines the maximum total amount that can be spent when using the `payment.agent_recurrence` constraint.

**Properties**:

| Name     | Type   | Required | Description                                          |
| -------- | ------ | -------- | ---------------------------------------------------- |
| type     | string | **Yes**  | Constraint type identifier.                          |
| max      | number | **Yes**  | Maximum amount for the budget.                       |
| currency | string | **Yes**  | ISO4217 Alpha-3 defining the currency of the amount. |

**Evaluation**: Evaluating the budget requires tracking the total amount spent using this Payment Mandate. For this constraint to evaluate as true, the requested amount plus the total sum of amounts from previously closed Payment Mandates MUST be less than or equal to `max`. After approval, the amount MUST be added to the accumulated total for future evaluation.

**Example**

```json
{
  "type": "payment.budget",
  "max": 1000.00,
  "currency": "USD"
}
```

### Reference

**Type**: `payment.reference`

**Description**: Constrains this Payment Mandate for use with a particular Checkout Mandate (and its associated closed Mandates).

**Properties**:

| Name                       | Type   | Required | Description                                     |
| -------------------------- | ------ | -------- | ----------------------------------------------- |
| type                       | string | **Yes**  | Constraint type identifier.                     |
| conditional_transaction_id | string | **Yes**  | Digest of the associated Open Checkout Mandate. |

**Evaluation**: The Checkout Mandate for the approved order MUST contain an open Checkout Mandate with a matching hash in its delegate chain. The hash algorithm used MUST be the `_sd_alg` algorithm for the SD-JWT this constraint is in, or `sha-256` if undefined.

**Example**

```json
{
  "type": "payment.reference",
  "conditional_transaction_id": "A4wG4B..."
}
```

### Execution Date

**Type**: `payment.execution_date`

**Description**: Defines the valid time window for the payment execution.

**Properties**:

| Name       | Type   | Required | Description                    |
| ---------- | ------ | -------- | ------------------------------ |
| type       | string | **Yes**  | Constraint type identifier.    |
| not_before | string | No       | Earliest valid execution date. |
| not_after  | string | No       | Latest valid execution date.   |

**Evaluation**: The `execution_date` of the Payment Mandate MUST be later than or equal to `not_before` (if present) and earlier than or equal to `not_after` (if present).

**Example**

```json
{
  "type": "payment.execution_date",
  "not_before": "2026-03-31T00:00:00Z",
  "not_after": "2026-04-30T23:59:59Z"
}
```

## Payment Receipt

| Name                    | Type                            | Required | Description                                                                                             |
| ----------------------- | ------------------------------- | -------- | ------------------------------------------------------------------------------------------------------- |
| status                  | [ReceiptStatus](#receiptstatus) | **Yes**  | The status of the payment.                                                                              |
| iss                     | string                          | **Yes**  | The issuer of the receipt.                                                                              |
| iat                     | integer                         | **Yes**  | The creation timestamp as a Unix epoch.                                                                 |
| reference               | string                          | **Yes**  | The hash of the closed Mandate that this receipt is binding to.                                         |
| error                   | string                          | No       | A unique error code. Present if and only if status is Error.                                            |
| error_description       | string                          | No       | A human-readable error description. Present if and only if status is Error.                             |
| payment_id              | string                          | **Yes**  | A unique identifier for the payment.                                                                    |
| psp_confirmation_id     | string                          | No       | A unique identifier for the transaction confirmation at the PSP. Present only if status is Success.     |
| network_confirmation_id | string                          | No       | A unique identifier for the transaction confirmation at the network. Present only if status is Success. |

### ReceiptStatus

The status of a receipt.

**Values:** `Success`   `Error`

## Examples

### Open Payment Mandate SD-JWT plus disclosures

```json
{
  "issuer_signed_jwt": {
    "header": {
      "alg": "ES256",
      "typ": "example+sd-jwt",
      "kid": "agent-provider-key-1"
    },
    "payload": {
      "delegate_payload": [
        {
          "...": "3YRtZ-lBNhI_YhggShrdHhrSuDPSpwMvJ3VWjUnhDQM"
        }
      ],
      "_sd_alg": "sha-256"
    }
  },
  "disclosures": [
    {
      "digest": "oEH7i1gyb-zn6awwjy57LvzxkQDfD-8tvlC2XuIkgOA",
      "decoded": [
        "s9WPt2U4GapcJsonyEb6bjg",
        {
          "id": "merchant_1",
          "name": "Demo Merchant",
          "website": "https://demo-merchant.example"
        }
      ]
    },
    {
      "digest": "3YRtZ-lBNhI_YhggShrdHhrSuDPSpwMvJ3VWjUnhDQM",
      "decoded": [
        "ZtKS5FSrIAY6HlGB4Ho7mg",
        {
          "vct": "mandate.payment.open.1",
          "constraints": [
            {
              "type": "payment.amount_range",
              "currency": "USD",
              "max": 20000,
              "min": 0
            },
            {
              "type": "payment.allowed_payees",
              "allowed": [
                {
                  "...": "oEH7i1gyb-zn6awwjy57LvzxkQDfD-8tvlC2XuIkgOA"
                }
              ]
            },
            {
              "type": "payment.reference",
              "conditional_transaction_id": "FzLoxbbtgQGYZxoSM2NJYJtkFTSsdfUBoVEQ12k7JN8"
            }
          ],
          "cnf": {
            "jwk": {
              "crv": "P-256",
              "kty": "EC",
              "x": "QpSyxPQHy38xckypDr54gZ3T42zj9iLtV4koyb5U27c",
              "y": "37HLd7JJinxjJIn8J7HijssoeclbfhdW-gUL7feI9lw"
            }
          },
          "iat": 1777342357,
          "exp": 1777345957
        }
      ]
    }
  ]
}
```

#### Encoded Token

```text
eyJhbGciOiAiRVMyNTYiLCAidHlwIjogImV4YW1wbGUrc2Qtand0IiwgImtpZCI6ICJhZ2VudC1wcm92aWRlci1rZXktMSJ9.eyJkZWxlZ2F0ZV9wYXlsb2FkIjogW3siLi4uIjogIjNZUnRaLWxCTmhJX1loZ2dTaHJkSGhyU3VEUFNwd012SjNWV2pVbmhEUU0ifV0sICJfc2RfYWxnIjogInNoYS0yNTYifQ.ZQ_5x2hYLusuUNAA2OJloeS2w3fxZRCsSvcU-wg9fK7nlMmsbpK6EPlntD8oHq5waegxsLmSL51V5hfyaQViMg~WyJzOVdQdDJVNEdhcGNKc255RWI2YmpnIiwgeyJpZCI6ICJtZXJjaGFudF8xIiwgIm5hbWUiOiAiRGVtbyBNZXJjaGFudCIsICJ3ZWJzaXRlIjogImh0dHBzOi8vZGVtby1tZXJjaGFudC5leGFtcGxlIn1d~WyJadEtTNUZTcklBWTZIbEdCNEhvN21nIiwgeyJ2Y3QiOiAibWFuZGF0ZS5wYXltZW50Lm9wZW4uMSIsICJjb25zdHJhaW50cyI6IFt7InR5cGUiOiAicGF5bWVudC5hbW91bnRfcmFuZ2UiLCAiY3VycmVuY3kiOiAiVVNEIiwgIm1heCI6IDIwMDAwLCAibWluIjogMH0sIHsidHlwZSI6ICJwYXltZW50LmFsbG93ZWRfcGF5ZWVzIiwgImFsbG93ZWQiOiBbeyIuLi4iOiAib0VIN2kxZ3liLXpuNmF3d2p5NTdMdnp4a1FEZkQtOHR2bEMyWHVJa2dPQSJ9XX0sIHsidHlwZSI6ICJwYXltZW50LnJlZmVyZW5jZSIsICJjb25kaXRpb25hbF90cmFuc2FjdGlvbl9pZCI6ICJGekxveGJidGdRR1laeG9TTTJOSllKdGtGVFNzZGZVQm9WRVExMms3Sk44In1dLCAiY25mIjogeyJqd2siOiB7ImNydiI6ICJQLTI1NiIsICJrdHkiOiAiRUMiLCAieCI6ICJRcFN5eFBRSHkzOHhja3l2RHI1NGdaM1Q0MnpqOWlMdFY0a295YjVVMjdjIiwgInkiOiAiMzdITGQ3SkppbnhqSkluOEo3SGlqc3NvZWNCbGZoZFctZ1VMN2ZlSTlsdyJ9fSwgImlhdCI6IDE3NzczNDIzNTcsICJleHAiOiAxNzc3MzQ1OTU3fV0~
```

### Closed Payment Mandate SD-JWT plus disclosures

```json
{
  "issuer_signed_jwt": {
    "header": {
      "alg": "ES256",
      "typ": "kb+sd-jwt"
    },
    "payload": {
      "delegate_payload": [
        {
          "...": "G2DuU6IjyDkD-9ItStdsUo48C5uJqDs1E9Hf5GT3TgM"
        }
      ],
      "iat": 1777342370,
      "aud": "credential-provider",
      "nonce": "a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3",
      "sd_hash": "uixoHemmfrrCSbPREo9j-ziLuMkqExsPeWrwA-PK0Ck",
      "_sd_alg": "sha-256"
    }
  },
  "disclosures": [
    {
      "digest": "G2DuU6IjyDkD-9ItStdsUo48C5uJqDs1E9Hf5GT3TgM",
      "decoded": [
        "FW6McBJImqODuhQlpI4Idw",
        {
          "vct": "mandate.payment.1",
          "transaction_id": "NivWhuqfzcvZNapvIEJ2-3tsdQLkiuIcye2g46WVgX8",
          "payee": {
            "id": "merchant_1",
            "name": "Demo Merchant",
            "website": "https://demo-merchant.example"
          },
          "payment_amount": {
            "amount": 19900,
            "currency": "USD"
          },
          "payment_instrument": {
            "id": "stub",
            "type": "card",
            "description": "Card ••••4242"
          }
        }
      ]
    }
  ]
}
```

#### Encoded Token

```text
eyJhbGciOiAiRVMyNTYiLCAidHlwIjogImtiK3NkLWp3dCJ9.eyJkZWxlZ2F0ZV9wYXlsb2FkIjogW3siLi4uIjogIkcyRHVVNklqeURrRC05SXRTdGRzVW80OEM1dUpxRHMxRTlIZjVHVDNUZ00ifV0sICJpYXQiOiAxNzc3MzQyMzcwLCAiYXVkIjogImNyZWRlbnRpYWwtcHJvdmlkZXIiLCAibm9uY2UiOiAiYThiN2M2ZDVlNGYzYTJiMWMwZDllOGY3YTZiNWM0ZDMiLCAic2RfaGFzaCI6ICJ1aXhvSGVtbWZyckNTYlBSRW85ai16aUx1TWtxRXhzUGVXcndBLVBLMENrIiwgIl9zZF9hbGciOiAic2hhLTI1NiJ9.TgI6w9zeL993uzAYE9fnAJXjnrpliDY5DpDKTSQoioH3msapVIz0Ex23ncQXwmsSmT3xOqkSpigQD1EYKck-dQ~WyJmVzZNY0JKSW1xT0R1aFFscEk0SWR3IiwgeyJ2Y3QiOiAibWFuZGF0ZS5wYXltZW50LjEiLCAidHJhbnNhY3Rpb25faWQiOiAiTml2V2h1cWZ6Y3ZaTmFwdklFSjItM3RzZFFMa2l1SWN5ZTJnNDZXVmdYOCIsICJwYXllZSI6IHsiaWQiOiAibWVyY2hhbnRfMSIsICJuYW1lIjogIkRlbW8gTWVyY2hhbnQiLCAid2Vic2l0ZSI6ICJodHRwczovL2RlbW8tbWVyY2hhbnQuZXhhbXBsZSJ9LCAicGF5bWVudF9hbW91bnQiOiB7ImFtb3VudCI6IDE5OTAwLCAiY3VycmVuY3kiOiAiVVNEIn0sICJwYXltZW50X2luc3RydW1lbnQiOiB7ImlkIjogInN0dWIiLCAidHlwZSI6ICJjYXJkIiwgImRlc2NyaXB0aW9uIjogIkNhcmQgXHUyMDIyXHUyMDIyXHUyMDIyNDI0MiJ9fV0~
```

### Open Payment Mandate chained with a closed Payment Mandate after processing the delegate SD-JWT.

```json
{
  "issuer_signed_jwt": {
    "header": {
      "alg": "ES256",
      "typ": "example+sd-jwt",
      "kid": "agent-provider-key-1"
    },
    "payload": {
      "delegate_payload": [
        {
          "...": "3YRtZ-lBNhI_YhggShrdHhrSuDPSpwMvJ3VWjUnhDQM"
        }
      ],
      "_sd_alg": "sha-256"
    }
  },
  "disclosures": [
    {
      "digest": "oEH7i1gyb-zn6awwjy57LvzxkQDfD-8tvlC2XuIkgOA",
      "decoded": [
        "s9WPt2U4GapcJsonyEb6bjg",
        {
          "id": "merchant_1",
          "name": "Demo Merchant",
          "website": "https://demo-merchant.example"
        }
      ]
    },
    {
      "digest": "3YRtZ-lBNhI_YhggShrdHhrSuDPSpwMvJ3VWjUnhDQM",
      "decoded": [
        "ZtKS5FSrIAY6HlGB4Ho7mg",
        {
          "vct": "mandate.payment.open.1",
          "constraints": [
            {
              "type": "payment.amount_range",
              "currency": "USD",
              "max": 20000,
              "min": 0
            },
            {
              "type": "payment.allowed_payees",
              "allowed": [
                {
                  "...": "oEH7i1gyb-zn6awwjy57LvzxkQDfD-8tvlC2XuIkgOA"
                }
              ]
            },
            {
              "type": "payment.reference",
              "conditional_transaction_id": "FzLoxbbtgQGYZxoSM2NJYJtkFTSsdfUBoVEQ12k7JN8"
            }
          ],
          "cnf": {
            "jwk": {
              "crv": "P-256",
              "kty": "EC",
              "x": "QpSyxPQHy38xckypDr54gZ3T42zj9iLtV4koyb5U27c",
              "y": "37HLd7JJinxjJIn8J7HijssoeclbfhdW-gUL7feI9lw"
            }
          },
          "iat": 1777342357,
          "exp": 1777345957
        }
      ]
    }
  ]
}
{
  "issuer_signed_jwt": {
    "header": {
      "alg": "ES256",
      "typ": "kb+sd-jwt"
    },
    "payload": {
      "delegate_payload": [
        {
          "...": "G2DuU6IjyDkD-9ItStdsUo48C5uJqDs1E9Hf5GT3TgM"
        }
      ],
      "iat": 1777342370,
      "aud": "credential-provider",
      "nonce": "a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3",
      "sd_hash": "uixoHemmfrrCSbPREo9j-ziLuMkqExsPeWrwA-PK0Ck",
      "_sd_alg": "sha-256"
    }
  },
  "disclosures": [
    {
      "digest": "G2DuU6IjyDkD-9ItStdsUo48C5uJqDs1E9Hf5GT3TgM",
      "decoded": [
        "FW6McBJImqODuhQlpI4Idw",
        {
          "vct": "mandate.payment.1",
          "transaction_id": "NivWhuqfzcvZNapvIEJ2-3tsdQLkiuIcye2g46WVgX8",
          "payee": {
            "id": "merchant_1",
            "name": "Demo Merchant",
            "website": "https://demo-merchant.example"
          },
          "payment_amount": {
            "amount": 19900,
            "currency": "USD"
          },
          "payment_instrument": {
            "id": "stub",
            "type": "card",
            "description": "Card ••••4242"
          }
        }
      ]
    }
  ]
}
```

#### Encoded Token

```text
eyJhbGciOiAiRVMyNTYiLCAidHlwIjogImV4YW1wbGUrc2Qtand0IiwgImtpZCI6ICJhZ2VudC1wcm92aWRlci1rZXktMSJ9.eyJkZWxlZ2F0ZV9wYXlsb2FkIjogW3siLi4uIjogIjNZUnRaLWxCTmhJX1loZ2dTaHJkSGhyU3VEUFNwd012SjNWV2pVbmhEUU0ifV0sICJfc2RfYWxnIjogInNoYS0yNTYifQ.ZQ_5x2hYLusuUNAA2OJloeS2w3fxZRCsSvcU-wg9fK7nlMmsbpK6EPlntD8oHq5waegxsLmSL51V5hfyaQViMg~WyJzOVdQdDJVNEdhcGNKc255RWI2YmpnIiwgeyJpZCI6ICJtZXJjaGFudF8xIiwgIm5hbWUiOiAiRGVtbyBNZXJjaGFudCIsICJ3ZWJzaXRlIjogImh0dHBzOi8vZGVtby1tZXJjaGFudC5leGFtcGxlIn1d~WyJadEtTNUZTcklBWTZIbEdCNEhvN21nIiwgeyJ2Y3QiOiAibWFuZGF0ZS5wYXltZW50Lm9wZW4uMSIsICJjb25zdHJhaW50cyI6IFt7InR5cGUiOiAicGF5bWVudC5hbW91bnRfcmFuZ2UiLCAiY3VycmVuY3kiOiAiVVNEIiwgIm1heCI6IDIwMDAwLCAibWluIjogMH0sIHsidHlwZSI6ICJwYXltZW50LmFsbG93ZWRfcGF5ZWVzIiwgImFsbG93ZWQiOiBbeyIuLi4iOiAib0VIN2kxZ3liLXpuNmF3d2p5NTdMdnp4a1FEZkQtOHR2bEMyWHVJa2dPQSJ9XX0sIHsidHlwZSI6ICJwYXltZW50LnJlZmVyZW5jZSIsICJjb25kaXRpb25hbF90cmFuc2FjdGlvbl9pZCI6ICJGekxveGJidGdRR1laeG9TTTJOSllKdGtGVFNzZGZVQm9WRVExMms3Sk44In1dLCAiY25mIjogeyJqd2siOiB7ImNydiI6ICJQLTI1NiIsICJrdHkiOiAiRUMiLCAieCI6ICJRcFN5eFBRSHkzOHhja3l2RHI1NGdaM1Q0MnpqOWlMdFY0a295YjVVMjdjIiwgInkiOiAiMzdITGQ3SkppbnhqSkluOEo3SGlqc3NvZWNCbGZoZFctZ1VMN2ZlSTlsdyJ9fSwgImlhdCI6IDE3NzczNDIzNTcsICJleHAiOiAxNzc3MzQ1OTU3fV0~~eyJhbGciOiAiRVMyNTYiLCAidHlwIjogImtiK3NkLWp3dCJ9.eyJkZWxlZ2F0ZV9wYXlsb2FkIjogW3siLi4uIjogIkcyRHVVNklqeURrRC05SXRTdGRzVW80OEM1dUpxRHMxRTlIZjVHVDNUZ00ifV0sICJpYXQiOiAxNzc3MzQyMzcwLCAiYXVkIjogImNyZWRlbnRpYWwtcHJvdmlkZXIiLCAibm9uY2UiOiAiYThiN2M2ZDVlNGYzYTJiMWMwZDllOGY3YTZiNWM0ZDMiLCAic2RfaGFzaCI6ICJ1aXhvSGVtbWZyckNTYlBSRW85ai16aUx1TWtxRXhzUGVXcndBLVBLMENrIiwgIl9zZF9hbGciOiAic2hhLTI1NiJ9.TgI6w9zeL993uzAYE9fnAJXjnrpliDY5DpDKTSQoioH3msapVIz0Ex23ncQXwmsSmT3xOqkSpigQD1EYKck-dQ~WyJmVzZNY0JKSW1xT0R1aFFscEk0SWR3IiwgeyJ2Y3QiOiAibWFuZGF0ZS5wYXltZW50LjEiLCAidHJhbnNhY3Rpb25faWQiOiAiTml2V2h1cWZ6Y3ZaTmFwdklFSjItM3RzZFFMa2l1SWN5ZTJnNDZXVmdYOCIsICJwYXllZSI6IHsiaWQiOiAibWVyY2hhbnRfMSIsICJuYW1lIjogIkRlbW8gTWVyY2hhbnQiLCAid2Vic2l0ZSI6ICJodHRwczovL2RlbW8tbWVyY2hhbnQuZXhhbXBsZSJ9LCAicGF5bWVudF9hbW91bnQiOiB7ImFtb3VudCI6IDE5OTAwLCAiY3VycmVuY3kiOiAiVVNEIn0sICJwYXltZW50X2luc3RydW1lbnQiOiB7ImlkIjogInN0dWIiLCAidHlwZSI6ICJjYXJkIiwgImRlc2NyaXB0aW9uIjogIkNhcmQgXHUyMDIyXHUyMDIyXHUyMDIyNDI0MiJ9fV0~
```

## Common Types

### Amount

| Name     | Type    | Required | Description                                                |
| -------- | ------- | -------- | ---------------------------------------------------------- |
| amount   | integer | **Yes**  | Amount in minor units, according to the ISO-4217 spec.     |
| currency | string  | **Yes**  | ISO-4217 3-letter alphabetic currency code of the payment. |

### Merchant

| Name    | Type   | Required | Description                          |
| ------- | ------ | -------- | ------------------------------------ |
| id      | string | **Yes**  | Unique identifier for the merchant.  |
| name    | string | **Yes**  | Human-readable name of the merchant. |
| website | string | No       | Website belonging to the merchant.   |

### PaymentInstrument

| Name        | Type   | Required | Description                                                                          |
| ----------- | ------ | -------- | ------------------------------------------------------------------------------------ |
| id          | string | **Yes**  | unique identifier for this instrument                                                |
| type        | string | **Yes**  | unique string identifying this category of instrument                                |
| description | string | No       | Description of the instrument to be displayed to the user for informational purposes |

### Pisp

| Name        | Type   | Required | Description                                                                    |
| ----------- | ------ | -------- | ------------------------------------------------------------------------------ |
| legal_name  | string | **Yes**  | Legal name of the PISP.                                                        |
| brand_name  | string | **Yes**  | Brand name of the PISP.                                                        |
| domain_name | string | **Yes**  | Domain name of the PISP as secured by the [eIDAS] QWAC certificate of the TPP. |
