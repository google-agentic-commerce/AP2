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

"""Unit tests for common.llm_config."""

import os
import unittest
from unittest import mock

from common.llm_config import LLMProvider
from common.llm_config import get_model
from common.llm_config import get_provider


class TestGetProvider(unittest.TestCase):
    """Tests for get_provider()."""

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_default_provider_is_google(self):
        self.assertEqual(get_provider(), LLMProvider.GOOGLE)

    @mock.patch.dict(os.environ, {"LLM_PROVIDER": "google"})
    def test_explicit_google(self):
        self.assertEqual(get_provider(), LLMProvider.GOOGLE)

    @mock.patch.dict(os.environ, {"LLM_PROVIDER": "minimax"})
    def test_minimax_provider(self):
        self.assertEqual(get_provider(), LLMProvider.MINIMAX)

    @mock.patch.dict(os.environ, {"LLM_PROVIDER": "MINIMAX"})
    def test_case_insensitive(self):
        self.assertEqual(get_provider(), LLMProvider.MINIMAX)

    @mock.patch.dict(os.environ, {"LLM_PROVIDER": "  minimax  "})
    def test_strips_whitespace(self):
        self.assertEqual(get_provider(), LLMProvider.MINIMAX)

    @mock.patch.dict(os.environ, {"LLM_PROVIDER": "unsupported"})
    def test_unsupported_raises(self):
        with self.assertRaises(ValueError) as ctx:
            get_provider()
        self.assertIn("unsupported", str(ctx.exception).lower())


class TestGetModel(unittest.TestCase):
    """Tests for get_model()."""

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_default_google_model(self):
        self.assertEqual(get_model(), "gemini-2.5-flash")

    @mock.patch.dict(os.environ, {"LLM_PROVIDER": "minimax"}, clear=True)
    def test_default_minimax_model(self):
        self.assertEqual(get_model(), "MiniMax-M2.7")

    @mock.patch.dict(
        os.environ,
        {"LLM_PROVIDER": "minimax", "LLM_MODEL": "MiniMax-M2.7-highspeed"},
    )
    def test_explicit_model_overrides(self):
        self.assertEqual(get_model(), "MiniMax-M2.7-highspeed")

    @mock.patch.dict(os.environ, {"LLM_MODEL": "gemini-2.5-pro"})
    def test_explicit_model_with_google(self):
        self.assertEqual(get_model(), "gemini-2.5-pro")

    @mock.patch.dict(os.environ, {"LLM_MODEL": "  "}, clear=True)
    def test_blank_model_falls_back(self):
        self.assertEqual(get_model(), "gemini-2.5-flash")


class TestLLMProviderEnum(unittest.TestCase):
    """Tests for LLMProvider enum."""

    def test_google_value(self):
        self.assertEqual(LLMProvider.GOOGLE.value, "google")

    def test_minimax_value(self):
        self.assertEqual(LLMProvider.MINIMAX.value, "minimax")

    def test_from_string(self):
        self.assertEqual(LLMProvider("google"), LLMProvider.GOOGLE)
        self.assertEqual(LLMProvider("minimax"), LLMProvider.MINIMAX)


if __name__ == "__main__":
    unittest.main()
