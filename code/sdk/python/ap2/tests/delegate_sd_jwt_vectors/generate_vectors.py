"""Generator for versioned delegate-SD-JWT (dSD-JWT) golden vectors.

This mints a keyed, versioned golden-vector set for the **delegation chain
layer** of AP2 mandates — the layer that travels on the SD-JWT ``~~`` wire
(picks up issue #303 / Discussion #262). Every vector is produced by the
*real* AP2 reference SDK (``ap2.sdk``), never by hand-forged strings, so the
committed serializations are authoritative.

What is covered:

- ``root-single-sd-jwt`` — a single, un-delegated root SD-JWT. Demonstrates the
  RFC 9901 rule that a lone SD-JWT ends with exactly one ``~`` and carries zero
  ``~~`` chain joins.
- ``single-hop-payment-chain`` — one delegation hop appended with the public
  ``MandateClient.present(...)`` API (open payment mandate -> closed payment
  mandate). Exactly one ``~~`` join, two resolved payloads.
- ``multi-hop-payment-chain`` — the canonical Bank -> SA -> CP -> Merchant
  three-segment chain (two ``~~`` joins, three resolved payloads), minted hop
  by hop with the SDK's ``sd_jwt.create`` + ``kb_sd_jwt.create`` primitives and
  joined on the ``~~`` wire exactly as the reference does.
- ``single-hop-checkout-chain`` — the same one-hop delegation for the *checkout*
  mandate family (open checkout mandate -> closed checkout mandate), covering
  the second mandate type called out in #303.

REPRODUCIBILITY
---------------
Keys are PINNED (see ``PINNED_KEYS`` below) and embedded in every vector, so
signature verification against the committed ``root_public_jwk`` is fully
deterministic and reproducible on any machine.

The compact serializations are NOT byte-reproducible, by design, for two
independent reasons that are inherent to the format:

1. RFC 9901 §4.1 requires each disclosure ``salt`` to be freshly random.
2. The signature alg is ES256 (ECDSA/P-256), which is randomized (a fresh
   nonce ``k`` per RFC 6279 — jwcrypto/cryptography do not use deterministic
   ECDSA).

So re-running this generator yields *semantically identical* vectors (same
keys, same claims, same wire shape, verifying to the same payloads) with
different salt/signature bytes. The committed JSON file is therefore the frozen
golden artifact; the consumer test verifies THOSE exact committed bytes against
the SDK rather than regenerating them. That is the correct model for a
randomized-signature credential format.

Run:  ``uv run python -m ap2.tests.delegate_sd_jwt_vectors.generate_vectors``
(writes ``delegate_sd_jwt_vectors.json`` next to this file). The consumer test
(``delegate_sd_jwt_vector_tests.py``) does NOT run this; it reads the frozen
JSON only.
"""

from __future__ import annotations

import json
import pathlib

from typing import Any

from ap2.sdk.disclosure_metadata import DisclosureMetadata
from ap2.sdk.generated.checkout_mandate import CheckoutMandate
from ap2.sdk.generated.open_checkout_mandate import (
    AllowedMerchants,
    OpenCheckoutMandate,
)
from ap2.sdk.generated.open_payment_mandate import OpenPaymentMandate
from ap2.sdk.generated.payment_mandate import PaymentMandate
from ap2.sdk.generated.types.amount import Amount
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.generated.types.payment_instrument import PaymentInstrument
from ap2.sdk.mandate import MandateClient
from ap2.sdk.sdjwt import kb_sd_jwt, parse_token, sd_jwt
from jwcrypto.jwk import JWK


# ── Version metadata (mirrors the keyed inventory in issue #303) ──────────

VERSION = {
    'vector_set': 'ap2-delegate-sd-jwt/v1',
    'delegate_sd_jwt_draft': 'draft-gco-oauth-delegate-sd-jwt-00',
    'ap2_reference_commit': 'e1ea56db72a6385bce3e5c1112b3a56ce60acb43',
    'frozen_standards': {
        'sd_jwt': 'RFC 9901',
        'jcs': 'RFC 8785',
        'jws': 'RFC 7515',
    },
}


# ── Pinned keys (generated once; embedded for deterministic verification) ─

PINNED_KEYS: dict[str, dict[str, str]] = {
    'user-root': {
        'crv': 'P-256',
        'd': 'OteyNUjAnN-JavrYb12_Wo_X4Mnuh6EX9m12PuNsFf0',
        'kty': 'EC',
        'x': 'toGTbmS_yILsQsNraZfhLjTy1yoGHd-NmHJ1FrV5OWs',
        'y': 'PiXfjVFtax7OIBhrFwgFV4esW8PAwQBnZhS_h-ZfwCk',
        'kid': 'user-root',
    },
    'agent-sa': {
        'crv': 'P-256',
        'd': 'iZi7Sme-wIEM2LjSiPGBrYcISGHyylc9yE7ZRPBiCI8',
        'kty': 'EC',
        'x': 'bYSLLVmu229lugkS6vzsT7rVGMJLlGA7r5qaO41dZxo',
        'y': 'GTWguqlzoLwGyvfdqVXLakN3ZYQo63ICAxu0oYRyckU',
        'kid': 'agent-sa',
    },
    'provider-cp': {
        'crv': 'P-256',
        'd': 'ZSpgdC8OZ8kaEXcx9cYoUNEBK9zsJ1tglT6ZlTnruug',
        'kty': 'EC',
        'x': 'MGtE_mNvXCJB2ZuZKVkmgr2yMdX3FbTRIUVO4cYapXU',
        'y': 'iksDJe7QVCFs-01YfrRe2kduda8AQzvPvXtBTE4x27U',
        'kid': 'provider-cp',
    },
    'merchant-key': {
        'crv': 'P-256',
        'd': '7hIxjcsFCw9wlbamhiH6nF2np8P60P3IgSptnvRS3ec',
        'kty': 'EC',
        'x': 'kfremiWl_Rn5FZuyCJxDn18WhLcBdbPS-79QyN5dZ6s',
        'y': '2LG18c1C30Mx7orscJ8VjOSq9t5AX4Cu0BhtEyZEPnw',
        'kid': 'merchant-key',
    },
    'checkout-user': {
        'crv': 'P-256',
        'd': '-2SnOhB3fPW7_swxgpBqyH-RkRQYMbsAvkw7yKQzRho',
        'kty': 'EC',
        'x': 'WuFQr15dAj6o8N35JFh5L9_6BvilsmrPd6ugwrsJbds',
        'y': '2yJAKCmRNaQZQM5Xczh3CN66Oul6qVkRmrqS221AWu4',
        'kid': 'checkout-user',
    },
    'checkout-agent': {
        'crv': 'P-256',
        'd': 'sE_r97_araaDITX8wt1I_tk0Oa8j4kYTozBKy0Jd2qY',
        'kty': 'EC',
        'x': 'Vxo2xJC2JDhNRCP0QGyDWXfyzWxw3_kb2zJTRmuxkL0',
        'y': 'X0CYROGy3VZFa2ALfUjiX9u_MFSEn0Xd4vczHZQM_9E',
        'kid': 'checkout-agent',
    },
}

OUT_PATH = pathlib.Path(__file__).with_name('delegate_sd_jwt_vectors.json')


def _priv(kid: str) -> JWK:
    return JWK.from_json(json.dumps(PINNED_KEYS[kid]))


def _pub_dict(kid: str) -> dict[str, Any]:
    return json.loads(_priv(kid).export_public())


def _make_cnf(kid: str) -> dict[str, Any]:
    """Public-only ``cnf`` binding for the delegate that holds ``kid``."""
    return {'jwk': _pub_dict(kid)}


# ── Wire-shape assertions (defensive; the consumer test re-checks these) ──


def _assert_single(token: str) -> None:
    assert '~~' not in token, 'single SD-JWT must carry no ~~ chain join'
    assert token.endswith('~'), 'single SD-JWT must end with ~'


def _assert_chain(token: str, expected_joins: int) -> None:
    assert token.count('~~') == expected_joins, (
        f'chain must have {expected_joins} ~~ joins, got {token.count("~~")}'
    )
    assert token.endswith('~'), 'final hop of a chain must end with ~'


# ── Vector builders ──────────────────────────────────────────────────────


def build_root_single() -> dict[str, Any]:
    """A single, un-delegated root SD-JWT (open payment mandate)."""
    open_payload = OpenPaymentMandate(
        constraints=[],
        cnf=_make_cnf('agent-sa'),
        payment_amount=Amount(amount=2500, currency='USD'),
        payee=Merchant(id='m-1', name='Acme Store'),
    )
    token = MandateClient().create(
        payloads=[open_payload],
        issuer_key=_priv('user-root'),
        sd=DisclosureMetadata(sd_keys=['payee', 'payment_amount']),
    )
    _assert_single(token)
    return {
        'id': 'root-single-sd-jwt',
        'description': (
            'A single issuer-signed root SD-JWT with no delegation hop. '
            'RFC 9901: ends with exactly one ~ and carries zero ~~ joins.'
        ),
        'root_public_jwk': _pub_dict('user-root'),
        'signer_kid': 'user-root',
        'holder_binding_kid': 'agent-sa',
        'verification': {'expected_aud': None, 'expected_nonce': None},
        'expected': {
            'hop_count': 1,
            'double_tilde_joins': 0,
            'ends_with_tilde': True,
            'payload_assertions': [
                {'path': [0, 'vct'], 'equals': 'mandate.payment.open.1'},
                {'path': [0, 'payment_amount', 'amount'], 'equals': 2500},
                {'path': [0, 'payee', 'name'], 'equals': 'Acme Store'},
            ],
        },
        'compact_serialization': token,
    }


def build_single_hop_payment() -> dict[str, Any]:
    """One delegation hop via the public ``MandateClient.present`` API."""
    client = MandateClient()
    open_payload = OpenPaymentMandate(
        constraints=[],
        cnf=_make_cnf('agent-sa'),
        payment_amount=Amount(amount=2500, currency='USD'),
        payee=Merchant(id='m-1', name='Acme Store'),
    )
    open_tok = client.create(
        payloads=[open_payload],
        issuer_key=_priv('user-root'),
        sd=DisclosureMetadata(sd_keys=['payee', 'payment_amount']),
    )
    closed = PaymentMandate(
        transaction_id='tx_single_hop',
        payee=Merchant(id='m-1', name='Acme Store'),
        payment_amount=Amount(amount=2500, currency='USD'),
        payment_instrument=PaymentInstrument(id='pi-1', type='credit'),
    )
    aud, nonce = 'merchant', 'merchant-nonce-single'
    token = client.present(
        holder_key=_priv('agent-sa'),
        mandate_token=open_tok,
        payloads=[closed],
        claims_to_disclose={'payment_amount': True},
        aud=aud,
        nonce=nonce,
    )
    _assert_chain(token, expected_joins=1)
    return {
        'id': 'single-hop-payment-chain',
        'description': (
            'One delegation hop appended with MandateClient.present(): '
            'open payment mandate -> closed payment mandate. Exactly one ~~ '
            'join; the open hop discloses only payment_amount (payee redacted).'
        ),
        'root_public_jwk': _pub_dict('user-root'),
        'signer_kid': 'user-root',
        'holder_binding_kid': 'agent-sa',
        'verification': {'expected_aud': aud, 'expected_nonce': nonce},
        'expected': {
            'hop_count': 2,
            'double_tilde_joins': 1,
            'ends_with_tilde': True,
            'payload_assertions': [
                {'path': [0, 'vct'], 'equals': 'mandate.payment.open.1'},
                {'path': [0, 'payment_amount', 'amount'], 'equals': 2500},
                {'path': [0, 'payee'], 'absent': True},
                {'path': [1, 'transaction_id'], 'equals': 'tx_single_hop'},
            ],
        },
        'compact_serialization': token,
    }


def build_multi_hop_payment() -> dict[str, Any]:
    """Canonical Bank -> SA -> CP -> Merchant three-segment chain.

    Minted hop-by-hop with the SDK primitives (``sd_jwt.create`` for the root,
    ``kb_sd_jwt.create`` for each KB-SD-JWT delegation) and joined on the ``~~``
    wire exactly as the reference verifier expects. ``present()`` appends a
    single hop onto one preceding segment, so multi-hop chains are composed
    from the segment primitives — this mirrors the SDK's own
    ``test_three_step_bank_sa_cp_merchant_flow``.
    """
    bank_segment = sd_jwt.create(
        payload=OpenPaymentMandate(
            constraints=[],
            cnf=_make_cnf('agent-sa'),
            payment_amount=Amount(amount=2500, currency='USD'),
            payee=Merchant(id='m-1', name='Acme Store'),
        ),
        issuer_key=_priv('user-root'),
        sd=DisclosureMetadata(sd_keys=['payee', 'payment_amount']),
    ).sd_jwt_issuance
    _assert_single(bank_segment)

    sa_segment = kb_sd_jwt.create(
        prev_token=parse_token(bank_segment),
        holder_key=_priv('agent-sa'),
        payload=OpenPaymentMandate(
            constraints=[], cnf=_make_cnf('provider-cp')
        ),
        aud='cp-agent',
        nonce='cp-nonce-123',
    ).sd_jwt_issuance

    closed = PaymentMandate(
        transaction_id='tx_multi_hop',
        payee=Merchant(id='m-1', name='Acme Store'),
        payment_amount=Amount(amount=2500, currency='USD'),
        payment_instrument=PaymentInstrument(id='pi-1', type='credit'),
    )
    aud, nonce = 'merchant', 'merchant-nonce-456'
    cp_segment = kb_sd_jwt.create(
        prev_token=parse_token(sa_segment),
        holder_key=_priv('provider-cp'),
        payload=closed,
        aud=aud,
        nonce=nonce,
    ).sd_jwt_issuance

    sa_stripped = sa_segment[:-1] if sa_segment.endswith('~') else sa_segment
    token = f'{bank_segment[:-1]}~~{sa_stripped}~~{cp_segment}'
    _assert_chain(token, expected_joins=2)
    return {
        'id': 'multi-hop-payment-chain',
        'description': (
            'Canonical Bank -> Shopping Agent -> Credentials Provider -> '
            'Merchant delegation chain. Three segments joined on the ~~ wire '
            '(two joins), three resolved payloads. Each hop binds to the '
            'preceding hop via cnf + sd_hash; aud/nonce enforced on the final '
            'CP -> Merchant hop.'
        ),
        'root_public_jwk': _pub_dict('user-root'),
        'signer_kid': 'user-root',
        'delegation_kids': ['user-root', 'agent-sa', 'provider-cp'],
        'verification': {'expected_aud': aud, 'expected_nonce': nonce},
        'expected': {
            'hop_count': 3,
            'double_tilde_joins': 2,
            'ends_with_tilde': True,
            'payload_assertions': [
                {'path': [0, 'vct'], 'equals': 'mandate.payment.open.1'},
                {'path': [1, 'cnf'], 'present': True},
                {'path': [2, 'transaction_id'], 'equals': 'tx_multi_hop'},
                {'path': [2, 'payment_amount', 'amount'], 'equals': 2500},
            ],
        },
        'compact_serialization': token,
    }


def build_single_hop_checkout() -> dict[str, Any]:
    """One delegation hop for the checkout mandate family.

    open checkout mandate -> closed checkout mandate, exercising the second
    mandate type called out in issue #303.
    """
    client = MandateClient()
    open_payload = OpenCheckoutMandate(
        constraints=[
            AllowedMerchants(allowed=[Merchant(id='m-1', name='Acme Store')])
        ],
        cnf=_make_cnf('checkout-agent'),
    )
    open_tok = client.create(
        payloads=[open_payload],
        issuer_key=_priv('checkout-user'),
    )
    closed = CheckoutMandate(
        checkout_jwt='hdr.eyJpZCI6ImNoa190ZXN0In0.sig',
        checkout_hash='Zm9vYmFyX2NoZWNrb3V0X2hhc2hfcGxhY2Vob2xkZXI',
    )
    aud, nonce = 'merchant', 'merchant-nonce-checkout'
    token = client.present(
        holder_key=_priv('checkout-agent'),
        mandate_token=open_tok,
        payloads=[closed],
        aud=aud,
        nonce=nonce,
    )
    _assert_chain(token, expected_joins=1)
    return {
        'id': 'single-hop-checkout-chain',
        'description': (
            'One delegation hop for the checkout mandate family: open checkout '
            'mandate (constrained to an allowed merchant) -> closed checkout '
            'mandate. Exactly one ~~ join.'
        ),
        'root_public_jwk': _pub_dict('checkout-user'),
        'signer_kid': 'checkout-user',
        'holder_binding_kid': 'checkout-agent',
        'verification': {'expected_aud': aud, 'expected_nonce': nonce},
        'expected': {
            'hop_count': 2,
            'double_tilde_joins': 1,
            'ends_with_tilde': True,
            'payload_assertions': [
                {'path': [0, 'vct'], 'equals': 'mandate.checkout.open.1'},
                {'path': [1, 'vct'], 'equals': 'mandate.checkout.1'},
                {
                    'path': [1, 'checkout_hash'],
                    'equals': 'Zm9vYmFyX2NoZWNrb3V0X2hhc2hfcGxhY2Vob2xkZXI',
                },
            ],
        },
        'compact_serialization': token,
    }


def build_all() -> dict[str, Any]:
    """Assemble the full versioned vector set (metadata + keys + vectors)."""
    return {
        'version': VERSION,
        'keys': {
            'note': (
                'Pinned P-256 signing keys. Private "d" is included so the '
                'vectors are fully reproducible; verification only needs the '
                'public coordinates.'
            ),
            'pinned': PINNED_KEYS,
        },
        'reproducibility': {
            'deterministic': ['keys', 'claims', 'aud', 'nonce', 'wire_shape'],
            'nondeterministic': [
                'disclosure salts (RFC 9901 4.1 requires fresh randomness)',
                'ES256 signatures (randomized ECDSA k; not RFC 6979)',
            ],
            'model': (
                'The committed JSON is the frozen golden artifact. The '
                'consumer test verifies these exact bytes against the SDK; '
                'regeneration yields semantically identical, byte-different '
                'vectors.'
            ),
        },
        'vectors': [
            build_root_single(),
            build_single_hop_payment(),
            build_multi_hop_payment(),
            build_single_hop_checkout(),
        ],
    }


def main() -> None:
    """Regenerate the frozen vector JSON next to this module."""
    data = build_all()
    OUT_PATH.write_text(json.dumps(data, indent=2, sort_keys=False) + '\n')
    print(f'Wrote {len(data["vectors"])} vectors to {OUT_PATH}')
    for v in data['vectors']:
        tok = v['compact_serialization']
        print(
            f'  - {v["id"]}: joins={tok.count("~~")} '
            f'ends_tilde={tok.endswith("~")} len={len(tok)}'
        )


if __name__ == '__main__':
    main()
