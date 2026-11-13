# SDK model generation

To generate pydantic models for use in sample code:

```sh
uv run --with datamodel-code-generator==0.87.0 python3 code/sdk/schemas/generate.py
```

The generator registers a pre-validation hook for payment constraints. It
requires a `type` on incoming constraint objects before generated defaults can
turn an unrecognized object into an empty constraint. Typed SDK constructors
retain their default type identifiers. Keep this hook when regenerating models;
the protocol schemas remain unchanged.
