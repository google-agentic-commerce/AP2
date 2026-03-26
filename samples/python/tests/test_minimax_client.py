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

"""Unit tests for common.minimax_client."""

import json
import os
import unittest
from unittest import mock

from common.minimax_client import _strip_think_tags
from common.minimax_client import MINIMAX_BASE_URL


class TestStripThinkTags(unittest.TestCase):
    """Tests for the _strip_think_tags helper."""

    def test_no_tags(self):
        self.assertEqual(_strip_think_tags("Hello world"), "Hello world")

    def test_single_tag(self):
        self.assertEqual(
            _strip_think_tags("<think>reasoning</think>Answer"),
            "Answer",
        )

    def test_multiline_tag(self):
        text = "<think>\nline1\nline2\n</think>\nResult"
        self.assertEqual(_strip_think_tags(text), "Result")

    def test_multiple_tags(self):
        text = "<think>a</think>X<think>b</think>Y"
        self.assertEqual(_strip_think_tags(text), "XY")

    def test_empty_tag(self):
        self.assertEqual(_strip_think_tags("<think></think>clean"), "clean")

    def test_strips_whitespace(self):
        self.assertEqual(
            _strip_think_tags("  <think>x</think>  result  "),
            "result",
        )


class TestGetClient(unittest.TestCase):
    """Tests for MiniMax client creation."""

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_missing_api_key_raises(self):
        from common.minimax_client import _get_client

        with self.assertRaises(ValueError) as ctx:
            _get_client()
        self.assertIn("MINIMAX_API_KEY", str(ctx.exception))

    @mock.patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"})
    def test_client_created_with_base_url(self):
        from common.minimax_client import _get_client

        client = _get_client()
        self.assertEqual(str(client.base_url).rstrip("/"), MINIMAX_BASE_URL)


class TestMinimaxResolveFunction(unittest.TestCase):
    """Tests for minimax_resolve_function_call."""

    @mock.patch("common.minimax_client._get_client")
    def test_returns_tool_name(self, mock_get_client):
        """Verify the function extracts the tool name from the response."""
        mock_client = mock.MagicMock()
        mock_get_client.return_value = mock_client

        mock_tool_call = mock.MagicMock()
        mock_tool_call.function.name = "find_items_workflow"

        mock_message = mock.MagicMock()
        mock_message.tool_calls = [mock_tool_call]

        mock_choice = mock.MagicMock()
        mock_choice.message = mock_message

        mock_response = mock.MagicMock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        def find_items_workflow():
            """Finds items."""
            pass

        def process_payment():
            """Processes payment."""
            pass

        from common.minimax_client import minimax_resolve_function_call

        result = minimax_resolve_function_call(
            model="MiniMax-M2.7",
            tools=[find_items_workflow, process_payment],
            system_prompt="You are helpful.",
            user_prompt="Find me shoes",
        )
        self.assertEqual(result, "find_items_workflow")

        call_args = mock_client.chat.completions.create.call_args
        self.assertEqual(call_args.kwargs["model"], "MiniMax-M2.7")
        self.assertEqual(call_args.kwargs["tool_choice"], "required")
        tools_sent = call_args.kwargs["tools"]
        self.assertEqual(len(tools_sent), 2)
        self.assertEqual(tools_sent[0]["function"]["name"], "find_items_workflow")
        self.assertEqual(tools_sent[1]["function"]["name"], "process_payment")

    @mock.patch("common.minimax_client._get_client")
    def test_returns_unknown_on_no_tool_calls(self, mock_get_client):
        mock_client = mock.MagicMock()
        mock_get_client.return_value = mock_client

        mock_message = mock.MagicMock()
        mock_message.tool_calls = None

        mock_choice = mock.MagicMock()
        mock_choice.message = mock_message

        mock_response = mock.MagicMock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        from common.minimax_client import minimax_resolve_function_call

        result = minimax_resolve_function_call(
            model="MiniMax-M2.7",
            tools=[lambda: None],
            system_prompt="test",
            user_prompt="test",
        )
        self.assertEqual(result, "Unknown")

    @mock.patch("common.minimax_client._get_client")
    def test_returns_unknown_on_empty_choices(self, mock_get_client):
        mock_client = mock.MagicMock()
        mock_get_client.return_value = mock_client

        mock_response = mock.MagicMock()
        mock_response.choices = []

        mock_client.chat.completions.create.return_value = mock_response

        from common.minimax_client import minimax_resolve_function_call

        result = minimax_resolve_function_call(
            model="MiniMax-M2.7",
            tools=[lambda: None],
            system_prompt="test",
            user_prompt="test",
        )
        self.assertEqual(result, "Unknown")


class TestMinimaxGenerateJson(unittest.TestCase):
    """Tests for minimax_generate_json."""

    @mock.patch("common.minimax_client._get_client")
    def test_returns_parsed_json(self, mock_get_client):
        mock_client = mock.MagicMock()
        mock_get_client.return_value = mock_client

        expected = {"items": [{"label": "Shoes", "amount": {"currency": "USD", "value": 99.99}}]}
        mock_message = mock.MagicMock()
        mock_message.content = json.dumps(expected)

        mock_choice = mock.MagicMock()
        mock_choice.message = mock_message

        mock_response = mock.MagicMock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        from common.minimax_client import minimax_generate_json

        result = minimax_generate_json(
            model="MiniMax-M2.7",
            prompt="Generate items",
        )
        self.assertEqual(result, expected)

        call_args = mock_client.chat.completions.create.call_args
        self.assertEqual(call_args.kwargs["response_format"], {"type": "json_object"})

    @mock.patch("common.minimax_client._get_client")
    def test_strips_think_tags(self, mock_get_client):
        mock_client = mock.MagicMock()
        mock_get_client.return_value = mock_client

        mock_message = mock.MagicMock()
        mock_message.content = '<think>reasoning here</think>{"result": true}'

        mock_choice = mock.MagicMock()
        mock_choice.message = mock_message

        mock_response = mock.MagicMock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        from common.minimax_client import minimax_generate_json

        result = minimax_generate_json(
            model="MiniMax-M2.7",
            prompt="test",
        )
        self.assertEqual(result, {"result": True})

    @mock.patch("common.minimax_client._get_client")
    def test_system_prompt_included(self, mock_get_client):
        mock_client = mock.MagicMock()
        mock_get_client.return_value = mock_client

        mock_message = mock.MagicMock()
        mock_message.content = "{}"

        mock_choice = mock.MagicMock()
        mock_choice.message = mock_message

        mock_response = mock.MagicMock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        from common.minimax_client import minimax_generate_json

        minimax_generate_json(
            model="MiniMax-M2.7",
            prompt="test",
            system_prompt="You are a catalog agent.",
        )

        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[0]["content"], "You are a catalog agent.")

    @mock.patch("common.minimax_client._get_client")
    def test_no_system_prompt(self, mock_get_client):
        mock_client = mock.MagicMock()
        mock_get_client.return_value = mock_client

        mock_message = mock.MagicMock()
        mock_message.content = "{}"

        mock_choice = mock.MagicMock()
        mock_choice.message = mock_message

        mock_response = mock.MagicMock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        from common.minimax_client import minimax_generate_json

        minimax_generate_json(
            model="MiniMax-M2.7",
            prompt="test",
        )

        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "user")

    @mock.patch("common.minimax_client._get_client")
    def test_empty_content_returns_empty_dict(self, mock_get_client):
        mock_client = mock.MagicMock()
        mock_get_client.return_value = mock_client

        mock_message = mock.MagicMock()
        mock_message.content = None

        mock_choice = mock.MagicMock()
        mock_choice.message = mock_message

        mock_response = mock.MagicMock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        from common.minimax_client import minimax_generate_json

        result = minimax_generate_json(
            model="MiniMax-M2.7",
            prompt="test",
        )
        self.assertEqual(result, {})

    @mock.patch("common.minimax_client._get_client")
    def test_temperature_clamped(self, mock_get_client):
        mock_client = mock.MagicMock()
        mock_get_client.return_value = mock_client

        mock_message = mock.MagicMock()
        mock_message.content = "{}"

        mock_choice = mock.MagicMock()
        mock_choice.message = mock_message

        mock_response = mock.MagicMock()
        mock_response.choices = [mock_choice]

        mock_client.chat.completions.create.return_value = mock_response

        from common.minimax_client import minimax_generate_json

        minimax_generate_json(model="MiniMax-M2.7", prompt="test")

        call_args = mock_client.chat.completions.create.call_args
        temp = call_args.kwargs["temperature"]
        self.assertGreater(temp, 0.0)
        self.assertLessEqual(temp, 1.0)


class TestConstants(unittest.TestCase):
    """Tests for module-level constants."""

    def test_base_url(self):
        self.assertEqual(MINIMAX_BASE_URL, "https://api.minimax.io/v1")


if __name__ == "__main__":
    unittest.main()
