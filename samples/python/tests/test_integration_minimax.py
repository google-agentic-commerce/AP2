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

"""Integration tests for MiniMax LLM provider.

These tests require a live MiniMax API key set via MINIMAX_API_KEY.
They are skipped automatically when the key is not available.
"""

import json
import os
import unittest

_HAS_KEY = bool(os.environ.get("MINIMAX_API_KEY"))
_SKIP_REASON = "MINIMAX_API_KEY not set"


@unittest.skipUnless(_HAS_KEY, _SKIP_REASON)
class TestMiniMaxFunctionCalling(unittest.TestCase):
    """Integration: function-calling via MiniMax API."""

    def test_resolve_function_call(self):
        from common.minimax_client import minimax_resolve_function_call

        def search_products():
            """Search for products in the catalog based on user query."""
            pass

        def process_payment():
            """Process a payment transaction for the user's cart."""
            pass

        def get_shipping_info():
            """Get shipping options and delivery estimates."""
            pass

        result = minimax_resolve_function_call(
            model="MiniMax-M2.7",
            tools=[search_products, process_payment, get_shipping_info],
            system_prompt="You help users shop for products.",
            user_prompt="I want to find some running shoes",
        )
        self.assertIn(result, ["search_products", "process_payment", "get_shipping_info"])
        self.assertEqual(result, "search_products")

    def test_resolve_payment_tool(self):
        from common.minimax_client import minimax_resolve_function_call

        def search_products():
            """Search for products in the catalog."""
            pass

        def process_payment():
            """Process payment for the user's selected items and charge the credit card."""
            pass

        result = minimax_resolve_function_call(
            model="MiniMax-M2.7",
            tools=[search_products, process_payment],
            system_prompt="You help users complete purchases.",
            user_prompt="Please charge my credit card for the order",
        )
        # Model should return a valid tool name (non-deterministic).
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)


@unittest.skipUnless(_HAS_KEY, _SKIP_REASON)
class TestMiniMaxJsonGeneration(unittest.TestCase):
    """Integration: JSON generation via MiniMax API."""

    def test_generate_json_items(self):
        from common.minimax_client import minimax_generate_json

        result = minimax_generate_json(
            model="MiniMax-M2.7",
            prompt=(
                "Generate a JSON object with a key 'items' containing a list "
                "of exactly 2 product items. Each item must have 'label' "
                "(string, product name) and 'amount' (object with 'currency' "
                "string and 'value' number). The items should be running shoes."
            ),
        )
        self.assertIsInstance(result, dict)
        self.assertIn("items", result)
        items = result["items"]
        self.assertEqual(len(items), 2)
        for item in items:
            self.assertIn("label", item)
            self.assertIn("amount", item)
            self.assertIn("currency", item["amount"])
            self.assertIn("value", item["amount"])


@unittest.skipUnless(_HAS_KEY, _SKIP_REASON)
class TestMiniMaxProviderEndToEnd(unittest.TestCase):
    """Integration: end-to-end provider configuration."""

    def test_provider_config_flow(self):
        """Full flow: set env vars -> get provider -> get model -> call API."""
        with unittest.mock.patch.dict(
            os.environ,
            {"LLM_PROVIDER": "minimax", "MINIMAX_API_KEY": os.environ.get("MINIMAX_API_KEY", "")},
        ):
            from common.llm_config import get_model, get_provider, LLMProvider

            provider = get_provider()
            self.assertEqual(provider, LLMProvider.MINIMAX)

            model = get_model()
            self.assertEqual(model, "MiniMax-M2.7")

            from common.minimax_client import minimax_generate_json

            result = minimax_generate_json(
                model=model,
                prompt='Return a JSON object with key "status" set to "ok".',
            )
            self.assertEqual(result.get("status"), "ok")


if __name__ == "__main__":
    unittest.main()
