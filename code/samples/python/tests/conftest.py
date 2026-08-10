"""Makes the samples src/ tree importable without installing ap2-samples."""

import sys

from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
