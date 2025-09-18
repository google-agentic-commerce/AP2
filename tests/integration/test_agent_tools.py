"""Integration tests for agent tools and functionality."""

import pytest
from unittest.mock import Mock, patch

# Import actual agent tools to test
from samples.python.src.roles.merchant_agent import tools as merchant_tools
from samples.python.src.common.base_server_executor import BaseServerExecutor


class TestMerchantAgentTools:
    """Test merchant agent tools integration."""

    def test_payment_processors_mapping_exists(self):
        """Test that payment processor mapping is available."""
        # Check if the payment processor mapping exists
        assert hasattr(merchant_tools, '_PAYMENT_PROCESSORS_BY_PAYMENT_METHOD_TYPE')
        processors = merchant_tools._PAYMENT_PROCESSORS_BY_PAYMENT_METHOD_TYPE
        assert 'CARD' in processors
        assert processors['CARD'] == 'http://localhost:8003/a2a/merchant_payment_processor_agent'

    @pytest.mark.integration
    def test_merchant_tools_imports(self):
        """Test that merchant tools can import required dependencies."""
        # Test that all required imports work
        from ap2.types.mandate import CART_MANDATE_DATA_KEY, PAYMENT_MANDATE_DATA_KEY
        from ap2.types.payment_request import PaymentCurrencyAmount, PaymentItem
        from common import message_utils
        from common.a2a_message_builder import A2aMessageBuilder

        assert CART_MANDATE_DATA_KEY == "ap2.mandates.CartMandate"
        assert PAYMENT_MANDATE_DATA_KEY == "ap2.mandates.PaymentMandate"


class TestBaseServerExecutor:
    """Test base server executor functionality."""

    def test_base_server_executor_imports(self):
        """Test that BaseServerExecutor can import its dependencies."""
        # Test critical imports work
        from a2a.server.agent_execution.agent_executor import AgentExecutor
        from a2a.types import Task, TextPart, Part
        from ap2.types.mandate import PaymentMandate

        # These should not raise import errors
        assert AgentExecutor is not None
        assert Task is not None
        assert PaymentMandate is not None

    @pytest.mark.integration
    def test_function_call_resolver_available(self):
        """Test that FunctionCallResolver is available."""
        from common.function_call_resolver import FunctionCallResolver
        assert FunctionCallResolver is not None


class TestCommonUtilities:
    """Test common utility modules."""

    def test_message_utils_import(self):
        """Test message utilities are available."""
        from common import message_utils
        assert message_utils is not None

    def test_validation_import(self):
        """Test validation utilities are available."""
        from common.validation import validate_payment_mandate_signature
        assert validate_payment_mandate_signature is not None

    def test_watch_log_import(self):
        """Test watch log utilities are available."""
        from common import watch_log
        assert watch_log is not None

    def test_a2a_extensions_import(self):
        """Test A2A extension utilities are available."""
        from common.a2a_extension_utils import EXTENSION_URI
        assert EXTENSION_URI is not None