"""Prepare one buyer-signed closed Commerce Assurance presentation offline."""

import argparse
import base64
import getpass
import hashlib
import json
import os
import re
import secrets
import time

from pathlib import Path

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_keys.datatypes import PublicKey
from eth_utils import is_address
from jwcrypto import jwk, jws
import rfc8785


ORIGIN = 'https://exchange.weverpay.com'
AUDIENCE = ORIGIN + '/api/ap2-settlement'
RESOURCE = ORIGIN + '/api/wever-pay/assurance/x402'
PROFILE = 'com.weverlabs.ap2.commerce-assurance.1'
MERCHANT = 'https://weverlabs.com/ap2/merchant/commerce-assurance'
ISSUER = 'https://weverlabs.com/ap2/issuer/commerce-assurance'
SERVICE = 'wever.deterministic-commerce-assurance.v1'
ASSET = '0x833589fcd6edb6e08f4c7c32d4f71b54bda02913'
PAYEE = '0x138887d2947f996ada0cf96d4034467371621216'
NETWORK = 'eip155:8453'
AMOUNT = '25000'
DOMAIN = {'name': 'USD Coin', 'version': '2', 'chainId': 8453,
          'verifyingContract': ASSET}
TRANSFER = {'TransferWithAuthorization': [
    {'name': name, 'type': kind} for name, kind in (
        ('from', 'address'), ('to', 'address'), ('value', 'uint256'),
        ('validAfter', 'uint256'), ('validBefore', 'uint256'), ('nonce', 'bytes32'))
]}
EXCLUDED = {
    PAYEE, '0x6b9d16d821d08d69d8ce5998d6b9c5a1b12b4339',  # Exchange buyer
    '0xb9d730328073d1a0013371aa5bdc652cf30bea6d',  # Operator pilot
    '0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266',  # Public sample wallet
    '0x70997970c51812dc3a010c7d01b50e0d17dc79c8',  # Sample merchant
    '0x3c44cdddb6a900fa2b585dd299e03d12fa4293bc',  # Sample facilitator
}


def compact(value):
  return rfc8785.dumps(value).decode('utf-8')


def b64(data):
  return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def sha(text):
  return hashlib.sha256(text.encode('utf-8')).digest()


def require(condition, message):
  if not condition:
    raise ValueError(message)


def claims(token, typ, anchor):
  require(isinstance(token, str) and len(token) <= 16384
          and re.fullmatch(r'[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', token),
          'Expected compact signed JWT')
  signed = jws.JWS()
  signed.deserialize(token)
  require(signed.jose_header == {'typ': typ, 'kid': anchor['kid'], 'alg': 'ES256'},
          'Unexpected JOSE header')
  key = jwk.JWK(**anchor['jwk'])
  require(key.get('crv') == 'P-256' and not key.has_private, 'Expected public P-256 anchor')
  signed.verify(key, alg='ES256')
  payload = json.loads(signed.payload)
  head, content, _ = token.split('.')
  require(head == b64(compact(signed.jose_header).encode())
          and content == b64(compact(payload).encode()), 'Noncanonical JWT')
  return payload


def check_terms(challenge):
  require(challenge['x402Version'] == 2 and challenge['resource']['url'] == RESOURCE,
          'Unexpected x402 resource or version')
  offer, = challenge['accepts']
  require(offer['scheme'] == 'exact' and offer['network'] == NETWORK
          and offer['asset'].lower() == ASSET and offer['amount'] == AMOUNT
          and offer['payTo'].lower() == PAYEE, 'Unexpected purchase terms')
  require(offer['extra'] == {'name': 'USD Coin', 'version': '2',
                             'assetTransferMethod': 'eip3009'}
          and type(offer['maxTimeoutSeconds']) is int
          and 0 < offer['maxTimeoutSeconds'] <= 300, 'Unexpected signing domain or timeout')
  return offer


def check_window(quote, now):
  start, end = quote['iat'], quote['exp']
  require(type(start) is int and type(end) is int and start <= now < end
          and end - start <= 300, 'Closed checkout is outside its validity window')


def check_purchase(challenge, pair, trust, input_json, buyer, now):
  offer = check_terms(challenge)
  require(is_address(buyer) and buyer.lower() not in EXCLUDED, 'Expected buyer-owned wallet')
  buyer = buyer.lower()
  require(pair['profile'] == PROFILE, 'Unexpected settlement profile')
  checkout = claims(pair['checkout_mandate'], 'dc+sd-jwt', trust['issuer'])
  payment = claims(pair['payment_mandate'], 'dc+sd-jwt', trust['issuer'])
  closed, = checkout['delegate_payload']
  quote_jwt = closed['checkout_jwt']
  quote = claims(quote_jwt, 'wever-ap2-settlement-checkout+jwt', trust['merchant'])
  checkout_id, payment_id = quote['checkout_id'], quote['payment_identifier']
  require(re.fullmatch('[0-9a-f]{64}', checkout_id)
          and re.fullmatch('[A-Za-z0-9_-]{16,128}', payment_id), 'Invalid purchase identifier')
  check_window(quote, now)
  service_input = json.loads(input_json)
  require(isinstance(service_input, dict) and compact(service_input) == input_json,
          'Expected exact canonical service input bytes')
  require(quote == {'iss': MERCHANT, 'aud': AUDIENCE, 'profile': PROFILE,
                    'iat': quote['iat'], 'exp': quote['exp'], 'wallet': buyer,
                    'checkout_id': checkout_id, 'payment_identifier': payment_id,
                    'scope': SERVICE, 'resource': RESOURCE, 'network': NETWORK,
                    'asset': ASSET, 'amount_atomic': AMOUNT, 'pay_to': PAYEE,
                    'request_sha256': sha(input_json).hex()}, 'Checkout terms or input mismatch')
  require(set(checkout['cnf']) == {'jwk'}
          and set(checkout['cnf']['jwk']) == {'kty', 'crv', 'x', 'y'}, 'Expected holder public key')
  holder = jwk.JWK(**checkout['cnf']['jwk'])
  require(holder.get('crv') == 'secp256k1' and not holder.has_private, 'Invalid holder key')
  point = holder.get_op_key('verify').public_numbers()
  address = PublicKey(point.x.to_bytes(32, 'big') + point.y.to_bytes(32, 'big')).to_address()
  require(address.lower() == buyer, 'Holder differs from buyer')

  ref = b64(sha(quote_jwt))
  for kind, stamp, terms in (
      ('checkout', checkout, {'vct': 'mandate.checkout.1', 'checkout_jwt': quote_jwt,
                              'checkout_hash': ref}),
      ('payment', payment, {'vct': 'mandate.payment.1', 'transaction_id': ref,
                            'payee': {'id': PAYEE, 'name': 'Wever Pay'},
                            'payment_instrument': {'id': buyer, 'type': 'x402'},
                            'network': NETWORK, 'asset': ASSET, 'amount_atomic': AMOUNT,
                            'payment_identifier': payment_id})):
    require(stamp == {'iss': ISSUER, 'aud': AUDIENCE, 'profile': PROFILE, '_sd_alg': 'sha-256',
                      'iat': quote['iat'], 'exp': quote['exp'], 'cnf': checkout['cnf'],
                      'jti': sha(kind + '\n' + checkout_id).hex(), 'delegate_payload': [terms]},
            f'Closed {kind} mandate differs from checkout')
  return offer, quote


def sign_payment(account, challenge, offer, quote, now, expiry):
  """Sign the exact EIP-3009 transfer in native token units."""
  # USDC consumes (payer, nonce) once. Reopening this purchase reuses that nonce.
  identifier = quote['payment_identifier']
  nonce = '0x' + sha(RESOURCE + '\n' + quote['wallet'] + '\n' + identifier).hex()
  authorization = {
      'from': account.address, 'to': offer['payTo'], 'value': offer['amount'],
      'validAfter': str(now - 1), 'validBefore': str(expiry), 'nonce': nonce,
  }
  signature = account.sign_typed_data(DOMAIN, TRANSFER, authorization).signature
  return {
      'x402Version': 2, 'resource': challenge['resource'], 'accepted': offer,
      'payload': {'authorization': authorization, 'signature': '0x' + signature.hex()},
      'extensions': {'payment-identifier': {'info': {'id': identifier, 'required': True}}},
  }


def personal(account, message):
  return bytes(account.sign_message(encode_defunct(text=message)).signature)


def bind_holder(account, pair, quote, now, expiry):
  digest = sha(pair['checkout_mandate'] + '~' + pair['payment_mandate'] + '~').hex()
  wallet = quote['wallet']
  binding = {
      'version': 2, 'wallet': wallet, 'chain_id': 8453, 'aud': AUDIENCE,
      'iat': now, 'exp': expiry, 'mandate_sha256': digest, 'nonce': quote['checkout_id'],
  }
  message = (f"Wever AP2 holder binding v2\nAudience: {AUDIENCE}\nChallenge: {quote['checkout_id']}"
             f'\nMandate SHA-256: {digest}\nIssued at: {now}\nExpires at: {expiry}'
             f'\nChain ID: 8453\nWallet: {wallet}')
  return '.'.join(('wever-holder-binding-v2', b64(compact(binding).encode()),
                   b64(personal(account, message))))


def sign_purchase(account, challenge, pair, trust, input_json, now):
  """Produce the canonical request body and its wallet-bound proof header."""
  offer, quote = check_purchase(challenge, pair, trust, input_json, account.address, now)
  expiry = min(quote['exp'], now + offer['maxTimeoutSeconds'])
  body = compact({
      'checkout_mandate': pair['checkout_mandate'], 'input_json': input_json,
      'payment_mandate': pair['payment_mandate'] + '~' + bind_holder(account, pair, quote, now, expiry),
      'paymentPayload': sign_payment(account, challenge, offer, quote, now, expiry),
  })
  require(len(body.encode()) <= 49152, 'Presentation exceeds the profile limit')
  nonce = secrets.token_hex(16)
  message = (f'Wever Agent World free call v1\nOrigin: {ORIGIN}\nNetwork: {NETWORK}\nMethod: POST'
             f'\nPath: /api/ap2-settlement\nBody-SHA256: {sha(body).hex()}'
             f'\nTimestamp: {now}\nNonce: {nonce}')
  proof = {'wallet': quote['wallet'], 'timestamp': now, 'nonce': nonce,
           'signature': '0x' + personal(account, message).hex()}
  return body, base64.b64encode(compact(proof).encode()).decode('ascii')


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  for name in ('challenge', 'mandates', 'trust', 'input'):
    parser.add_argument('--' + name, type=Path, required=True)
  parser.add_argument('--buyer', required=True)
  parser.add_argument('--keystore', type=Path)
  parser.add_argument('--sign-to', type=Path, help='Create a private directory for the signed files')
  args = parser.parse_args()
  if bool(args.keystore) != bool(args.sign_to):
    parser.error('--keystore and --sign-to go together')
  challenge, pair, trust = (json.loads(p.read_bytes()) for p in
                            (args.challenge, args.mandates, args.trust))
  input_json = args.input.read_bytes().decode('utf-8')
  _, quote = check_purchase(challenge, pair, trust, input_json, args.buyer, int(time.time()))
  print(f"{SERVICE}\nBuyer {args.buyer}\nPayee {PAYEE}\nPrice 0.025 USDC (25000 atomic) on Base mainnet"
        f"\nPayment ID {quote['payment_identifier']}\nInput SHA-256 {quote['request_sha256']}")
  if not args.sign_to:
    return
  require(not args.sign_to.exists(), 'Choose a new output directory')
  require(input('Type SIGN to authorize this exact purchase: ') == 'SIGN', 'Signing cancelled')
  account = Account.from_key(Account.decrypt(args.keystore.read_text(encoding='utf-8'),
                                             getpass.getpass('Buyer keystore password: ')))
  require(account.address.lower() == args.buyer.lower(), 'Keystore differs from buyer')
  body, proof = sign_purchase(account, challenge, pair, trust, input_json, int(time.time()))
  args.sign_to.mkdir(mode=0o700)
  for name, value in [('body.json', body), ('proof.txt', proof)]:
    fd = os.open(args.sign_to / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as output:
      output.write(value.encode())
  print('Saved the signed request locally.')


if __name__ == '__main__':
  main()
