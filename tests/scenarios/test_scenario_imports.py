"""Scenario tests that validate the sample implementations work."""

import pytest
import importlib
import sys
from pathlib import Path


class TestScenarioImports:
    """Test that all scenario components can be imported successfully."""

    def test_merchant_agent_import(self):
        """Test merchant agent can be imported."""
        try:
            from samples.python.src.roles.merchant_agent import agent_executor
            from samples.python.src.roles.merchant_agent import tools
            assert agent_executor is not None
            assert tools is not None
        except ImportError as e:
            pytest.fail(f"Failed to import merchant agent: {e}")

    def test_credentials_provider_agent_import(self):
        """Test credentials provider agent can be imported."""
        try:
            from samples.python.src.roles.credentials_provider_agent import agent_executor
            assert agent_executor is not None
        except ImportError as e:
            pytest.fail(f"Failed to import credentials provider agent: {e}")

    def test_merchant_payment_processor_agent_import(self):
        """Test merchant payment processor agent can be imported."""
        try:
            from samples.python.src.roles.merchant_payment_processor_agent import agent_executor
            from samples.python.src.roles.merchant_payment_processor_agent import tools
            assert agent_executor is not None
            assert tools is not None
        except ImportError as e:
            pytest.fail(f"Failed to import merchant payment processor agent: {e}")

    def test_shopping_agent_tools_import(self):
        """Test shopping agent tools can be imported."""
        try:
            from samples.python.src.roles.shopping_agent import tools
            assert tools is not None
        except ImportError as e:
            pytest.fail(f"Failed to import shopping agent tools: {e}")


class TestScenarioConfiguration:
    """Test scenario configuration and setup."""

    @pytest.mark.scenario
    def test_environment_requirements(self):
        """Test that environment is set up correctly for scenarios."""
        import os

        # We don't require GOOGLE_API_KEY for unit tests, but should note when missing
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            pytest.skip("GOOGLE_API_KEY not set - scenario tests require API key")

    @pytest.mark.scenario
    def test_agent_main_modules_exist(self):
        """Test that agent main modules exist and can be imported."""
        agent_modules = [
            "samples.python.src.roles.merchant_agent.__main__",
            "samples.python.src.roles.credentials_provider_agent.__main__",
            "samples.python.src.roles.merchant_payment_processor_agent.__main__",
        ]

        for module_name in agent_modules:
            try:
                importlib.import_module(module_name)
            except ImportError as e:
                pytest.fail(f"Failed to import {module_name}: {e}")


class TestScenarioStructure:
    """Test that scenario directory structure is correct."""

    def test_scenario_directories_exist(self):
        """Test that expected scenario directories exist."""
        base_path = Path("samples/python/scenarios")
        expected_scenarios = [
            "a2a/human-present/cards",
            # "a2a/human-present/x402"  # Comment out until this scenario exists
        ]

        for scenario in expected_scenarios:
            scenario_path = base_path / scenario
            assert scenario_path.exists(), f"Scenario directory {scenario_path} does not exist"

            # Check for run.sh script
            run_script = scenario_path / "run.sh"
            assert run_script.exists(), f"Run script {run_script} does not exist"

    def test_android_scenarios_exist(self):
        """Test that Android scenario directories exist."""
        android_base = Path("samples/android/scenarios")
        expected_android_scenarios = [
            "digital-payment-credentials"
        ]

        for scenario in expected_android_scenarios:
            scenario_path = android_base / scenario
            assert scenario_path.exists(), f"Android scenario {scenario_path} does not exist"