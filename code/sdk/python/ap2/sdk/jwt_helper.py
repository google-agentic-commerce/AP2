"""Helper functions for creating and verifying JWTs."""

import json

from typing import Any

from jwcrypto.jwk import JWK
from jwcrypto.jws import JWS


def create_jwt(
    header: dict[str, Any],
    payload: dict[str, Any],
    private_key: JWK,
) -> str:
    """Create a compact JWS (ES256).

    Args:
      header: The JWT header.
      payload: The JWT payload.
      private_key: The JWK private key to sign the JWT with.

    Returns:
      The compact JWS string.
    """
    jws = JWS(json.dumps(payload).encode('utf-8'))
    jws.add_signature(private_key, alg='ES256', protected=json.dumps(header))
    return jws.serialize(compact=True)


def verify_jwt(
    token: str,
    public_key: JWK,
) -> dict[str, Any]:
    """Verify a compact JWS (ES256) and return the payload.

    Args:
      token: The JWT string to verify.
      public_key: The JWK public key to verify the JWT with.

    Returns:
      The JWT payload as a dictionary.

    Raises:
      ValueError: If the JWT format is invalid or the signature is invalid.
      InvalidSignature: If the JWT signature is invalid.
    """
    jws = JWS()
    jws.deserialize(token)
    jws.verify(public_key)
    return json.loads(jws.payload.decode('utf-8'))
