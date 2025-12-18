#!/usr/bin/env python3
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Generate JSON Schema definitions for AP2 mandate types.

This script generates JSON Schema files from the Pydantic models defined in
the AP2 types package. These schemas can be used for validation in any
programming language and are essential for Verifiable Credential implementations.

Usage:
    python scripts/generate_schemas.py

Requirements:
    pip install pydantic --break-system-packages --user
    or use: uv pip install pydantic
"""

import json
import sys
import textwrap
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    # Import the mandate types
    from ap2.types.mandate import CartMandate
    from ap2.types.mandate import IntentMandate
    from ap2.types.mandate import PaymentMandate
except ImportError as e:
    print(f"Error importing AP2 types: {e}")
    print("\nPlease install pydantic:")
    print("  pip install pydantic --break-system-packages --user")
    print("  or: uv pip install pydantic")
    sys.exit(1)


def generate_schema(model_class, output_path: Path, schema_id: str) -> None:
    """Generate JSON Schema for a Pydantic model and write to file.

    Args:
        model_class: The Pydantic model class to generate schema from.
        output_path: Path where the schema file should be written.
        schema_id: The $id for the JSON Schema.
    """
    # Generate the schema using Pydantic's built-in method
    schema = model_class.model_json_schema(mode="serialization")

    # Post-process the schema to improve formatting and add details
    def _post_process(node):
        if isinstance(node, dict):
            if "description" in node and isinstance(node["description"], str):
                node["description"] = textwrap.dedent(node["description"]).strip()

            if "properties" in node and isinstance(node["properties"], dict):
                for prop_name, prop_schema in node["properties"].items():
                    if prop_name in ("intent_expiry", "cart_expiry", "timestamp"):
                        if prop_schema.get("type") == "string":
                            prop_schema["format"] = "date-time"

            for value in node.values():
                _post_process(value)
        elif isinstance(node, list):
            for item in node:
                _post_process(item)

    _post_process(schema)

    # Add $schema and $id fields for proper JSON Schema compliance
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = schema_id

    # Add metadata
    schema["title"] = model_class.__name__
    if model_class.__doc__:
        schema["description"] = textwrap.dedent(model_class.__doc__).strip()

    # Write schema to file with pretty formatting
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
        f.write("\n")  # Add trailing newline

    print(f"✓ Generated {output_path}")


def main():
    """Generate all mandate JSON schemas."""
    # Define the output directory
    schemas_dir = Path(__file__).parent.parent / "schemas"

    # Define the base URL for schema IDs (can be updated when hosted publicly)
    base_url = "https://raw.githubusercontent.com/google-agentic-commerce/AP2/main/schemas"

    # Generate schemas for each mandate type
    schemas_to_generate = [
        {
            "model": IntentMandate,
            "filename": "intent-mandate.schema.json",
            "id": f"{base_url}/intent-mandate.schema.json",
        },
        {
            "model": CartMandate,
            "filename": "cart-mandate.schema.json",
            "id": f"{base_url}/cart-mandate.schema.json",
        },
        {
            "model": PaymentMandate,
            "filename": "payment-mandate.schema.json",
            "id": f"{base_url}/payment-mandate.schema.json",
        },
    ]

    print("Generating JSON Schemas for AP2 mandate types...\n")

    for schema_config in schemas_to_generate:
        output_path = schemas_dir / schema_config["filename"]
        generate_schema(
            schema_config["model"],
            output_path,
            schema_config["id"],
        )

    print(f"\n✓ All schemas generated successfully in {schemas_dir}/")
    print("\nThese schemas can be used for:")
    print("  • Validating mandate objects in any programming language")
    print("  • Generating type definitions for non-Python implementations")
    print("  • Creating Verifiable Credentials with proper schema references")
    print("  • IDE autocomplete and validation support")


if __name__ == "__main__":
    main()
