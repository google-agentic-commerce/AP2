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

"""Unit tests for common.function_call_resolver with provider routing."""

import os
import unittest
from unittest import mock

from common.llm_config import LLMProvider


class TestFunctionCallResolverProviderRouting(unittest.TestCase):
    """Tests that FunctionCallResolver routes to the correct backend."""

    @mock.patch.dict(os.environ, {"LLM_PROVIDER": "google"}, clear=False)
    @mock.patch("common.function_call_resolver.get_provider", return_value=LLMProvider.GOOGLE)
    @mock.patch("common.function_call_resolver.get_model", return_value="gemini-2.5-flash")
    def test_google_provider_uses_genai(self, mock_model, mock_provider):
        """When provider is Google, _determine_tool_google is called."""
        mock_client = mock.MagicMock()

        from common.function_call_resolver import FunctionCallResolver

        def dummy_tool():
            """A test tool."""
            pass

        resolver = FunctionCallResolver(
            llm_client=mock_client,
            tools=[dummy_tool],
            instructions="test",
        )

        mock_part = mock.MagicMock()
        mock_part.function_call.name = "dummy_tool"
        mock_content = mock.MagicMock()
        mock_content.parts = [mock_part]
        mock_candidate = mock.MagicMock()
        mock_candidate.content = mock_content
        mock_response = mock.MagicMock()
        mock_response.candidates = [mock_candidate]
        mock_client.models.generate_content.return_value = mock_response

        result = resolver.determine_tool_to_use("test prompt")
        self.assertEqual(result, "dummy_tool")
        mock_client.models.generate_content.assert_called_once()

    @mock.patch.dict(os.environ, {"LLM_PROVIDER": "minimax", "MINIMAX_API_KEY": "test"}, clear=False)
    @mock.patch("common.function_call_resolver.get_provider", return_value=LLMProvider.MINIMAX)
    @mock.patch("common.function_call_resolver.get_model", return_value="MiniMax-M2.7")
    @mock.patch("common.minimax_client.minimax_resolve_function_call", return_value="my_tool")
    def test_minimax_provider_uses_openai(self, mock_resolve, mock_model, mock_provider):
        """When provider is MiniMax, minimax_resolve_function_call is called."""
        from common.function_call_resolver import FunctionCallResolver

        def my_tool():
            """A test tool."""
            pass

        resolver = FunctionCallResolver(
            llm_client=None,
            tools=[my_tool],
            instructions="test prompt",
        )

        result = resolver.determine_tool_to_use("find me items")
        self.assertEqual(result, "my_tool")
        mock_resolve.assert_called_once()

    @mock.patch.dict(os.environ, {"LLM_PROVIDER": "google"}, clear=False)
    @mock.patch("common.function_call_resolver.get_provider", return_value=LLMProvider.GOOGLE)
    @mock.patch("common.function_call_resolver.get_model", return_value="gemini-2.5-flash")
    def test_google_returns_unknown_on_empty(self, mock_model, mock_provider):
        """When Google returns no function call, Unknown is returned."""
        mock_client = mock.MagicMock()

        from common.function_call_resolver import FunctionCallResolver

        def dummy_tool():
            """A test tool."""
            pass

        resolver = FunctionCallResolver(
            llm_client=mock_client,
            tools=[dummy_tool],
            instructions="test",
        )

        mock_response = mock.MagicMock()
        mock_response.candidates = []
        mock_client.models.generate_content.return_value = mock_response

        result = resolver.determine_tool_to_use("test prompt")
        self.assertEqual(result, "Unknown")

    @mock.patch.dict(os.environ, {"LLM_PROVIDER": "google"}, clear=False)
    @mock.patch("common.function_call_resolver.get_provider", return_value=LLMProvider.GOOGLE)
    @mock.patch("common.function_call_resolver.get_model", return_value="gemini-2.5-flash")
    def test_google_uses_configured_model(self, mock_model, mock_provider):
        """Verifies the model from get_model() is used in the API call."""
        mock_client = mock.MagicMock()

        from common.function_call_resolver import FunctionCallResolver

        def dummy_tool():
            """A test tool."""
            pass

        resolver = FunctionCallResolver(
            llm_client=mock_client,
            tools=[dummy_tool],
        )

        mock_part = mock.MagicMock()
        mock_part.function_call.name = "dummy_tool"
        mock_content = mock.MagicMock()
        mock_content.parts = [mock_part]
        mock_candidate = mock.MagicMock()
        mock_candidate.content = mock_content
        mock_response = mock.MagicMock()
        mock_response.candidates = [mock_candidate]
        mock_client.models.generate_content.return_value = mock_response

        resolver.determine_tool_to_use("test")

        call_args = mock_client.models.generate_content.call_args
        self.assertEqual(call_args.kwargs["model"], "gemini-2.5-flash")


class TestFunctionCallResolverInit(unittest.TestCase):
    """Tests for FunctionCallResolver initialization."""

    @mock.patch.dict(os.environ, {"LLM_PROVIDER": "minimax"}, clear=False)
    @mock.patch("common.function_call_resolver.get_provider", return_value=LLMProvider.MINIMAX)
    @mock.patch("common.function_call_resolver.get_model", return_value="MiniMax-M2.7")
    def test_minimax_init_skips_genai_config(self, mock_model, mock_provider):
        """MiniMax provider should not create Google-specific config."""
        from common.function_call_resolver import FunctionCallResolver

        def dummy():
            """test"""
            pass

        resolver = FunctionCallResolver(
            llm_client=None, tools=[dummy], instructions="test"
        )
        self.assertFalse(hasattr(resolver, "_config"))

    @mock.patch.dict(os.environ, {"LLM_PROVIDER": "google"}, clear=False)
    @mock.patch("common.function_call_resolver.get_provider", return_value=LLMProvider.GOOGLE)
    @mock.patch("common.function_call_resolver.get_model", return_value="gemini-2.5-flash")
    def test_google_init_creates_config(self, mock_model, mock_provider):
        """Google provider should create the function calling config."""
        mock_client = mock.MagicMock()

        from common.function_call_resolver import FunctionCallResolver

        def dummy():
            """test"""
            pass

        resolver = FunctionCallResolver(
            llm_client=mock_client, tools=[dummy], instructions="test"
        )
        self.assertTrue(hasattr(resolver, "_config"))


if __name__ == "__main__":
    unittest.main()
