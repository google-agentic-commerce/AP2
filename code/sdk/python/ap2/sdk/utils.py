"""Shared utilities for the AP2 SDK."""

from __future__ import annotations

import base64
import hashlib

from ap2.sdk.generated.types.jwk import JsonWebKey
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


# base64url (RFC 4648 §5) encodes 3 input bytes into 4 output chars.
_B64_BLOCK_LEN = 4

# ANSI X9.62 uncompressed EC point: 0x04 || X || Y, 65 bytes for P-256.
_P256_UNCOMPRESSED_POINT_LEN = 65
_X962_UNCOMPRESSED_TAG = 0x04


def b64url_encode(data: bytes) -> str:
    """Base64url-encode bytes without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def b64url_decode(s: str) -> bytes:
    """Base64url-decode a string, adding padding as needed."""
    pad = _B64_BLOCK_LEN - len(s) % _B64_BLOCK_LEN
    if pad != _B64_BLOCK_LEN:
        s += '=' * pad
    return base64.urlsafe_b64decode(s)


def compute_sha256_b64url(data: str) -> str:
    """Return the base64url-encoded SHA-256 digest of ``data``."""
    return b64url_encode(hashlib.sha256(data.encode()).digest())


def ec_key_to_jwk(pub: ec.EllipticCurvePublicKey) -> JsonWebKey:
    """Export an EC P-256 public key to a typed JsonWebKey model."""
    raw = pub.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    if (
        len(raw) != _P256_UNCOMPRESSED_POINT_LEN
        or raw[0] != _X962_UNCOMPRESSED_TAG
    ):
        raise ValueError('Expected uncompressed P-256 point (65 bytes)')
    return JsonWebKey(
        kty='EC',
        crv='P-256',
        x=b64url_encode(raw[1:33]),
        y=b64url_encode(raw[33:65]),
    )
