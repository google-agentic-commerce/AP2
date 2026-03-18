#!/bin/bash

# A script to automate the execution of the x402 payment example.
# This is a convenience wrapper that runs the standard scenario with
# the x402 payment method.

SCRIPT_DIR="$(dirname "$0")"
exec bash "$SCRIPT_DIR/../cards/run.sh" --payment-method x402 "$@"
