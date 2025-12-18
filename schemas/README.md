# AP2 JSON Schemas

This directory contains JSON Schema definitions for the Agent Payments Protocol (AP2) mandate types. These schemas provide language-agnostic specifications for validating AP2 mandate objects.

## Available Schemas

### Intent Mandate

- **File**: [`intent-mandate.schema.json`](./intent-mandate.schema.json)
- **Schema ID**: `https://raw.githubusercontent.com/google-agentic-commerce/AP2/main/schemas/intent-mandate.schema.json`
- **Description**: Represents the user's purchase intent, including constraints on merchants, SKUs, and refundability.

### Cart Mandate

- **File**: [`cart-mandate.schema.json`](./cart-mandate.schema.json)
- **Schema ID**: `https://raw.githubusercontent.com/google-agentic-commerce/AP2/main/schemas/cart-mandate.schema.json`
- **Description**: A cart whose contents have been digitally signed by the merchant, serving as a guarantee of items and price for a limited time.

### Payment Mandate

- **File**: [`payment-mandate.schema.json`](./payment-mandate.schema.json)
- **Schema ID**: `https://raw.githubusercontent.com/google-agentic-commerce/AP2/main/schemas/payment-mandate.schema.json`
- **Description**: Contains the user's instructions and authorization for payment, shared with the payments ecosystem.

## Usage

### Validating JSON Objects

These schemas can be used with any JSON Schema validator to ensure mandate objects conform to the AP2 specification.

#### Python Example

```python
import json
import jsonschema
import requests

# Load the schema
schema_url = "https://raw.githubusercontent.com/google-agentic-commerce/AP2/main/schemas/intent-mandate.schema.json"
schema = requests.get(schema_url).json()

# Your mandate object
mandate = {
    "natural_language_description": "High top, old school, red basketball shoes",
    "intent_expiry": "2025-12-31T23:59:59Z",
    "user_cart_confirmation_required": True
}

# Validate
jsonschema.validate(instance=mandate, schema=schema)
print("✓ Mandate is valid!")
```

#### JavaScript/TypeScript Example

```typescript
import Ajv from 'ajv';

const ajv = new Ajv();

// Load schema
const schema = await fetch(
  'https://raw.githubusercontent.com/google-agentic-commerce/AP2/main/schemas/intent-mandate.schema.json'
).then(r => r.json());

const validate = ajv.compile(schema);

const mandate = {
  natural_language_description: "High top, old school, red basketball shoes",
  intent_expiry: "2025-12-31T23:59:59Z",
  user_cart_confirmation_required: true
};

if (validate(mandate)) {
  console.log('✓ Mandate is valid!');
} else {
  console.error('Validation errors:', validate.errors);
}
```

#### Go Example

```go
import (
    "encoding/json"
    "github.com/xeipuuv/gojsonschema"
)

// Load schema
schemaLoader := gojsonschema.NewReferenceLoader(
    "https://raw.githubusercontent.com/google-agentic-commerce/AP2/main/schemas/intent-mandate.schema.json",
)

// Your mandate
mandate := map[string]interface{}{
    "natural_language_description": "High top, old school, red basketball shoes",
    "intent_expiry": "2025-12-31T23:59:59Z",
    "user_cart_confirmation_required": true,
}
mandateLoader := gojsonschema.NewGoLoader(mandate)

// Validate
result, _ := gojsonschema.Validate(schemaLoader, mandateLoader)

if result.Valid() {
    fmt.Println("✓ Mandate is valid!")
} else {
    fmt.Println("Validation errors:")
    for _, err := range result.Errors() {
        fmt.Printf("- %s\n", err)
    }
}
```

### Generating Type Definitions

You can use tools like `json-schema-to-typescript` or `quicktype` to generate type definitions from these schemas:

```bash
# TypeScript
npx json-schema-to-typescript schemas/intent-mandate.schema.json > IntentMandate.ts

# Multiple languages with quicktype
quicktype schemas/intent-mandate.schema.json -o IntentMandate.swift
quicktype schemas/intent-mandate.schema.json -o IntentMandate.kt
```

### Using with Verifiable Credentials

These schemas are designed to work with Verifiable Credentials (VCs). When creating a VC that contains an AP2 mandate, reference the appropriate schema:

```json
{
  "@context": [
    "https://www.w3.org/2018/credentials/v1"
  ],
  "type": ["VerifiableCredential", "AP2IntentMandate"],
  "credentialSubject": {
    "$schema": "https://raw.githubusercontent.com/google-agentic-commerce/AP2/main/schemas/intent-mandate.schema.json",
    "natural_language_description": "High top, old school, red basketball shoes",
    "intent_expiry": "2025-12-31T23:59:59Z",
    "user_cart_confirmation_required": true
  }
}
```

## Regenerating Schemas

If the Python type definitions in [`src/ap2/types/mandate.py`](../src/ap2/types/mandate.py) are updated, you can regenerate these schemas by running:

```bash
python3 scripts/generate_schemas.py
```

This script uses Pydantic's built-in JSON Schema generation to ensure the schemas stay in sync with the Python implementation.

## Schema Versioning

These schemas follow the AP2 protocol versioning. When breaking changes are made to the protocol, new schema versions will be created with appropriate version tags.

## Related Documentation

- [AP2 Specification](../docs/specification.md) - Full protocol specification
- [A2A Extension](../docs/a2a-extension.md) - Details on using AP2 with A2A
- [Python Type Definitions](../src/ap2/types/) - Source Pydantic models

## Contributing

If you find issues with these schemas or have suggestions for improvements, please [open an issue](https://github.com/google-agentic-commerce/AP2/issues) or submit a pull request.
