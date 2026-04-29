## how to test it:

Run from the repository root:

```bash
# Remove the broken virtual environment
rm -rf .venv

# Optional: Clean the uv cache to ensure fresh wheels
uv cache clean

# Rebuild environment and run tests
uv sync
uv run python -m pytest code/sdk/python/ap2/tests/ -v
```