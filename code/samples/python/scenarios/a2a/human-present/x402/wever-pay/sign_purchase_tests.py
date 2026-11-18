"""Exercise signing with an ephemeral buyer and a permanently expired checkout."""

import base64
import json
import sys
from copy import deepcopy
from unittest.mock import patch

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct, encode_typed_data
from eth_keys.datatypes import PrivateKey
from jwcrypto import jwk, jws

import sign_purchase as sample


NOW = 946684800


def jwt(payload, key, typ):
  signer = jws.JWS(sample.compact(payload).encode())
  signer.add_signature(key, protected=sample.compact({'alg': 'ES256', 'kid': key.kid, 'typ': typ}))
  return signer.serialize(compact=True)


@pytest.fixture
def issuer():
  return jwk.JWK.generate(kty='EC', crv='P-256', kid='issuer')


@pytest.fixture
def order(issuer):
  account = Account.create()
  buyer = account.address.lower()
  public = PrivateKey(account.key).public_key.to_bytes()
  holder = {'kty': 'EC', 'crv': 'secp256k1', 'x': sample.b64(public[:32]), 'y': sample.b64(public[32:])}
  merchant = jwk.JWK.generate(kty='EC', crv='P-256', kid='merchant')
  trust = {k.kid: {'kid': k.kid, 'jwk': json.loads(k.export_public())} for k in (issuer, merchant)}
  raw = '{"artifact":{"type":"local-synthetic"}}'
  q = {'iss': sample.MERCHANT, 'aud': sample.AUDIENCE, 'profile': sample.PROFILE,
       'iat': NOW - 10, 'exp': NOW + 120, 'checkout_id': '01' * 32, 'wallet': buyer,
       'request_sha256': sample.sha(raw).hex(), 'payment_identifier': 'ap2_fixture_0123456789',
       'scope': sample.SERVICE, 'resource': sample.RESOURCE, 'network': 'eip155:8453',
       'asset': sample.ASSET, 'amount_atomic': '25000', 'pay_to': sample.PAYEE}
  quote = jwt(q, merchant, 'wever-ap2-settlement-checkout+jwt')
  ref = sample.b64(sample.sha(quote))
  pair = {'profile': sample.PROFILE}
  for kind, content in [
      ('checkout', {'vct': 'mandate.checkout.1', 'checkout_jwt': quote, 'checkout_hash': ref}),
      ('payment', {'vct': 'mandate.payment.1', 'transaction_id': ref,
                   'payment_instrument': {'id': buyer, 'type': 'x402'},
                   'payee': {'id': sample.PAYEE, 'name': 'Wever Pay'}, 'payment_identifier': q['payment_identifier'],
                   'network': q['network'], 'asset': q['asset'], 'amount_atomic': q['amount_atomic']})]:
    mandate = {'iss': sample.ISSUER, 'aud': sample.AUDIENCE, 'profile': sample.PROFILE,
               '_sd_alg': 'sha-256', 'iat': q['iat'], 'exp': q['exp'],
               'cnf': {'jwk': holder}, 'jti': sample.sha(kind + '\n' + q['checkout_id']).hex(),
               'delegate_payload': [content]}
    pair[kind + '_mandate'] = jwt(mandate, issuer, 'dc+sd-jwt')
  challenge = {'x402Version': 2, 'resource': {'url': sample.RESOURCE}, 'accepts': [{
      'scheme': 'exact', 'network': 'eip155:8453', 'asset': sample.ASSET, 'amount': '25000',
      'payTo': sample.PAYEE, 'maxTimeoutSeconds': 300,
      'extra': {'name': 'USD Coin', 'version': '2', 'assetTransferMethod': 'eip3009'}}]}
  return account, challenge, pair, trust, raw


def test_transfer_signature_and_retry(order):
  account = order[0]
  body, _ = sample.sign_purchase(*order, NOW)
  payment = json.loads(body)['paymentPayload']
  auth = payment['payload']['authorization']
  assert auth['value'] == '25000'
  assert auth['validBefore'] == str(NOW + 120)
  assert auth['to'] == sample.PAYEE
  assert payment['extensions']['payment-identifier']['info']['id'] == 'ap2_fixture_0123456789'
  sig = payment['payload']['signature']
  def recover(domain, message):
    typed = encode_typed_data(domain, sample.TRANSFER, message)
    return Account.recover_message(typed, signature=sig)
  assert recover(sample.DOMAIN, auth) == account.address
  assert recover({**sample.DOMAIN, 'chainId': 84532}, auth) != account.address
  assert recover(sample.DOMAIN, {**auth, 'value': '20000'}) != account.address
  retry = json.loads(sample.sign_purchase(*order, NOW + 1)[0])
  assert retry['paymentPayload']['payload']['authorization']['nonce'] == auth['nonce']


@pytest.mark.parametrize(('field', 'value'), [
    ('amount', '20000'), ('amount', 25000), ('network', 'eip155:84532'), ('asset', sample.PAYEE),
    ('payTo', sample.ASSET), ('scheme', 'other'), ('maxTimeoutSeconds', 0),
    ('maxTimeoutSeconds', 301), ('extra', {'name': 'USDC', 'version': '2'})])
def test_refuse_altered_offer(order, field, value):
  order[1]['accepts'][0][field] = value
  with pytest.raises(ValueError):
    sample.sign_purchase(*order, NOW)


def test_reject_unbound_requests(order):
  buyer, challenge, pair, trust, raw = order
  def check(**changes):
    args = dict(challenge=challenge, pair=pair, trust=trust, input_json=raw, buyer=buyer.address, now=NOW)
    with pytest.raises((ValueError, jws.InvalidJWSSignature)):
      sample.check_purchase(**{**args, **changes})
  check(input_json=raw + ' ')
  check(now=NOW + 120)
  check(buyer=Account.create().address)
  for wallet in sample.EXCLUDED:
    check(buyer=wallet)
  check(pair={**pair, 'payment_mandate': pair['checkout_mandate']})
  other = deepcopy(trust)
  other['issuer']['jwk'] = trust['merchant']['jwk']
  check(trust=other)
  check(challenge={**challenge, 'resource': {'url': 'https://example.org/'}})


@pytest.mark.parametrize(('field', 'value'), [
    ('amount_atomic', '20000'), ('payee', {'id': sample.ASSET, 'name': 'Wever Pay'}),
    ('transaction_id', 'different-checkout')])
def test_signed_payment_must_match_checkout(order, issuer, field, value):
  pair = order[2]
  claim = sample.claims(pair['payment_mandate'], 'dc+sd-jwt', order[3]['issuer'])
  claim['delegate_payload'][0][field] = value
  pair['payment_mandate'] = jwt(claim, issuer, 'dc+sd-jwt')
  with pytest.raises(ValueError, match='payment mandate differs'):
    sample.sign_purchase(*order, NOW)


def test_wallet_binds_both_mandates_and_exact_http_bytes(order):
  buyer, _, pair, _, _ = order
  body, header = sample.sign_purchase(*order, NOW)
  proof = json.loads(base64.b64decode(header))
  expected_body_hash = sample.sha(body).hex()
  request = '\n'.join(['Wever Agent World free call v1', 'Origin: https://exchange.weverpay.com',
                       'Network: eip155:8453', 'Method: POST', 'Path: /api/ap2-settlement',
                       'Body-SHA256: ' + expected_body_hash, 'Timestamp: ' + str(NOW),
                       'Nonce: ' + proof['nonce']])
  assert Account.recover_message(encode_defunct(text=request), signature=proof['signature']) == buyer.address
  signed_payment, binding = json.loads(body)['payment_mandate'].split('~')
  assert signed_payment == pair['payment_mandate']
  method, payload, sig = binding.split('.')
  assert method == 'wever-holder-binding-v2'
  def decode(segment):
    return base64.urlsafe_b64decode(segment + '=' * (-len(segment) % 4))
  fields = json.loads(decode(payload))
  digest = sample.sha(pair['checkout_mandate'] + '~' + signed_payment + '~').hex()
  assert fields['mandate_sha256'] == digest
  message = '\n'.join(['Wever AP2 holder binding v2', 'Audience: ' + sample.AUDIENCE,
                       'Challenge: ' + fields['nonce'], 'Mandate SHA-256: ' + digest,
                       'Issued at: ' + str(NOW), 'Expires at: ' + str(NOW + 120),
                       'Chain ID: 8453', 'Wallet: ' + buyer.address.lower()])
  assert Account.recover_message(encode_defunct(text=message), signature=decode(sig)) == buyer.address


def test_cli_preview_and_sign(order, tmp_path, monkeypatch):
  buyer, challenge, pair, trust, raw = order
  argv = ['sign_purchase.py', '--buyer', buyer.address]
  for name, value in [('challenge', challenge), ('mandates', pair), ('trust', trust), ('input', raw)]:
    path = tmp_path / name
    path.write_bytes((value if name == 'input' else json.dumps(value)).encode())
    argv.extend(['--' + name, str(path)])
  monkeypatch.setattr(sys, 'argv', argv)
  monkeypatch.setattr(sample.time, 'time', lambda: NOW)
  with patch.object(Account, 'decrypt', side_effect=AssertionError):
    sample.main()
  keyfile, output = tmp_path / 'key.json', tmp_path / 'signed'
  keyfile.write_text(json.dumps(Account.encrypt(buyer.key, 'fixture-password', kdf='pbkdf2', iterations=1000)))
  argv.extend(['--keystore', str(keyfile), '--sign-to', str(output)])
  with patch('builtins.input', return_value='cancel'), pytest.raises(ValueError, match='cancelled'):
    sample.main()
  assert not output.exists()
  with patch('builtins.input', return_value='SIGN'), patch.object(sample.getpass, 'getpass', return_value='fixture-password'):
    sample.main()
  assert (output / 'proof.txt').stat().st_size > 0
  assert json.loads((output / 'body.json').read_bytes())['paymentPayload']['payload']['authorization']['from'] == buyer.address
  for path in (output, output / 'body.json', output / 'proof.txt'):
    assert path.stat().st_mode & 0o077 == 0
  with pytest.raises(ValueError, match='new output directory'):
    sample.main()
