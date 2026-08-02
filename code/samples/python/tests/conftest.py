"""Pytest configuration for the samples test-suite.

Adds the samples ``src`` directory to ``sys.path`` so role modules such as
``roles.x402_psp_mcp.server`` and the shared ``common`` package import
cleanly when the suite runs from ``code/samples/python``.
"""

import sys

from pathlib import Path


_SRC = Path(__file__).resolve().parent.parent / 'src'
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
