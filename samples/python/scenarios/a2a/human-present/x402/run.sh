#!/bin/bash
set -e

# A script to automate the execution of the x402 payment example.
# This is a convenience wrapper that runs the standard scenario with
# the x402 payment method.

# The wrapped script, cards/run.sh, expects to be run from the repository root.
# To make this script runnable from any directory, we first change to the repo root.
cd "$(dirname "$0")/../../../../../../"

exec bash "samples/python/scenarios/a2a/human-present/cards/run.sh" --payment-method x402 "$@"
