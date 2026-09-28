"""Sensitive A2A values must not enter the watch log."""

import logging

from io import StringIO

from common import watch_log


def test_a2a_parts_log_counts_not_values():
  secret = "SENSITIVE_PAYMENT_TOKEN_123"
  output = StringIO()
  handler = logging.StreamHandler(output)
  watch_log._logger.addHandler(handler)
  old_level = watch_log._logger.level
  watch_log._logger.setLevel(logging.INFO)
  try:
    watch_log.log_a2a_message_parts(
        [f"Text containing {secret}"],
        [
            {secret: "unknown field", "risk_data": secret},
            {"checkout_mandate": secret},
        ],
    )
  finally:
    watch_log._logger.removeHandler(handler)
    watch_log._logger.setLevel(old_level)
  logged = output.getvalue()
  assert secret not in logged
  assert "text_parts=1 data_parts=2" in logged
  assert "fields=2" in logged
  assert "fields=1" in logged
