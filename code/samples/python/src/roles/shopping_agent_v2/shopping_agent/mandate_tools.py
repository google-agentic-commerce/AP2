"""Mandate tools: assemble & sign open mandates, create closed mandates.

Open mandates are SD-JWTs signed by the user key.
Closed mandates are SD-JWTs signed by the agent key.
Signing is embedded in the SD-JWT — no separate sign step needed.

ADK ToolContext: tools accept an optional ``tool_context`` parameter
(auto-injected by ADK) to read/write session state programmatically.
"""

import json
import logging
import os
import time
import uuid

from pathlib import Path
from typing import Any

from ap2.sdk.constraints import MandateContext, check_payment_constraints
from ap2.sdk.generated.checkout_mandate import CheckoutMandate
from ap2.sdk.generated.open_checkout_mandate import (
    AllowedMerchants,
    Item,
    LineItemRequirements,
    LineItems,
    OpenCheckoutMandate,
)
from ap2.sdk.generated.open_payment_mandate import (
    AllowedPayees,
    AllowedPaymentInstruments,
    AmountRange,
    OpenPaymentMandate,
    PaymentReference,
)
from ap2.sdk.generated.payment_mandate import PaymentMandate
from ap2.sdk.generated.types.amount import Amount
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.generated.types.payment_instrument import PaymentInstrument
from ap2.sdk.mandate import MandateClient
from ap2.sdk.receipt_wrapper import ReceiptClient
from ap2.sdk.sdjwt import compute_sd_hash, parse_token
from ap2.sdk.utils import compute_sha256_b64url
from common.constants import (
    AGENT_PROVIDER_KEY_PATH,
    AGENT_PROVIDER_PUB_PATH,
    DEFAULT_MANDATE_TTL_SECONDS,
    MERCHANT_PUB_PATH,
    TEMP_DB,
)
from common.x402_constants import (
    DEFAULT_FACILITATOR_ADDRESS,
    DEFAULT_MERCHANT_ADDRESS,
)
from cryptography.hazmat.primitives.asymmetric import ec
from google.adk.tools.tool_context import ToolContext
from jwcrypto.jwk import JWK
from pydantic import ValidationError


_logger = logging.getLogger('shopping_agent')

_SCRIPT_DIR = Path(__file__).resolve().parent
_AP2_ROOT = _SCRIPT_DIR.parent.parent
_AGENT_KEY_PATH = TEMP_DB / 'agent_signing_key.pem'
_AGENT_PUB_PATH = TEMP_DB / 'agent_signing_key.pub'

_DEFAULT_CURRENCY = 'USD'

DEMO_MERCHANT = Merchant(
    id='merchant_1',
    name='Demo Merchant',
    website='https://demo-merchant.example',
)

DEMO_PAYMENT_INSTRUMENT = PaymentInstrument(
    type='card',
    id='stub',
    description='Card •••4242',
)

_PAYMENT_METHOD = os.environ.get('FLOW', 'x402')

_merchant_address = (
    os.environ.get('MERCHANT_WALLET_ADDRESS') or DEFAULT_MERCHANT_ADDRESS
)
_truncated_address = (
    f'{_merchant_address[:6]}...{_merchant_address[-4:]}'
    if _merchant_address
    else 'Web3 Payment'
)

X402_PAYMENT_INSTRUMENT = PaymentInstrument(
    type='x402',
    id='x402-base-sepolia-usdc',
    description=_truncated_address,
    payee_address=_merchant_address,
    facilitator=os.environ.get(
        'FACILITATOR_ADDRESS', DEFAULT_FACILITATOR_ADDRESS
    ),
)


_PERSISTED_MANDATE_FILES = (
    'closed_checkout_mandate.sdjwt',
    'closed_payment_mandate.sdjwt',
)


def _clear_persisted_mandates() -> None:
    """Remove stale mandate files from a previous flow."""
    for filename in _PERSISTED_MANDATE_FILES:
        path = TEMP_DB / filename
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def _load_persisted_mandate(filename: str) -> str | None:
    """Read a persisted SD-JWT from the shared temp-db."""
    path = TEMP_DB / filename
    try:
        return path.read_text(encoding='ascii').strip()
    except FileNotFoundError:
        return None
    except OSError:
        _logger.exception('Could not load persisted mandate %s', filename)
        return None


def _resolve_mandate(mandate_or_id: str, expected_prefix: str) -> str:
    """Resolves a mandate ID to its content, or returns the content if not an ID."""
    if mandate_or_id.startswith(expected_prefix):
        loaded = _load_persisted_mandate(f'{mandate_or_id}.sdjwt')
        if not loaded:
            raise ValueError(f'Mandate {mandate_or_id} not found')
        return loaded
    return mandate_or_id


def _persist_mandate(filename: str, sd_jwt: str) -> None:
    """Write an SD-JWT to the shared temp-db so downstream MCP tools can read.

    the original bytes instead of relying on the LLM to relay long strings.

    Args:
        filename: The name of the file to write within the temp-db directory.
        sd_jwt: The SD-JWT string to persist.
    """
    try:
        TEMP_DB.mkdir(parents=True, exist_ok=True)
        (TEMP_DB / filename).write_text(sd_jwt, encoding='ascii')
    except OSError as e:
        _logger.warning('Failed to persist %s: %s', filename, e)


def _write_private_jwk(
    path: Path,
    key: JWK,
) -> None:
    """Write a private JWK to a file as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(key.export(), encoding='utf-8')


def _write_public_jwk(
    path: Path,
    key: JWK,
) -> None:
    """Write a public JWK to a file as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(key.export_public(), encoding='utf-8')


def _load_jwk_key(
    env_var: str,
    path: Path,
) -> JWK | None:
    """Loads a JWK from an environment variable or a file.

    The function first attempts to load the key from the environment variable
    specified by `env_var`. If the environment variable is not set, it tries
    to load the key from the file path specified by `path`.

    Args:
        env_var: The name of the environment variable containing the JSON JWK.
        path: The `Path` object to the file containing the JSON JWK.

    Returns:
        A `JWK` if a key is found and loaded, otherwise `None`.
    """
    json_str = os.environ.get(env_var)
    if json_str:
        return JWK.from_json(json_str)
    if path.exists():
        return JWK.from_json(path.read_text(encoding='utf-8'))
    return None


def _get_agent_provider_signing_key() -> JWK:
    """Load or generate the Agent Provider's signing key.

    This represents the user's root signing key provided by the agent platform
    (e.g., Google/Apple wallet or Gemini) used to sign the open mandate.

    Returns:
        The loaded or newly generated JWK.
    """
    key = _load_jwk_key(
        'AGENT_PROVIDER_SIGNING_KEY_PEM', AGENT_PROVIDER_KEY_PATH
    )
    if key is not None:
        if not AGENT_PROVIDER_PUB_PATH.exists():
            _write_public_jwk(AGENT_PROVIDER_PUB_PATH, key)
        return key
    raw_key = ec.generate_private_key(ec.SECP256R1())
    key = JWK.from_pyca(raw_key)
    jwk_dict = json.loads(key.export())
    jwk_dict['kid'] = 'agent-provider-key-1'
    key = JWK.from_json(json.dumps(jwk_dict))
    _write_private_jwk(AGENT_PROVIDER_KEY_PATH, key)
    _write_public_jwk(AGENT_PROVIDER_PUB_PATH, key)
    return key


def _get_agent_signing_key() -> JWK:
    """Load or generate the Agent's signing key.

    Used to sign closed mandates. The corresponding public key is embedded
    in the open mandate's ``cnf.jwk`` via the delegation chain.

    Returns:
        The loaded or newly generated JWK.
    """
    key = _load_jwk_key('AGENT_PRIVATE_KEY_PEM', _AGENT_KEY_PATH)
    if key is not None:
        if not _AGENT_PUB_PATH.exists():
            _write_public_jwk(_AGENT_PUB_PATH, key)
        return key
    raw_key = ec.generate_private_key(ec.SECP256R1())
    key = JWK.from_pyca(raw_key)
    _write_private_jwk(_AGENT_KEY_PATH, key)
    _write_public_jwk(_AGENT_PUB_PATH, key)
    return key


def _get_merchant_public_key() -> JWK | None:
    """Loads the merchant's public JWK from a file."""
    try:
        if MERCHANT_PUB_PATH.exists():
            return JWK.from_json(MERCHANT_PUB_PATH.read_text(encoding='utf-8'))
    except (ValueError, json.JSONDecodeError, OSError) as e:
        _logger.warning('could not load merchant public key: %s', e)
    return None


# ── Open-mandate assembly (SD-JWT, agent-provider-signed) ───────────────────


def _build_open_checkout_mandate(
    mandate_request: dict[str, Any],
    agent_pub_key: JWK,
    now: int,
    mandate_ttl_seconds: int,
) -> OpenCheckoutMandate:
    """Build an OpenCheckoutMandate Pydantic model from the request."""
    qty = mandate_request.get('qty', 1)
    item_name = mandate_request.get('item_name') or mandate_request.get(
        'item_id', ''
    )
    matches = mandate_request.get('matches') or []

    if matches:
        acceptable_items = [
            Item(id=m['item_id'], title=m.get('name', m['item_id']))
            for m in matches
        ]
    else:
        acceptable_items = [
            Item(id=mandate_request['item_id'], title=item_name),
        ]

    line_items = LineItems(
        items=[
            LineItemRequirements(
                id='line_1',
                acceptable_items=acceptable_items,
                quantity=qty,
            ),
        ],
    )
    allowed_merchants = AllowedMerchants(
        allowed=[DEMO_MERCHANT],
    )
    cnf = {'jwk': json.loads(agent_pub_key.export_public())}
    return OpenCheckoutMandate(
        constraints=[line_items, allowed_merchants],
        cnf=cnf,
        iat=now,
        exp=now + mandate_ttl_seconds,
    )


def _build_open_payment_mandate(
    mandate_request: dict[str, Any],
    agent_pub_key: JWK,
    checkout_reference: str,
    now: int,
    mandate_ttl_seconds: int,
) -> OpenPaymentMandate:
    """Build an OpenPaymentMandate Pydantic model from the request."""
    price_cap_cents = int(round(mandate_request['price_cap'] * 100))
    amount_range = AmountRange(
        currency=_DEFAULT_CURRENCY,
        min=0,
        max=price_cap_cents,
    )
    allowed_payee = AllowedPayees(
        allowed=[DEMO_MERCHANT],
    )
    payment_ref = PaymentReference(
        conditional_transaction_id=checkout_reference,
    )
    _logger.info('DEBUG: created payment_ref=%s', payment_ref)
    cnf = {'jwk': json.loads(agent_pub_key.export_public())}

    constraints = [amount_range, allowed_payee, payment_ref]
    if _PAYMENT_METHOD == 'x402':
        constraints.append(
            AllowedPaymentInstruments(
                allowed=[X402_PAYMENT_INSTRUMENT]
            )
        )

    return OpenPaymentMandate(
        constraints=constraints,
        cnf=cnf,
        iat=now,
        exp=now + mandate_ttl_seconds,
    )


_REQUIRED_MANDATE_FIELDS = ('item_id', 'price_cap')


def assemble_and_sign_mandates(
    mandate_request: dict[str, Any],
) -> dict[str, str]:
    """Assembles and signs open mandates (checkout and payment) as SD-JWTs.

    Both mandates are signed by the agent provider key. The agent's public key
    is embedded in the `cnf.jwk` claim for delegation binding.

    Args:
        mandate_request: A dictionary containing mandate details. Required fields:
          "item_id", "price_cap". Optional fields: "qty", "item_name", "matches".

    Returns:
        A dictionary containing:
          - "open_checkout_mandate": The serialized SD-JWT for checkout.
          - "open_payment_mandate": The serialized SD-JWT for payment.

    Raises:
        ValueError: If required fields are missing from `mandate_request`.
    """
    missing = [f for f in _REQUIRED_MANDATE_FIELDS if f not in mandate_request]
    if missing:
        raise ValueError(
            f'Missing required fields in mandate_request: {missing}'
        )

    _clear_persisted_mandates()
    agent_provider_key = _get_agent_provider_signing_key()
    agent_key = _get_agent_signing_key()
    agent_pub = JWK.from_json(agent_key.export_public())

    mandate_ttl_seconds = int(
        mandate_request.get('ttl_seconds', DEFAULT_MANDATE_TTL_SECONDS)
    )

    client = MandateClient()
    open_checkout_model = _build_open_checkout_mandate(
        mandate_request, agent_pub, int(time.time()), mandate_ttl_seconds
    )

    open_checkout_sdjwt = client.create(
        payloads=[open_checkout_model],
        issuer_key=agent_provider_key,
    )

    checkout_reference = compute_sd_hash(parse_token(open_checkout_sdjwt))
    _logger.info('DEBUG: open_checkout_sdjwt=%s', open_checkout_sdjwt)
    _logger.info('DEBUG: computed checkout_reference=%s', checkout_reference)

    open_payment_model = _build_open_payment_mandate(
        mandate_request,
        agent_pub,
        checkout_reference,
        int(time.time()),
        mandate_ttl_seconds,
    )
    open_payment_sdjwt = client.create(
        payloads=[open_payment_model],
        issuer_key=agent_provider_key,
    )

    open_checkout_id = 'open_chk_' + str(uuid.uuid4()).replace('-', '')
    _persist_mandate(f'{open_checkout_id}.sdjwt', open_checkout_sdjwt)

    open_payment_id = 'open_pay_' + str(uuid.uuid4()).replace('-', '')
    _persist_mandate(f'{open_payment_id}.sdjwt', open_payment_sdjwt)

    return {
        'open_checkout_mandate': open_checkout_id,
        'open_payment_mandate': open_payment_id,
        'open_checkout_hash': checkout_reference,
    }


def assemble_and_sign_mandates_tool(
    mandate_request: str,
    tool_context: ToolContext,
) -> dict[str, str]:
    """ADK tool to assemble and sign open mandates as SD-JWTs.

    This function parses the JSON request, generates the mandates, and persists
    them to the session state (`tool_context.state`). Constraints can be checked
    later using `check_constraints_against_mandate`.

    Args:
        mandate_request: A JSON string containing mandate details (item_id,
          price_cap, etc.).
        tool_context: The ADK ToolContext (automatically injected).

    Returns:
        A dictionary containing the "open_checkout_mandate" and
        "open_payment_mandate"
        SD-JWTs, or a dictionary with an "error" key if the operation fails.
    """
    truncated = (
        mandate_request[:200] + '...'
        if mandate_request and len(mandate_request) > 200
        else mandate_request
    )
    _logger.info(
        'assemble_and_sign_mandates_tool called: mandate_request=%s',
        truncated,
    )
    if not mandate_request or not mandate_request.strip():
        return {'error': 'mandate_request is required'}
    try:
        req = (
            json.loads(mandate_request)
            if isinstance(mandate_request, str)
            else mandate_request
        )
        mandates = assemble_and_sign_mandates(req)
        if 'error' not in mandates:
            _logger.info(
                'assemble_and_sign_mandates_tool result: open_checkout=%s...'
                ' open_payment=%s...',
                mandates['open_checkout_mandate'][:40],
                mandates['open_payment_mandate'][:40],
            )
            tool_context.state['app:open_checkout_mandate_id'] = mandates[
                'open_checkout_mandate'
            ]
            tool_context.state['app:open_payment_mandate_id'] = mandates[
                'open_payment_mandate'
            ]
        else:
            _logger.warning(
                'assemble_and_sign_mandates_tool error: %s',
                mandates.get('error'),
            )
        return mandates
    except json.JSONDecodeError as e:
        return {'error': f'Invalid mandate_request JSON: {e}'}
    except (ValueError, ValidationError, TypeError) as e:
        return {'error': str(e)}


# ── Constraint extraction & checking ────────────────────────────────────


def _extract_mandate_constraints(
    open_payment: str,
    open_checkout: str,
    pub_key: JWK,
) -> dict[str, Any]:
    """Verify and extract constraints from open mandate SD-JWTs.

    Args:
      open_payment: The open payment mandate SD-JWT string.
      open_checkout: The open checkout mandate SD-JWT string.
      pub_key: The public key used to verify the SD-JWTs.

    Returns:
      A dict with ``price_cap``, ``currency``, ``line_items``,
      ``allowed_merchants``, ``allowed_payees``, and the parsed
      ``open_payment_mandate`` model.
    """
    result: dict[str, Any] = {}

    open_payment = _resolve_mandate(open_payment, 'open_pay_')
    open_checkout = _resolve_mandate(open_checkout, 'open_chk_')
    verified_payment = MandateClient().verify(
        token=open_payment,
        key_or_provider=pub_key,
        payload_type=OpenPaymentMandate,
    )
    payment_mandate = verified_payment.mandate_payload
    result['_open_payment_mandate'] = payment_mandate
    for constraint in payment_mandate.constraints:
        if isinstance(constraint, AmountRange):
            result['price_cap'] = constraint.max / 100.0
            result['currency'] = constraint.currency
        elif isinstance(constraint, AllowedPayees):
            result['allowed_payees'] = [
                m.model_dump(exclude_none=True)
                for m in constraint.allowed
            ]
        elif isinstance(constraint, AllowedPaymentInstruments):
            desc = next(
                (
                    inst.description
                    for inst in constraint.allowed
                    if inst.description
                ),
                None,
            )
            if desc:
                result['payment_method_description'] = desc

    verified_checkout = MandateClient().verify(
        token=open_checkout,
        key_or_provider=pub_key,
        payload_type=OpenCheckoutMandate,
    )
    checkout_mandate = verified_checkout.mandate_payload
    for constraint in checkout_mandate.constraints:
        if isinstance(constraint, LineItems):
            items = []
            for req in constraint.items:
                items.append(
                    {
                        'acceptable_items': [
                            {'id': it.id, 'title': it.title}
                            for it in req.acceptable_items
                        ],
                        'quantity': req.quantity,
                    }
                )
            result['line_items'] = items
        elif isinstance(constraint, AllowedMerchants):
            result['allowed_merchants'] = [
                m.model_dump(exclude_none=True)
                for m in constraint.allowed
            ]

    return result


class FileBasedUsageProvider:
    """Provides mandate usage history from local JSON files."""

    def __init__(self, open_payment_hash: str):
        self.open_payment_hash = open_payment_hash

    def get_context(self) -> MandateContext:
        recurrence_file = TEMP_DB / f'recurrence_{self.open_payment_hash}.json'
        try:
            if recurrence_file.exists():
                with open(recurrence_file) as f:
                    data = json.load(f)
                    return MandateContext(**data)
        except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
            _logger.warning('Failed to read recurrence file: %s', e)
        return MandateContext(total_amount=0, total_uses=0, last_used_date=None)


def check_constraints_against_mandate(
    price: float,
    currency: str = 'USD',
    available: bool = True,
    tool_context: ToolContext = None,
) -> dict[str, Any]:
    """Checks whether a candidate product/price satisfies the open mandate constraints.

    Extracts constraints from the open mandates in the session state and verifies
    if the provided price and availability meet those constraints.

    Args:
        price: The price of the product to check. Pass 0 on the first call to just
          extract `line_items` without a real price check.
        currency: The ISO 4217 currency code (default `"USD"`).
        available: Whether the product is available for purchase.
        tool_context: The ADK ToolContext (automatically injected).

    Returns:
        A dictionary containing:
          - "meets_constraints": Boolean indicating if all constraints are met.
          - "violations": List of violated constraint descriptions.
          - "price": The checked price.
          - "available": The checked availability.
          - Other extracted constraints like "price_cap" and "line_items".
    """
    if not tool_context:
        return {'error': 'no_context', 'message': 'tool_context is required'}

    open_payment_id = tool_context.state.get('app:open_payment_mandate_id', '')
    open_checkout_id = tool_context.state.get(
        'app:open_checkout_mandate_id', ''
    )
    if not open_payment_id or not open_checkout_id:
        return {
            'error': 'no_mandates',
            'message': 'No open mandates in session.',
        }

    open_payment = _resolve_mandate(open_payment_id, 'open_pay_')
    open_checkout = _resolve_mandate(open_checkout_id, 'open_chk_')

    agent_provider_pub = JWK.from_json(
        _get_agent_provider_signing_key().export_public()
    )

    try:
        constraints = _extract_mandate_constraints(
            open_payment, open_checkout, agent_provider_pub
        )
    except (ValueError, NotImplementedError, ValidationError) as e:
        return {'error': 'mandate_parse_failed', 'message': str(e)}

    open_mandate = constraints.pop('_open_payment_mandate')

    if not available:
        return {
            'meets_constraints': False,
            'price': price,
            'violations': ['item_not_available'],
            'available': False,
            **constraints,
        }

    amount_cents = int(round(price * 100))
    instrument = (
        X402_PAYMENT_INSTRUMENT
        if _PAYMENT_METHOD == 'x402'
        else DEMO_PAYMENT_INSTRUMENT
    )
    candidate = PaymentMandate(
        transaction_id='pending',
        payee=DEMO_MERCHANT,
        payment_amount=Amount(amount=amount_cents, currency=currency),
        payment_instrument=instrument,
    )

    open_checkout_hash = compute_sd_hash(parse_token(open_checkout))
    _logger.info(
        'DEBUG: check_constraints: open_checkout_hash=%s', open_checkout_hash
    )
    open_payment_hash = compute_sd_hash(parse_token(open_payment))
    usage_provider = FileBasedUsageProvider(open_payment_hash)
    mandate_context = usage_provider.get_context()

    violations = check_payment_constraints(
        open_mandate,
        candidate,
        open_checkout_hash=open_checkout_hash,
        mandate_context=mandate_context,
    )
    _logger.info(
        'DEBUG: check_constraints result: meets_constraints=%s, violations=%s',
        len(violations) == 0,
        violations,
    )
    return {
        'meets_constraints': len(violations) == 0,
        'price': price,
        'violations': violations,
        'available': True,
        **constraints,
    }


# ── Closed-mandate creation (SD-JWT, agent-signed) ─────────────────────


def create_checkout_presentation(
    checkout_jwt: str,
    checkout_hash: str,
    nonce: str,
    aud: str = 'merchant',
    tool_context: ToolContext = None,
) -> dict[str, str]:
    """Creates a closed checkout mandate SD-JWT, signed by the agent's key.

    Binds the agent to a specific checkout session.

    Args:
        checkout_jwt: The JWT representing the checkout session (from
          `create_checkout`).
        checkout_hash: The hash of the checkout JWT.
        nonce: Nonce for Key Binding.
        aud: Optional audience for Key Binding. Defaults to "merchant".
        tool_context: The ADK ToolContext (automatically injected).

    Returns:
        A dictionary with key `"checkout_mandate"` containing the mandate chain ID
        (e.g., `"chk_..."`). Pass this ID to `complete_checkout`.
    """
    _logger.info('create_checkout_presentation called')
    try:
        payload = CheckoutMandate(
            checkout_jwt=checkout_jwt,
            checkout_hash=checkout_hash,
        )

        open_mandate_token = ''
        if tool_context:
            open_mandate_id = tool_context.state.get(
                'app:open_checkout_mandate_id',
                '',
            )
            if not open_mandate_id:
                raise ValueError('open_checkout_mandate_id is required')
            open_mandate_token = _resolve_mandate(open_mandate_id, 'open_chk_')

        agent_key = _get_agent_signing_key()
        full_chain = MandateClient().present(
            holder_key=agent_key,
            mandate_token=open_mandate_token or '',
            payloads=[payload],
            nonce=nonce,
            aud=aud,
        )

        mandate_id = 'chk_' + str(uuid.uuid4()).replace('-', '')
        closed_mandate_jwt = MandateClient().get_closed_mandate_jwt(full_chain)

        # Store chain with both the mandate ID and the hash of closed mandate as keys.
        _persist_mandate(f'{mandate_id}.sdjwt', full_chain)
        _persist_mandate(
            f'{compute_sha256_b64url(closed_mandate_jwt)}',
            full_chain,
        )

        if tool_context:
            tool_context.state['temp:checkout_mandate_chain'] = mandate_id
            tool_context.state['temp:checkout_nonce'] = nonce
        return {
            'checkout_mandate_chain_id': mandate_id,
            'checkout_nonce': nonce,
        }
    except (json.JSONDecodeError, ValidationError, ValueError) as e:
        return {'error': 'checkout_mandate_failed', 'message': str(e)}


def create_payment_presentation(
    checkout_hash: str,
    amount_cents: int,
    nonce: str,
    currency: str = 'USD',
    payee_json: str = '{}',
    aud: str = 'credential-provider',
    tool_context: ToolContext = None,
) -> dict[str, str]:
    """Creates a closed payment mandate SD-JWT, signed by the agent's key.

    This function binds the payment to a specific checkout and amount.

    Args:
        checkout_hash: The hash of the checkout JWT (from `create_checkout`). Used
          as the transaction ID to bind this payment to the checkout.
        amount_cents: The total amount in cents (e.g., 1000 for $10.00).
        nonce: Nonce for Key Binding.
        currency: ISO 4217 currency code (default `"USD"`).
        payee_json: A JSON string representing the payee (merchant) details.
          Defaults to the demo merchant if empty or invalid.
        aud: Optional audience for Key Binding. Defaults to "credential-provider"
          if None.
        tool_context: ADK ToolContext (automatically injected).

    Returns:
        A dictionary with key `"payment_mandate"` containing the mandate chain ID
        (e.g., `"pay_..."`). Pass this ID to `issue_payment_credential`.
    """
    _logger.info(
        'create_payment_presentation called: amount_cents=%s', amount_cents
    )
    try:
        payee_data = (
            json.loads(payee_json)
            if isinstance(payee_json, str)
            else payee_json
        )
        payee = (
            Merchant(**payee_data)
            if isinstance(payee_data, dict) and payee_data.get('id')
            else DEMO_MERCHANT
        )

        instrument = (
            X402_PAYMENT_INSTRUMENT
            if _PAYMENT_METHOD == 'x402'
            else DEMO_PAYMENT_INSTRUMENT
        )
        payload = PaymentMandate(
            transaction_id=checkout_hash,
            payee=payee,
            payment_amount=Amount(amount=amount_cents, currency=currency),
            payment_instrument=instrument,
        )

        if not tool_context:
            raise ValueError('tool_context is required')
        open_payment_mandate_id = tool_context.state.get(
            'app:open_payment_mandate_id',
            '',
        )
        if not open_payment_mandate_id:
            raise ValueError('open_payment_mandate_id is required')
        open_payment_mandate_token = _resolve_mandate(
            open_payment_mandate_id, 'open_pay_'
        )

        agent_key = _get_agent_signing_key()
        full_chain = MandateClient().present(
            holder_key=agent_key,
            mandate_token=open_payment_mandate_token,
            payloads=[payload],
            nonce=nonce,
            aud=aud,
        )

        mandate_id = 'pay_' + str(uuid.uuid4()).replace('-', '')
        closed_mandate_jwt = MandateClient().get_closed_mandate_jwt(full_chain)

        # Store chain with both the mandate ID and the hash of closed mandate as keys.
        _persist_mandate(f'{mandate_id}.sdjwt', full_chain)
        _persist_mandate(
            f'{compute_sha256_b64url(closed_mandate_jwt)}',
            full_chain,
        )

        if open_payment_mandate_token:
            open_payment_hash = compute_sd_hash(
                parse_token(open_payment_mandate_token)
            )
            recurrence_file = TEMP_DB / f'recurrence_{open_payment_hash}.json'
            try:
                if recurrence_file.exists():
                    with open(recurrence_file) as f:
                        data = json.load(f)
                        total_amount = data.get('total_amount', 0)
                        total_uses = data.get('total_uses', 0)
                else:
                    total_amount = 0
                    total_uses = 0

                total_amount += amount_cents
                total_uses += 1
                last_used_date = time.time()

                data = {
                    'total_amount': total_amount,
                    'total_uses': total_uses,
                    'last_used_date': last_used_date,
                }
                with open(recurrence_file, 'w') as f:
                    json.dump(data, f)
            except (OSError, ValueError) as e:
                _logger.warning('Failed to update recurrence context: %s', e)

        if tool_context:
            tool_context.state['temp:payment_mandate_chain'] = mandate_id
            tool_context.state['temp:payment_nonce'] = nonce
        return {
            'payment_mandate_chain_id': mandate_id,
            'payment_nonce': nonce,
            'payment_mandate_content': payload.model_dump(),
        }
    except (json.JSONDecodeError, ValidationError, ValueError) as e:
        return {'error': 'payment_mandate_failed', 'message': str(e)}


def verify_checkout_receipt(
    checkout_receipt: str,
) -> dict[str, Any]:
    """Verifies the checkout receipt returned by the merchant.

    Args:
        checkout_receipt: The checkout receipt JWT to verify.

    Returns:
        A dictionary with the verification result.
    """
    _logger.info(
        'verify_checkout_receipt called: checkout_receipt=%s', checkout_receipt
    )

    merchant_pub = _get_merchant_public_key()
    if not merchant_pub:
        return {'error': 'merchant_public_key_not_found'}

    result = ReceiptClient().verify_receipt(
        receipt_jwt=checkout_receipt,
        receipt_issuer_public_key=merchant_pub,
        has_reference_in_store_cb=lambda reference: (
            _load_persisted_mandate(reference) is not None
        ),
        is_payment_receipt=False,
    )

    _logger.info(
        'verify_checkout_receipt result: %s',
        result,
    )

    if 'error' in result:
        return result

    return {'verified': True}
