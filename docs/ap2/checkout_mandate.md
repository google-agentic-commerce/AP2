# Checkout Mandate

The Checkout Mandate is a Mandate used for authorizing the completion of a
checkout.

## Usage

The Checkout Mandate Content is created by the Shopping Agent, rendered to the
User by the Trusted Surface and verified by the Merchant. The Merchant creates a
signed Checkout object which is included in closed Checkout Mandate Content.

## Type

A closed Checkout Mandate MUST use the value `mandate.checkout.1` for the `vct`
claim and an open Checkout Mandate MUST use the value `mandate.checkout.open.1`.

See [Mandate Versioning](specification.md#mandate-versioning) for how the
version suffix works.

## Mandate Schema

The closed Checkout Mandate conforms to the following schema:

{{ schema_fields('checkout_mandate', 'ap2', show_sd=True) }}

`checkout_hash` is the base64url-encoded hash of the value of `checkout_jwt`.
The algorithm used MUST be the same as the SD-JWT, as defined by the `_sd_alg`
claim in the base payload, or `sha-256` if not present.

Before releasing credentials or initiating payment, the Credential Provider,
Merchant, and Merchant Payment Processor each MUST verify that the `checkout_hash`
field's value matches a computed hash of the `checkout_jwt` value. The hash
MUST be computed by applying the `_sd_alg` algorithm (or `sha-256` if absent)
to the raw bytes of the `checkout_jwt` value. If the values do not match, the
verifier MUST reject the mandate and MUST NOT proceed with the transaction.

`checkout_jwt` is the merchant-signed JWT containing the details of the
checkout. The details of the payload are outside the scope of this
specification, when used with the [Universal Commerce Protocol](https://ucp.dev)
this MUST be the Checkout object.

## Constraints

The following constraints are defined in this document for use with the open
Checkout Mandates:

- **Allowed Merchant:** Constrains the Merchants that this Checkout Mandate
    can be used with.
- **Line Items:** Defines the valid set of Line Items to be included in the
    Checkout Mandate.

### Allowed Merchants

**Type**: `checkout.allowed_merchants`

**Description**: Constrains the possible merchants for this Checkout Mandate.

**Properties**:

{{ schema_fields('open_checkout_mandate', 'ap2', show_sd=True,
pointer='#/$defs/allowed_merchants') }}

**Evaluation**: The Merchant MUST be present in the revealed elements of
`allowed`. If they are not present, or if the `allowed`
contains no revealed elements, the constraint is invalid.

#### Example

```json
{
  "type":  "checkout.allowed_merchants",
  "allowed": [
    {"name": "Merchant Choice", "website": "https://merchant-choice.com" },
    {"name": "Second Merchant", "website": "https://second-merchant.com" },
  ]
}
```

### Line Items

**Type**: `checkout.line_items`

**Description**: Defines the sets of line items that are to be present in the
checkout_jwt.

**Properties**:

{{ schema_fields('open_checkout_mandate', 'ap2', show_sd=True,
pointer='#/$defs/line_items') }}

**Evaluation**: This constraint is met when:

- Each `items` entry in the constraint has a total quantity of matching items
    in the Checkout.
- An item matches an `items` entry if its ID is present in the revealed
    `acceptable_items`.
- No `items` entry or item in the Checkout may be used more than once.

One way to implement this is as a maximal flow problem. The graph is defined as
follows:

1. Create a node for each `items` entry.
2. Provide an edge from the source to each `items` node with a capacity equal
    to the quantity.
3. Create a node for each item ID in the Checkout.
4. Provide an edge from each Checkout item node to the sink with a capacity
    equal to the total quantity of that item ID in the checkout.
5. Provide an edge with infinite capacity between each `items` node and each
    Checkout item node that matches the revealed `acceptable_items` for that
    item.

The constraint is met if the maximal flow equals the total constraint `items`
quantity and the total checkout `items` quantity.

> NOTE: This evaluation does not support splitting the open Checkout Mandate
> across multiple Checkouts. Future constraint extensions can add this support,
> but consideration must be given to how multiple duplicate orders can be
> prevented.

#### Example

```json
{
  "type":  "checkout.line_items",
  "items": [
    {
      "id": "id-shoe-choices",
      "acceptable_items": [
        {"id": "BAB1234", "title": "Red Style"}
        {"id": "FAF1234", "title": "Blue Style"}
      ],
      "quantity": 1
    },
    {
      "id": "id-sock-choices",
      "acceptable_items": [
        {"id": "QRT1234", "title": "The Best Socks"}
      ],
      "quantity": 1
    },
  ]
}
```

This would be fulfilled by the following combinations:

- Item: Red Style, Item: The Best Socks
- Item: Blue Style, Item 3: The Best Socks

But it would be invalid to have a Checkout containing:

- Item: Red Style, Item: Blue Style
- Item: Red Style
- Item: Blue Style
- Item: The Best Socks

## Checkout Receipt

The Checkout Receipt conforms to the following Schema:

{{ schema_fields('checkout_receipt', 'ap2', show_sd=True) }}

## Examples

<!-- cspell:disable -->

### Open Checkout Mandate SD-JWT plus disclosures

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
          "...": "QtXTJtWqg999CmUWGjHFTWMkRPguDfeK3wGSaInd-dw"
        }
      ],
      "_sd_alg": "sha-256"
    }
  },
  "disclosures": [
    {
      "digest": "y3aocAD2rhYpJQOUMN016faDFGkTBGEDVl1R1TRHdbw",
      "decoded": [
        "4n3L_-3_Fm2GgyFAF8Ct_g",
        {
          "id": "supershoe_limited_edition_gold_sneaker_womens_9_0",
          "title": "SuperShoe Limited Edition Gold"
        }
      ]
    },
    {
      "digest": "a5UMAdxCk_MRayyVdRhpIAZ0ZhjVLEq1g2BWyruKUwg",
      "decoded": [
        "2zPL6vqLBg2WYAdbW9-1lQ",
        {
          "id": "merchant_1",
          "name": "Demo Merchant",
          "website": "https://demo-merchant.example"
        }
      ]
    },
    {
      "digest": "QtXTJtWqg999CmUWGjHFTWMkRPguDfeK3wGSaInd-dw",
      "decoded": [
        "laAoWKNRuGnwREjJWYJ7pg",
        {
          "vct": "mandate.checkout.open.1",
          "constraints": [
            {
              "type": "checkout.line_items",
              "items": [
                {
                  "id": "line_1",
                  "acceptable_items": [
                    {
                      "...": "y3aocAD2rhYpJQOUMN016faDFGkTBGEDVl1R1TRHdbw"
                    }
                  ],
                  "quantity": 1
                }
              ]
            },
            {
              "type": "checkout.allowed_merchants",
              "allowed": [
                {
                  "...": "a5UMAdxCk_MRayyVdRhpIAZ0ZhjVLEq1g2BWyruKUwg"
                }
              ]
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
eyJhbGciOiAiRVMyNTYiLCAidHlwIjogImV4YW1wbGUrc2Qtand0IiwgImtpZCI6ICJhZ2VudC1wcm92aWRlci1rZXktMSJ9.eyJkZWxlZ2F0ZV9wYXlsb2FkIjogW3siLi4uIjogIlF0WFRKdFdxZzk5OUNtVVdHakhGVFdNa1JQZ3VEZmVLM3dHU2FJbmQtZHcifV0sICJfc2RfYWxnIjogInNoYS0yNTYifQ.HvCGk7ye_c0LN2-NFG13wfyu3LA--rckTPGm36ugO2aRvsded7ngw1py8W3JF7wBpoQnsKr17tNTF3zLeYcoWA~WyI0bjNMXy0zX0ZtMkdneUZBRjhDdF9nIiwgeyJpZCI6ICJzdXBlcnNob2VfbGltaXRlZF9lZGl0aW9uX2dvbGRfc25lYWtlcl93b21lbnNfOV8wIiwgInRpdGxlIjogIlN1cGVyU2hvZSBMaW1pdGVkIEVkaXRpb24gR29sZCJ9XQ~WyIyelBMNnZxTEJnMldZQWRiVzktMWxRIiwgeyJpZCI6ICJtZXJjaGFudF8xIiwgIm5hbWUiOiAiRGVtbyBNZXJjaGFudCIsICJ3ZWJzaXRlIjogImh0dHBzOi8vZGVtby1tZXJjaGFudC5leGFtcGxlIn1d~WyJsYUFvV0tOUnVHbndSRWpKV1lKN3BnIiwgeyJ2Y3QiOiAibWFuZGF0ZS5jaGVja291dC5vcGVuLjEiLCAiY29uc3RyYWludHMiOiBbeyJ0eXBlIjogImNoZWNrb3V0LmxpbmVfaXRlbXMiLCAiaXRlbXMiOiBbeyJpZCI6ICJsaW5lXzEiLCAiYWNjZXB0YWJsZV9pdGVtcyI6IFt7Ii4uLiI6ICJ5M2FvY0FEMnJoWXBKUU9VTU4wMTZmYURGR2tUQkdFRFZsMVIxVFJIZGJ3In1dLCAicXVhbnRpdHkiOiAxfV19LCB7InR5cGUiOiAiY2hlY2tvdXQuYWxsb3dlZF9tZXJjaGFudHMiLCAiYWxsb3dlZCI6IFt7Ii4uLiI6ICJhNVVNQWR4Q2tfTVJheXlWZFJocElBWjBaaGpWTEVxMWcyQld5cndLVXdnIn1dfV0sICJjbmYiOiB7Imp3ayI6IHsiY3J2IjogIlAtMjU2IiwgImt0eSI6ICJFQyIsICJ4IjogIlFwU3l4UFFIeTM4eGNreXZEcjU0Z1ozVDQyemo5aUx0VjRrb3liNVUyN2MiLCAieSI6ICIzN0hMZDdKSmlueGpKSW44SjdIaWpzc29lY0JsZmhkVy1nVUw3ZmVJOWx3In19LCAiaWF0IjogMTc3NzM0MjM1NywgImV4cCI6IDE3NzczNDU5NTd9XQ~
```

### Closed Checkout Mandate SD-JWT plus disclosures

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
          "...": "7VLY-eKTFSShLoZRXY5jXcD2UHm1JvPmoANYRqqxy34"
        }
      ],
      "iat": 1777342376,
      "aud": "merchant",
      "nonce": "b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4",
      "sd_hash": "FzLoxbbtgQGYZxoSM2NJYJtkFTSsdfUBoVEQ12k7JN8",
      "_sd_alg": "sha-256"
    }
  },
  "disclosures": [
    {
      "digest": "FzLoxbbtgQGYZxoSM2NJYJtkFTSsdfUBoVEQ12k7JN8",
      "decoded": [
        "w-n1leFT6z8rHTNHwr5Wow",
        "checkout_jwt",
        {
          "header": {
            "alg": "ES256",
            "typ": "JWT"
          },
          "payload": {
            "order_id": "09414145-b7bi-432e-bf5c-ha0ba0bc4580",
            "merchant": {
              "id": "merchant_1",
              "name": "Demo Merchant",
              "website": "https://demo-merchant.example"
            },
            "line_items": [
              {
                "id": "line_1",
                "product": {
                  "id": "supershoe_limited_edition_gold_sneaker_womens_9_0",
                  "title": "SuperShoe Limited Edition Gold — Women's 9",
                  "price": 199.0,
                  "currency": "USD"
                },
                "quantity": 1
              }
            ],
            "total_price": 199.0,
            "currency": "USD",
            "shipping_policy": "Standard Shipping",
            "return_policy": "30-day returns"
          }
        }
      ]
    },
    {
      "digest": "7VLY-eKTFSShLoZRXY5jXcD2UHm1JvPmoANYRqqxy34",
      "decoded": [
        "szhpxKrgGJwyqMEN9WI5Sw",
        {
          "_sd": [
            "3A9UyZJofw2eMP-Lx2tYaNpCcuB8elnhwwLhZLwqFFM"
          ],
          "vct": "mandate.checkout.1",
          "checkout_hash": "NivWhuqfzcvZNapvIEJ2-3tsdQLkiuIcye2g46WVgX8"
        }
      ]
    }
  ]
}
```

#### Encoded Token

```text
eyJhbGciOiAiRVMyNTYiLCAidHlwIjogImtiK3NkLWp3dCJ9.eyJkZWxlZ2F0ZV9wYXlsb2FkIjogW3siLi4uIjogIjdWTFktZUtURlNTaExvWlJYWTVqWGNEMlVIbTFKdlBtb0FOWVJxcXh5MzQifV0sICJpYXQiOiAxNzc3MzQyMzc2LCAiYXVkIjogIm1lcmNoYW50IiwgIm5vbmNlIjogImI5YzhkN2U2ZjVhNGIzYzJkMWUwZjlhOGI3YzZkNWU0IiwgInNkX2hhc2giOiAiRnpMb3hiYnRnUUdZWnhvU00yTkpZSnRrRlRTc2RmVUJvVkVRMTJrN0pOOCIsICJfc2RfYWxnIjogInNoYS0yNTYifQ.lSjkli6K3NbKlWOl1gJdWDwiyL88yJVyx32ZJHmvCXfRoItnchXw-MLUDEJv7o9lmTeipS42qNt7Z_oGSnRH1w~WyJzeGhweEtyZ0dKd3lxTUVNOVdJNVN3IiwgeyJfc2QiOiBbIjNBOVV5WkpvZncyZU1QLUx4MnRZYU5wQ2N1QjhlbG5od3dMaFpMd3FRRk0iXSwgInZjdCI6ICJtYW5kYXRlLmNoZWNrb3V0LjEiLCAiY2hlY2tvdXRfaGFzaCI6ICJOaXZXaHVxZnpjdlpOYXB2SUVKMi0zdHNkUUxraXVJY3llMmc0NldWZ1g4In1d~WyJ3LW4xbGVGVDZ6OHJIVE5Id3I1V293IiwgImNoZWNrb3V0X2p3dCIsICJleUpoYkdjaU9pQWlSVk15TlRZaUxDQWlkSGx3SWpvZ0lrcFhWQ0lzSUNKcmFXUWlPaUFpYldWeVkyaGhiblF0YTJWNUxURWlmUS5leUpwWkNJNklDSXdPVFF4TkRFME5TMWlOekJpTFRRNE0yRXRZamcxWXkxaFlUQm1ZVEJqTkRVNE1EQWlMQ0FpYldWeVkyaGhiblFpT2lCN0ltbGtJam9nSW0xbGNtTm9ZVzUwWHpFaUxDQWlibUZ0WlNJNklDSkVaVzF2SUUxbGNtTm9ZVzUwSWl3Z0luZGxZbk5wZEdVaU9pQWlhSFIwY0hNNkx5OWtaVzF2TFcxbGNtTm9ZVzUwTG1WNFlXMXdiR1VpZlN3Z0lteHBibVZmYVhSbGJYTWlPaUJiZXlKcFpDSTZJQ0pzYVY4d0lpd2dJbWwwWlcwaU9pQjdJbWxrSWpvZ0luTjFjR1Z5YzJodlpWOXNhVzFwZEdWa1gyVmthWFJwYjI1ZloyOXNaRjl6Ym1WaGEyVnlYM2R2YldWdWMxODVYekFpTENBaWRHbDBiR1VpT2lBaVUzVndaWEp6YUc5bElFeHBiV2wwWldRZ1JXUnBkR2x2YmlCSGIyeGtJRk51WldGclpYSWdWMjl0Wlc1eklEa2lMQ0FpY0hKcFkyVWlPaUF4T1Rrd01IMHNJQ0p4ZFdGdWRHbDBlU0k2SURFc0lDSjBiM1JoYkhNaU9pQmJleUowZVhCbElqb2dJbk4xWW5SdmRHRnNJaXdnSW1GdGIzVnVkQ0k2SURFNU9UQXdmU3dnZXlKMGVYQmxJam9nSW5SdmRHRnNJaXdnSW1GdGIzVnVkQ0k2SURFNU9UQXdmVjE5WFN3Z0luTjBZWFIxY3lJNklDSnBibU52YlhCc1pYUmxJaXdnSW1OMWNuSmxibU41SWpvZ0lsVlRSQ0lzSUNKMGIzUmhiSE1pT2lCYmV5SjBlWEJsSWpvZ0luTjFZblJ2ZEdGc0lpd2dJbUZ0YjNWdWRDSTZJREU1T1RBd2ZTd2dleUowZVhCbElqb2dJblJ2ZEdGc0lpd2dJbUZ0YjNWdWRDSTZJREU1T1RBd2ZWMHNJQ0pzYVc1cmN5STZJRnQ3SW5SNWNHVWlPaUFpY0hKcGRtRmplVjl3YjJ4cFkza2lMQ0FpZFhKc0lqb2dJbWgwZEhCek9pOHZhSFIwY0hNdkwyUmxiVzh0YldWeVkyaGhiblF1WlhoaGJYQnNaUzl3Y21sMllXTjVJbjBzSUhzaWRIbHdaU0k2SUNKMFpYSnRjMTl2Wmw5elpYSjJhV05sSWl3Z0luVnliQ0k2SUNKb2RIUndjem92TDJoMGRIQnpMeTlrWlcxdkxXMWxjbU5vWVc1MExtVjRZVzF3YkdVdmRHOXpJbjFkZlEuUC1WS3poeUp1bzktUlBpTjVheW5naDdmTFVLY09QQWVaejczU09Zd2Q1UDlZWG1HTE9yTFRXeGdYdkd5UVF0dERETTVELUc0czE5dnhfVTY1ZHJ1UmciXQ~
```

### Open Checkout Mandate chained with a Closed Checkout Mandate after processing the delegate SD-JWT

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
          "...": "QtXTJtWqg999CmUWGjHFTWMkRPguDfeK3wGSaInd-dw"
        }
      ],
      "_sd_alg": "sha-256"
    }
  },
  "disclosures": [
    {
      "digest": "y3aocAD2rhYpJQOUMN016faDFGkTBGEDVl1R1TRHdbw",
      "decoded": [
        "4n3L_-3_Fm2GgyFAF8Ct_g",
        {
          "id": "supershoe_limited_edition_gold_sneaker_womens_9_0",
          "title": "SuperShoe Limited Edition Gold"
        }
      ]
    },
    {
      "digest": "a5UMAdxCk_MRayyVdRhpIAZ0ZhjVLEq1g2BWyruKUwg",
      "decoded": [
        "2zPL6vqLBg2WYAdbW9-1lQ",
        {
          "id": "merchant_1",
          "name": "Demo Merchant",
          "website": "https://demo-merchant.example"
        }
      ]
    },
    {
      "digest": "QtXTJtWqg999CmUWGjHFTWMkRPguDfeK3wGSaInd-dw",
      "decoded": [
        "laAoWKNRuGnwREjJWYJ7pg",
        {
          "vct": "mandate.checkout.open.1",
          "constraints": [
            {
              "type": "checkout.line_items",
              "items": [
                {
                  "id": "line_1",
                  "acceptable_items": [
                    {
                      "...": "y3aocAD2rhYpJQOUMN016faDFGkTBGEDVl1R1TRHdbw"
                    }
                  ],
                  "quantity": 1
                }
              ]
            },
            {
              "type": "checkout.allowed_merchants",
              "allowed": [
                {
                  "...": "a5UMAdxCk_MRayyVdRhpIAZ0ZhjVLEq1g2BWyruKUwg"
                }
              ]
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
          "...": "7VLY-eKTFSShLoZRXY5jXcD2UHm1JvPmoANYRqqxy34"
        }
      ],
      "iat": 1777342376,
      "aud": "merchant",
      "nonce": "b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4",
      "sd_hash": "FzLoxbbtgQGYZxoSM2NJYJtkFTSsdfUBoVEQ12k7JN8",
      "_sd_alg": "sha-256"
    }
  },
  "disclosures": [
    {
      "digest": "7VLY-eKTFSShLoZRXY5jXcD2UHm1JvPmoANYRqqxy34",
      "decoded": [
        "szhpxKrgGJwyqMEN9WI5Sw",
        {
          "_sd": [
            "3A9UyZJofw2eMP-Lx2tYaNpCcuB8elnhwwLhZLwqFFM"
          ],
          "vct": "mandate.checkout.1",
          "checkout_hash": "NivWhuqfzcvZNapvIEJ2-3tsdQLkiuIcye2g46WVgX8"
        }
      ]
    },
    {
      "digest": "FzLoxbbtgQGYZxoSM2NJYJtkFTSsdfUBoVEQ12k7JN8",
      "decoded": [
        "w-n1leFT6z8rHTNHwr5Wow",
        "checkout_jwt",
        {
          "header": {
            "alg": "ES256",
            "typ": "JWT"
          },
          "payload": {
            "order_id": "09414145-b7bi-432e-bf5c-ha0ba0bc4580",
            "merchant": {
              "id": "merchant_1",
              "name": "Demo Merchant",
              "website": "https://demo-merchant.example"
            },
            "line_items": [
              {
                "id": "line_1",
                "product": {
                  "id": "supershoe_limited_edition_gold_sneaker_womens_9_0",
                  "title": "SuperShoe Limited Edition Gold — Women's 9",
                  "price": 199.0,
                  "currency": "USD"
                },
                "quantity": 1
              }
            ],
            "total_price": 199.0,
            "currency": "USD",
            "shipping_policy": "Standard Shipping",
            "return_policy": "30-day returns"
          }
        }
      ]
    }
  ]
}
```

#### Encoded Token

```text
eyJhbGciOiAiRVMyNTYiLCAidHlwIjogImV4YW1wbGUrc2Qtand0IiwgImtpZCI6ICJhZ2VudC1wcm92aWRlci1rZXktMSJ9.eyJkZWxlZ2F0ZV9wYXlsb2FkIjogW3siLi4uIjogIlF0WFRKdFdxZzk5OUNtVVdHakhGVFdNa1JQZ3VEZmVLM3dHU2FJbmQtZHcifV0sICJfc2RfYWxnIjogInNoYS0yNTYifQ.HvCGk7ye_c0LN2-NFG13wfyu3LA--rckTPGm36ugO2aRvsded7ngw1py8W3JF7wBpoQnsKr17tNTF3zLeYcoWA~WyI0bjNMXy0zX0ZtMkdneUZBRjhDdF9nIiwgeyJpZCI6ICJzdXBlcnNob2VfbGltaXRlZF9lZGl0aW9uX2dvbGRfc25lYWtlcl93b21lbnNfOV8wIiwgInRpdGxlIjogIlN1cGVyU2hvZSBMaW1pdGVkIEVkaXRpb24gR29sZCJ9XQ~WyIyelBMNnZxTEJnMldZQWRiVzktMWxRIiwgeyJpZCI6ICJtZXJjaGFudF8xIiwgIm5hbWUiOiAiRGVtbyBNZXJjaGFudCIsICJ3ZWJzaXRlIjogImh0dHBzOi8vZGVtby1tZXJjaGFudC5leGFtcGxlIn1d~WyJsYUFvV0tOUnVHbndSRWpKV1lKN3BnIiwgeyJ2Y3QiOiAibWFuZGF0ZS5jaGVja291dC5vcGVuLjEiLCAiY29uc3RyYWludHMiOiBbeyJ0eXBlIjogImNoZWNrb3V0LmxpbmVfaXRlbXMiLCAiaXRlbXMiOiBbeyJpZCI6ICJsaW5lXzEiLCAiYWNjZXB0YWJsZV9pdGVtcyI6IFt7Ii4uLiI6ICJ5M2FvY0FEMnJoWXBKUU9VTU4wMTZmYURGR2tUQkdFRFZsMVIxVFJIZGJ3In1dLCAicXVhbnRpdHkiOiAxfV19LCB7InR5cGUiOiAiY2hlY2tvdXQuYWxsb3dlZF9tZXJjaGFudHMiLCAiYWxsb3dlZCI6IFt7Ii4uLiI6ICJhNVVNQWR4Q2tfTVJheXlWZFJocElBWjBaaGpWTEVxMWcyQld5cndLVXdnIn1dfV0sICJjbmYiOiB7Imp3ayI6IHsiY3J2IjogIlAtMjU2IiwgImt0eSI6ICJFQyIsICJ4IjogIlFwU3l4UFFIeTM4eGNreXZEcjU0Z1ozVDQyemo5aUx0VjRrb3liNVUyN2MiLCAieSI6ICIzN0hMZDdKSmlueGpKSW44SjdIaWpzc29lY0JsZmhkVy1nVUw3ZmVJOWx3In19LCAiaWF0IjogMTc3NzM0MjM1NywgImV4cCI6IDE3NzczNDU5NTd9XQ~~eyJhbGciOiAiRVMyNTYiLCAidHlwIjogImtiK3NkLWp3dCJ9.eyJkZWxlZ2F0ZV9wYXlsb2FkIjogW3siLi4uIjogIjdWTFktZUtURlNTaExvWlJYWTVqWGNEMlVIbTFKdlBtb0FOWVJxcXh5MzQifV0sICJpYXQiOiAxNzc3MzQyMzc2LCAiYXVkIjogIm1lcmNoYW50IiwgIm5vbmNlIjogImI5YzhkN2U2ZjVhNGIzYzJkMWUwZjlhOGI3YzZkNWU0IiwgInNkX2hhc2giOiAiRnpMb3hiYnRnUUdZWnhvU00yTkpZSnRrRlRTc2RmVUJvVkVRMTJrN0pOOCIsICJfc2RfYWxnIjogInNoYS0yNTYifQ.lSjkli6K3NbKlWOl1gJdWDwiyL88yJVyx32ZJHmvCXfRoItnchXw-MLUDEJv7o9lmTeipS42qNt7Z_oGSnRH1w~WyJzeGhweEtyZ0dKd3lxTUVNOVdJNVN3IiwgeyJfc2QiOiBbIjNBOVV5WkpvZncyZU1QLUx4MnRZYU5wQ2N1QjhlbG5od3dMaFpMd3FRRk0iXSwgInZjdCI6ICJtYW5kYXRlLmNoZWNrb3V0LjEiLCAiY2hlY2tvdXRfaGFzaCI6ICJOaXZXaHVxZnpjdlpOYXB2SUVKMi0zdHNkUUxraXVJY3llMmc0NldWZ1g4In1d~WyJ3LW4xbGVGVDZ6OHJIVE5Id3I1V293IiwgImNoZWNrb3V0X2p3dCIsICJleUpoYkdjaU9pQWlSVk15TlRZaUxDQWlkSGx3SWpvZ0lrcFhWQ0lzSUNKcmFXUWlPaUFpYldWeVkyaGhiblF0YTJWNUxURWlmUS5leUpwWkNJNklDSXdPVFF4TkRFME5TMWlOekJpTFRRNE0yRXRZamcxWXkxaFlUQm1ZVEJqTkRVNE1EQWlMQ0FpYldWeVkyaGhiblFpT2lCN0ltbGtJam9nSW0xbGNtTm9ZVzUwWHpFaUxDQWlibUZ0WlNJNklDSkVaVzF2SUUxbGNtTm9ZVzUwSWl3Z0luZGxZbk5wZEdVaU9pQWlhSFIwY0hNNkx5OWtaVzF2TFcxbGNtTm9ZVzUwTG1WNFlXMXdiR1VpZlN3Z0lteHBibVZmYVhSbGJYTWlPaUJiZXlKcFpDSTZJQ0pzYVY4d0lpd2dJbWwwWlcwaU9pQjdJbWxrSWpvZ0luTjFjR1Z5YzJodlpWOXNhVzFwZEdWa1gyVmthWFJwYjI1ZloyOXNaRjl6Ym1WaGEyVnlYM2R2YldWdWMxODVYekFpTENBaWRHbDBiR1VpT2lBaVUzVndaWEp6YUc5bElFeHBiV2wwWldRZ1JXUnBkR2x2YmlCSGIyeGtJRk51WldGclpYSWdWMjl0Wlc1eklEa2lMQ0FpY0hKcFkyVWlPaUF4T1Rrd01IMHNJQ0p4ZFdGdWRHbDBlU0k2SURFc0lDSjBiM1JoYkhNaU9pQmJleUowZVhCbElqb2dJbk4xWW5SdmRHRnNJaXdnSW1GdGIzVnVkQ0k2SURFNU9UQXdmU3dnZXlKMGVYQmxJam9nSW5SdmRHRnNJaXdnSW1GdGIzVnVkQ0k2SURFNU9UQXdmVjE5WFN3Z0luTjBZWFIxY3lJNklDSnBibU52YlhCc1pYUmxJaXdnSW1OMWNuSmxibU41SWpvZ0lsVlRSQ0lzSUNKMGIzUmhiSE1pT2lCYmV5SjBlWEJsSWpvZ0luTjFZblJ2ZEdGc0lpd2dJbUZ0YjNWdWRDSTZJREU1T1RBd2ZTd2dleUowZVhCbElqb2dJblJ2ZEdGc0lpd2dJbUZ0YjNWdWRDSTZJREU1T1RBd2ZWMHNJQ0pzYVc1cmN5STZJRnQ3SW5SNWNHVWlPaUFpY0hKcGRtRmplVjl3YjJ4cFkza2lMQ0FpZFhKc0lqb2dJbWgwZEhCek9pOHZhSFIwY0hNdkwyUmxiVzh0YldWeVkyaGhiblF1WlhoaGJYQnNaUzl3Y21sMllXTjVJbjBzSUhzaWRIbHdaU0k2SUNKMFpYSnRjMTl2Wmw5elpYSjJhV05sSWl3Z0luVnliQ0k2SUNKb2RIUndjem92TDJoMGRIQnpMeTlrWlcxdkxXMWxjbU5vWVc1MExtVjRZVzF3YkdVdmRHOXpJbjFkZlEuUC1WS3poeUp1bzktUlBpTjVheW5naDdmTFVLY09QQWVaejczU09Zd2Q1UDlZWG1HTE9yTFRXeGdYdkd5UVF0dERETTVELUc0czE5dnhfVTY1ZHJ1UmciXQ~
```

<!-- cspell:enable -->

## Common Types

### Item

{{ schema_fields('open_checkout_mandate', 'ap2', show_sd=True,
pointer='#/$defs/item') }}

### LineItemRequirements

{{ schema_fields('open_checkout_mandate', 'ap2', show_sd=True,
pointer='#/$defs/line_item_requirements') }}

### Merchant

{{ schema_fields('types/merchant', 'ap2', show_sd=True) }}
