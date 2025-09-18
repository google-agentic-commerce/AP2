"""Pytest configuration and shared fixtures."""

import pytest


@pytest.fixture(scope="session")
def google_api_key():
    """Google API key fixture for tests that need it."""
    import os

    key = os.getenv("GOOGLE_API_KEY")
    if not key:
        pytest.skip("GOOGLE_API_KEY not set")
    return key


@pytest.fixture
def sample_payment_request():
    """Sample payment request for testing."""
    from ap2.types.payment_request import PaymentRequest

    return {
        "amount": "10.00",
        "currency": "USD",
        "merchant_id": "test_merchant",
        "description": "Test payment"
    }
