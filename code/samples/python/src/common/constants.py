"""Shared constants for AP2 sample agents."""

import os

from pathlib import Path


PAYMENT_MANDATE_SD_JWT_KEY = "ap2.mandates.PaymentMandateSdJwt"
CHECKOUT_MANDATE_SD_JWT_KEY = "ap2.mandates.CheckoutMandateSdJwt"

TEMP_DB = Path(os.environ.get("TEMP_DB_DIR", ".temp-db"))
AGENT_PROVIDER_KEY_PATH = TEMP_DB / "agent_provider_signing_key.pem"
AGENT_PROVIDER_PUB_PATH = TEMP_DB / "agent_provider_signing_key.pub"
AGENT_KEY_PATH = TEMP_DB / "agent_signing_key.pem"
AGENT_PUB_PATH = TEMP_DB / "agent_signing_key.pub"
MERCHANT_KEY_PATH = TEMP_DB / "merchant_signing_key.pem"
MERCHANT_PUB_PATH = TEMP_DB / "merchant_signing_key.pub"
MERCHANT_PAYMENT_PROCESSOR_KEY_PATH = TEMP_DB / "merchant_payment_processor_signing_key.pem"
MERCHANT_PAYMENT_PROCESSOR_PUB_PATH = TEMP_DB / "merchant_payment_processor_signing_key.pub"

DEFAULT_MANDATE_TTL_SECONDS = 60 * 60

PAYMENT_RECEIPT_DATA_KEY = "ap2.PaymentReceipt"

CREDENTIALS_PROVIDER_PAYMENT_RECEIPT_URL = "http://localhost:8082/payment-receipt"
MERCHANT_PAYMENT_PROCESSOR_INITIATE_PAYMENT_URL = (
    "http://127.0.0.1:8083/initiate-payment"
)
