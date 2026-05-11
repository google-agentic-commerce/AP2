"""Merchant MCP Server — inventory, cart, checkout tools.

Exposes five MCP tools consumed by the ADK shopping agent over stdio:
  search_inventory, check_product, assemble_cart,
  create_checkout, complete_checkout.

Mandate verification uses the AP2 SDK (MandateClient / chain verifier)
instead of ad-hoc ECDSA + canonical-JSON checking.
Checkout JWTs are properly ES256-signed instead of using stubs.
"""

import hashlib
import json
import logging
import os
import re
import time
import uuid

from pathlib import Path
from typing import Any

import httpx

from ap2.sdk.checkout_mandate_chain import CheckoutMandateChain
from ap2.sdk.constraints import check_checkout_constraints
from ap2.sdk.generated.open_checkout_mandate import OpenCheckoutMandate
from ap2.sdk.generated.types.checkout import Checkout, Status
from ap2.sdk.generated.types.item import Item
from ap2.sdk.generated.types.line_item import LineItem
from ap2.sdk.generated.types.link import Link
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.generated.types.total import Total
from ap2.sdk.jwt_helper import create_jwt
from ap2.sdk.mandate import MandateClient
from ap2.sdk.receipt_wrapper import ReceiptClient
from ap2.sdk.sdjwt import compute_sd_hash, parse_token
from ap2.sdk.utils import (
    b64url_decode,
    compute_sha256_b64url,
)
from common.constants import (
    AGENT_PROVIDER_PUB_PATH,
    MERCHANT_KEY_PATH,
    MERCHANT_PAYMENT_PROCESSOR_INITIATE_PAYMENT_URL,
    MERCHANT_PUB_PATH,
    TEMP_DB,
)
from common.x402_constants import (
    DEFAULT_FACILITATOR_ADDRESS,
    DEFAULT_MERCHANT_ADDRESS,
)
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ec
from fastmcp import FastMCP
from fastmcp.server.middleware.logging import LoggingMiddleware
from jwcrypto.jwk import JWK
from pydantic import BaseModel, PositiveInt, ValidationError


mcp = FastMCP('Merchant MCP Server')

_SCRIPT_DIR = Path(__file__).resolve().parent
_LOG_DIR = Path(os.environ.get('LOGS_DIR', _SCRIPT_DIR.parent / '.logs'))
_LOG_FILE = _LOG_DIR / 'merchant-mcp.log'
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_logger = logging.getLogger('merchant-mcp')
_logger.setLevel(logging.DEBUG)
_handler = logging.FileHandler(_LOG_FILE, mode='w', encoding='utf-8')
_handler.setFormatter(
    logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
)
_logger.addHandler(_handler)

mcp.add_middleware(
    LoggingMiddleware(
        logger=_logger,
        include_payloads=True,
        include_payload_length=True,
        max_payload_length=8000,
    )
)

_MOCK_CATALOG: dict[str, dict[str, Any]] = {
    'item_001': {'name': 'Wireless Headphones', 'price': 120.00, 'stock': 5},
    'item_002': {'name': 'USB-C Cable', 'price': 15.00, 'stock': 20},
}

_INVENTORY_PATH = Path(
    os.environ.get(
        'MERCHANT_INVENTORY_PATH',
        str(TEMP_DB / 'merchant_inventory.json'),
    )
)

_MERCHANT_KEY_PATH = Path(
    os.environ.get(
        'MERCHANT_SIGNING_KEY_PATH',
        str(TEMP_DB / 'merchant_signing_key.pem'),
    )
)


def _load_inventory() -> dict[str, dict[str, Any]]:
    try:
        if _INVENTORY_PATH.exists():
            with open(_INVENTORY_PATH) as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        _logger.warning('inventory load failed: %s', e)
    return {}


def _save_inventory(inv: dict[str, dict[str, Any]]) -> None:
    try:
        _INVENTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_INVENTORY_PATH, 'w') as f:
            json.dump(inv, f, indent=2)
    except OSError as e:
        _logger.warning('inventory save failed: %s', e)


class MerchantCartItem(BaseModel):
    item_id: str
    qty: PositiveInt
    unit_price: int | None = None
    item_name: str | None = None


class MerchantCart(BaseModel):
    cart_id: str
    total: int
    line_items: list[MerchantCartItem]
    currency: str = 'USD'


_TEMP_INVENTORY: dict[str, dict[str, Any]] = _load_inventory()
_CART_STORE: dict[str, dict[str, Any]] = {}

_TOKEN_STORE_PATH = Path(
    os.environ.get(
        'AP2_TOKEN_STORE_PATH',
        str(TEMP_DB / 'ap2_token_store.json'),
    )
)

_TRIGGER_STATE_PATH = Path(
    os.environ.get(
        'MERCHANT_TRIGGER_STATE_PATH',
        str(TEMP_DB / 'merchant_trigger_state.json'),
    )
)


# ── Key loading ─────────────────────────────────────────────────────────


def _get_agent_provider_public_key() -> JWK | None:
    """Loads the Agent Provider's public JWK from a file."""
    from jwcrypto.jwk import JWK

    if not AGENT_PROVIDER_PUB_PATH.exists():
        return None
    try:
        return JWK.from_json(
            AGENT_PROVIDER_PUB_PATH.read_text(encoding='utf-8')
        )
    except (ValueError, json.JSONDecodeError, OSError) as e:
        _logger.warning('could not load agent-provider public key: %s', e)
        return None


def _get_merchant_signing_key(kid: str = 'merchant-key-1') -> JWK:
    """Load or generate the merchant's ES256 signing key as a JWK."""
    pem = os.environ.get('MERCHANT_SIGNING_KEY_PEM')
    if pem:
        return JWK.from_json(pem)
    if MERCHANT_KEY_PATH.exists():
        return JWK.from_json(MERCHANT_KEY_PATH.read_text(encoding='utf-8'))

    raw_key = ec.generate_private_key(ec.SECP256R1())
    key = JWK.from_pyca(raw_key)
    jwk_dict = json.loads(key.export())
    jwk_dict['kid'] = 'merchant-key-1'
    key = JWK.from_json(json.dumps(jwk_dict))
    MERCHANT_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MERCHANT_KEY_PATH.write_text(key.export(), encoding='utf-8')
    MERCHANT_PUB_PATH.write_text(key.export_public(), encoding='utf-8')
    return key


def _load_persisted_mandate(filename: str) -> str | None:
    """Read an SD-JWT written by the agent's mandate tools.

    Avoids depending on the LLM to relay long base64url strings without
    corruption (the root cause of the 'utf-8 codec can't decode' errors).

    Args:
      filename: The name of the file (without directory) containing the persisted
        mandate.

    Returns:
      The content of the file as a string, or None if the file does not exist
      or cannot be read.
    """
    path = TEMP_DB / filename
    try:
        if path.exists():
            return path.read_text(encoding='ascii').strip()
    except OSError as e:
        _logger.warning('Could not load persisted mandate %s: %s', filename, e)
    return None


# ── Store helpers ───────────────────────────────────────────────────────


def _load_token_store() -> dict[str, Any]:
    try:
        if _TOKEN_STORE_PATH.exists():
            with open(_TOKEN_STORE_PATH) as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        _logger.warning('token_store load failed: %s', e)
    return {}


def _save_token_store(store: dict[str, Any]) -> None:
    try:
        _TOKEN_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_TOKEN_STORE_PATH, 'w') as f:
            json.dump(store, f, indent=2)
    except OSError as e:
        _logger.warning('token_store save failed: %s', e)


def _load_trigger_state() -> dict[str, Any]:
    """Loads the trigger state from the file system.

    Returns:
      A dictionary containing the trigger state, or an empty dictionary if the
      file does not exist or loading fails.
    """
    try:
        if _TRIGGER_STATE_PATH.exists():
            with open(_TRIGGER_STATE_PATH) as f:
                state = json.load(f)
            _logger.debug(
                'trigger_state loaded from %s: %s', _TRIGGER_STATE_PATH, state
            )
            return state
        _logger.debug('trigger_state file not found: %s', _TRIGGER_STATE_PATH)
    except (json.JSONDecodeError, OSError) as e:
        _logger.warning('trigger_state load failed: %s', e)
    return {}


# ── Inventory helpers ───────────────────────────────────────────────────


def _get_item(item_id: str) -> dict[str, Any] | None:
    if item_id in _TEMP_INVENTORY:
        return _TEMP_INVENTORY[item_id].copy()
    return _MOCK_CATALOG.get(item_id)


def _trigger_price_and_stock(
    raw: Any,
) -> tuple[float | None, int | None]:
    """Parse trigger file entry: legacy float (price only) or dict with price/stock."""
    if raw is None:
        return None, None
    if isinstance(raw, (int, float)):
        return float(raw), None
    if isinstance(raw, dict):
        p = raw.get('price')
        s = raw.get('stock')
        price = float(p) if p is not None else None
        stock = int(s) if s is not None else None
        return price, stock
    return None, None


def _trigger_overrides_for(item_id: str) -> tuple[float | None, int | None]:
    state = _load_trigger_state()
    return _trigger_price_and_stock(state.get(item_id))


def _get_effective_price(item_id: str, base_price: float) -> float:
    price_ov, _ = _trigger_overrides_for(item_id)
    if price_ov is not None:
        _logger.info(
            'trigger_state override: item_id=%s base=%.2f -> %.2f',
            item_id,
            base_price,
            price_ov,
        )
        return price_ov
    return base_price


def _generate_inventory_entry(
    description: str,
    constraint_price_cap: float | None = None,
) -> dict[str, Any]:
    """Generates a single inventory entry for a limited-drop product.

    The item is created with stock 0 — it becomes purchasable only when the
    trigger server sets a positive stock value. If a price cap is provided the
    generated price is a deterministic fraction below the cap; otherwise a
    hash-derived base price is used.

    Args:
      description: A natural-language description of the product (e.g.
        ``"supershoe limited edition gold sneaker womens 9"``).
      constraint_price_cap: An optional budget cap. When provided the generated
        price will be strictly below this value.

    Returns:
      A dictionary with ``item_id``, ``name``, ``price``, and ``stock`` (always
      0).
    """
    desc = description.strip().lower()
    slug = re.sub(r'[^a-z0-9]+', '_', desc).strip('_') or 'item'
    h = int(hashlib.sha256(desc.encode()).hexdigest()[:8], 16)

    if constraint_price_cap is not None and constraint_price_cap > 0:
        jitter = 0.48 + (0.10 + (h % 30) / 100) * 0.28
        price = round(constraint_price_cap * jitter, 2)
    else:
        price = round(5.0 + (h % 95) / 10, 2)

    return {
        'item_id': f'{slug}_0',
        'name': desc.title(),
        'price': price,
        'stock': 0,
    }


def _resolve_item(
    item_id: str,
    constraint_price_cap: float | None = None,
) -> dict[str, Any] | None:
    """Looks up an item by ID, generating it on the fly if necessary.

    First checks the in-memory inventory and mock catalog. If the item is not
    found, attempts to load or generate it via ``_ensure_item_in_inventory``.

    Args:
      item_id: The item identifier (e.g.
        ``"supershoe_limited_edition_gold_sneaker_womens_9_0"``).
      constraint_price_cap: Forwarded to the generator when the item must be
        created for the first time.

    Returns:
      A dict with the item's ``name``, ``price``, and ``stock``, or ``None``
      if the ID cannot be resolved.
    """
    item = _get_item(item_id)
    if not item and _ensure_item_in_inventory(item_id, constraint_price_cap):
        item = _get_item(item_id)
    return item


def _ensure_item_in_inventory(
    item_id: str,
    constraint_price_cap: float | None = None,
) -> bool:
    """Ensures the given item_id is present in the in-memory inventory.

    If the item is not in ``_TEMP_INVENTORY``, it is loaded from the on-disk
    inventory file. If still not found, a new entry is generated from the
    slug encoded in the ``item_id`` and persisted to disk.

    Args:
      item_id: The item identifier to look up or create.
      constraint_price_cap: Forwarded to ``_generate_inventory_entry`` when a new
        entry must be created.

    Returns:
      True if the item is now available in the inventory (loaded or generated),
      False if the ``item_id`` format is invalid.
    """
    disk_inv = _load_inventory()
    if item_id in disk_inv:
        _TEMP_INVENTORY.update(disk_inv)
        return True
    m = re.fullmatch(r'([a-z0-9_]+)_(\d+)', item_id)
    if not m:
        return False
    slug = m.group(1)
    desc = slug.replace('_', ' ')
    entry = _generate_inventory_entry(desc, constraint_price_cap)
    _TEMP_INVENTORY[entry['item_id']] = {
        'name': entry['name'],
        'price': entry['price'],
        'stock': entry['stock'],
    }
    _save_inventory(_TEMP_INVENTORY)
    _logger.info('_ensure_item_in_inventory: generated %s', entry['item_id'])
    return True


_DEMO_MERCHANT: dict[str, str] = {
    'id': 'merchant_1',
    'name': 'Demo Merchant',
    'website': 'https://demo-merchant.example',
}


async def _initiate_payment_with_payment_processor(
    payment_token: str,
    checkout_jwt_hash: str,
    open_checkout_hash: str,
) -> dict[str, Any]:
    """Initiates a payment with the merchant payment processor."""
    _logger.info(
        'initiate_payment_with_payment_processor called: payment_token=%s...',
        payment_token,
    )

    headers = {
        'Content-Type': 'application/json',
    }

    payload = {
        'payment_token': payment_token,
        'checkout_jwt_hash': checkout_jwt_hash,
        'open_checkout_hash': open_checkout_hash,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            _logger.info(
                'Sending POST to %s with payload: %s',
                MERCHANT_PAYMENT_PROCESSOR_INITIATE_PAYMENT_URL,
                json.dumps(payload),
            )
            response = await client.post(
                MERCHANT_PAYMENT_PROCESSOR_INITIATE_PAYMENT_URL,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            _logger.info(
                'Response from merchant payment processor: %s', response.text
            )
            return response.json()

    except httpx.RequestError as exc:
        _logger.warning(
            'An error occurred while requesting %r: %s', exc.request.url, exc
        )
        return {'error': 'Failed to connect to the merchant payment processor'}
    except httpx.HTTPStatusError as exc:
        _logger.warning(
            'Error response %s while requesting %r: %s',
            exc.response.status_code,
            exc.request.url,
            exc.response.text,
        )
        return {
            'error': (
                'Merchant payment processor returned status'
                f' {exc.response.status_code}'
            ),
            'details': exc.response.text,
        }
    except json.JSONDecodeError as e:
        _logger.warning('Failed to decode JSON response: %s', e)
        return {'error': 'Invalid JSON response from payment processor'}


# ── MCP tools ───────────────────────────────────────────────────────────


@mcp.tool()
def search_inventory(
    product_description: str,
    constraint_price_cap: float | None = None,
) -> dict[str, Any]:
    """Search inventory by product description.

    Returns a single matching product. Stock is 0 until a drop is simulated
    via the trigger server.

    Args:
      product_description: A description of the product to search for.
      constraint_price_cap: An optional price cap to apply to generated items.
    """
    _logger.info(
        'search_inventory called: product_description=%r cap=%s',
        product_description,
        constraint_price_cap,
    )
    if not product_description or not product_description.strip():
        return {
            'error': 'invalid_description',
            'message': 'product_description must be non-empty',
        }
    entry = _generate_inventory_entry(product_description, constraint_price_cap)
    _TEMP_INVENTORY[entry['item_id']] = {
        'name': entry['name'],
        'price': entry['price'],
        'stock': entry['stock'],
    }
    _save_inventory(_TEMP_INVENTORY)
    _logger.info('search_inventory result: %s', entry)
    return {
        'matches': [entry],
        'message': (
            f'Found 1 matching product: {entry["item_id"]}.'
            ' Stock is 0 until a drop is simulated via the trigger server.'
        ),
    }


@mcp.tool()
def check_product(
    item_id: str,
    constraint_price_cap: float | None = None,
) -> dict[str, Any]:
    """Return the current price and availability for an item.

    If the SKU is not in memory it is created from ``item_id`` (pattern
    ``<slug>_0``). Stock starts at 0; ``available`` becomes true only when
    the trigger server sets positive stock for this item.

    Args:
      item_id: The item identifier to look up or create.
      constraint_price_cap: An optional price cap to apply to generated items.

    Args:
      item_id: The item identifier (e.g.
        ``"nike_limited_edition_nba_sneaker_womens_9_0"``).
      constraint_price_cap: Optional budget cap forwarded when the item must be
        generated for the first time.

    Returns:
      ``item_id``, ``price``, ``available``, ``timestamp``.
      Pass ``price`` and ``available`` to ``check_constraints_against_mandate``.
    """
    _logger.info(
        'check_product called: item_id=%r cap=%s', item_id, constraint_price_cap
    )
    item = _resolve_item(item_id, constraint_price_cap)
    if not item:
        _logger.warning('check_product: item_not_found for %r', item_id)
        return {'error': 'item_not_found'}
    price = _get_effective_price(item_id, item['price'])
    _, stock_from_trigger = _trigger_overrides_for(item_id)
    available = stock_from_trigger is not None and stock_from_trigger > 0
    merchant_address = (
        os.environ.get('MERCHANT_WALLET_ADDRESS') or DEFAULT_MERCHANT_ADDRESS
    )
    truncated_address = (
        f'{merchant_address[:6]}...{merchant_address[-4:]}'
        if merchant_address
        else 'Web3 Payment'
    )
    payment_method = os.environ.get('FLOW') or 'card'
    result = {
        'item_id': item_id,
        'price': price,
        'available': available,
        'timestamp': int(time.time()),
        'payment_method': payment_method,
        'payment_method_description': truncated_address,
    }
    _logger.info(
        'check_product result: price=%s, available=%s',
        price,
        available,
    )
    return result


@mcp.tool()
def assemble_cart(item_id: str, qty: int) -> dict[str, Any]:
    """Create a cart with the given item and quantity.

    Args:
      item_id: From ``check_constraints_against_mandate`` →
        ``line_items[0].acceptable_items[0].id``.
      qty: Number of units (usually 1).

    Returns:
      ``cart_id`` (pass to ``create_checkout``), ``line_items``, ``total``,
      ``currency``.
    """
    _logger.info('assemble_cart called: item_id=%r, qty=%s', item_id, qty)
    item = _resolve_item(item_id)
    if not item:
        _logger.warning('assemble_cart: item_not_found for %r', item_id)
        return {'error': 'item_not_found'}
    _, stock_from_trigger = _trigger_overrides_for(item_id)
    if not (stock_from_trigger is not None and stock_from_trigger > 0):
        return {
            'error': 'out_of_stock',
            'message': (
                'Item is not available to purchase yet (e.g. drop not live).'
            ),
        }
    price = _get_effective_price(item_id, item['price'])
    cart_id = str(uuid.uuid4())
    price_minor = int(round(price * 100))
    total_minor = price_minor * qty

    cart_item = MerchantCartItem(
        item_id=item_id,
        qty=qty,
        unit_price=price_minor,
        item_name=item.get('name', item_id),
    )
    cart_obj = MerchantCart(
        cart_id=cart_id,
        total=total_minor,
        line_items=[cart_item],
        currency='USD',
    )

    cart_dict = cart_obj.model_dump()

    _CART_STORE[cart_id] = cart_dict

    _logger.info(
        'assemble_cart result: cart_id=%s, total=%s', cart_id, total_minor
    )
    return cart_obj.model_dump()


@mcp.tool()
def create_checkout(
    cart_id: str, open_checkout_mandate_id: str
) -> dict[str, Any]:
    """Create a properly ES256-signed checkout JWT for the cart.

    Args:
      cart_id: From ``assemble_cart``.
      open_checkout_mandate_id: The open checkout mandate ID from session state.

    Returns:
      ``checkout_jwt`` and ``checkout_jwt_hash`` — pass both to
      ``create_checkout_closed_mandate``. ``checkout_jwt_hash`` is also the
      checkout transaction binding for ``issue_payment_credential``.
      Note: ``open_checkout_hash`` required for ``issue_payment_credential`` is
      the hash of the ``open_checkout_mandate`` provided to this tool.
    """
    _logger.info('create_checkout called: cart_id=%s', cart_id)
    if not cart_id:
        return {'error': 'missing_cart_id', 'message': 'cart_id is required'}
    cart = _CART_STORE.get(cart_id)
    if not cart:
        return {
            'error': 'cart_not_found',
            'message': f'No cart found for cart_id={cart_id}',
        }

    agent_provider_pub = _get_agent_provider_public_key()
    if not agent_provider_pub:
        return {
            'error': 'no_public_key',
            'message': 'Agent provider public key not found.',
        }

    open_checkout_mandate = None
    if open_checkout_mandate_id.startswith('open_chk_'):
        open_checkout_mandate = _load_persisted_mandate(
            f'{open_checkout_mandate_id}.sdjwt'
        )
    if not open_checkout_mandate:
        return {
            'error': 'mandate_not_found',
            'message': (
                f'Open checkout mandate {open_checkout_mandate_id} not found'
            ),
        }

    try:
        verified_checkout = MandateClient().verify(
            token=open_checkout_mandate,
            key_or_provider=agent_provider_pub,
            payload_type=OpenCheckoutMandate,
        )
        checkout_mandate = verified_checkout.mandate_payload
    except (ValueError, NotImplementedError) as e:
        _logger.warning('Failed to verify open checkout mandate: %s', e)
        return {
            'error': 'invalid_mandate',
            'message': f'Failed to verify open checkout mandate: {e}',
        }

    total = cart['total']
    subtotal = 0
    line_items = []
    for idx, li in enumerate(cart.get('line_items', [])):
        item_id = li.get('item_id')
        inv_item = _get_item(item_id) if item_id else None
        title = (
            (inv_item.get('name') if inv_item else None)
            or li.get('item_name', '')
            or (item_id or '')
        )
        qty = li.get('qty', 1)
        unit_price = li.get('unit_price', 0)
        line_subtotal = unit_price * qty
        subtotal += line_subtotal

        line_items.append(
            LineItem(
                id=f'li_{idx}',
                item=Item(id=item_id, title=title, price=unit_price),
                quantity=qty,
                totals=[
                    Total(type='subtotal', amount=line_subtotal),
                    Total(type='total', amount=line_subtotal),
                ],
            )
        )

    merchant = Merchant(
        id=_DEMO_MERCHANT['id'],
        name=_DEMO_MERCHANT['name'],
        website=_DEMO_MERCHANT['website'],
    )
    website = _DEMO_MERCHANT.get('website', 'example.com')

    checkout = Checkout(
        id=cart_id,
        merchant=merchant,
        line_items=line_items,
        status=Status.incomplete,
        currency='USD',
        totals=[
            Total(type='subtotal', amount=subtotal),
            Total(type='total', amount=total),
        ],
        links=[
            Link(type='privacy_policy', url=f'https://{website}/privacy'),
            Link(type='terms_of_service', url=f'https://{website}/tos'),
        ],
    )

    violations = check_checkout_constraints(checkout_mandate, checkout)
    if violations:
        _logger.warning('Checkout constraints violated: %s', violations)
        return {
            'error': 'constraint_violation',
            'message': f'Checkout constraints violated: {violations}',
        }

    checkout_payload = checkout.model_dump(mode='json', exclude_none=True)

    flow = os.environ.get('FLOW', 'x402')
    if flow == 'x402':
        checkout_payload['accepted_payment_methods'] = [
            {
                'type': 'x402',
                'address': os.environ.get(
                    'MERCHANT_WALLET_ADDRESS', DEFAULT_MERCHANT_ADDRESS
                ),
                'network': 'base-sepolia',
                'facilitator': os.environ.get(
                    'FACILITATOR_ADDRESS', DEFAULT_FACILITATOR_ADDRESS
                ),
            }
        ]
    mpp_key = _get_merchant_signing_key()
    jwk_dict = json.loads(mpp_key.export())
    kid = jwk_dict.get('kid')
    header = {'alg': 'ES256', 'typ': 'JWT'}
    if kid:
        header['kid'] = kid

    checkout_jwt = create_jwt(
        header=header, payload=checkout_payload, private_key=mpp_key
    )
    checkout_jwt_hash = compute_sha256_b64url(checkout_jwt)

    open_checkout_hash = compute_sd_hash(parse_token(open_checkout_mandate))
    result = {
        'checkout_jwt': checkout_jwt,
        'checkout_jwt_hash': checkout_jwt_hash,
        'open_checkout_hash': open_checkout_hash,
    }
    _logger.info(
        'create_checkout result: checkout_jwt=%s..., total=%s',
        checkout_jwt[:24],
        total,
    )
    return result


@mcp.tool()
async def complete_checkout(
    payment_token: str,
    checkout_mandate_id: str,
    checkout_nonce: str,
) -> dict[str, Any]:
    """Complete checkout: verify the checkout mandate SD-JWT chain.

    Then call the (stubbed) payment processor.

    The checkout_mandate_chain must be an SD-JWT signed by the agent.

    Args:
      payment_token: The token received from the payment provider. The bound
        payment_mandate_chain is looked up in the credentials-provider token
        store; no separate mandate id is needed here.
      checkout_mandate_id: The ID of the checkout mandate chain (e.g., 'chk_...').
      checkout_nonce: The nonce generated by the Shopping Agent when creating
        the checkout mandate presentation.

    Returns:
      status: Success or failure indicator
      order_id: Order ID if successful, None otherwise
      payment_receipt: Payment receipt if successful, None otherwise
    """
    _logger.info(
        'complete_checkout called: payment_token=%s...',
        payment_token[:12] if payment_token else 'None',
    )
    if not checkout_nonce:
        return {
            'error': 'missing_checkout_nonce',
            'message': 'checkout_nonce is required',
        }

    checkout_mandate = None
    if checkout_mandate_id:
        checkout_mandate = _load_persisted_mandate(
            f'{checkout_mandate_id}.sdjwt'
        )
    if not checkout_mandate:
        return {
            'error': 'mandate_not_found',
            'message': (
                f'Could not load checkout_mandate from {checkout_mandate_id}.sdjwt'
            ),
        }

    token_store = _load_token_store()
    token_data = token_store.get(payment_token)
    if not token_data:
        return {
            'error': 'token_not_found',
            'message': (
                'payment_token not found or not issued by credential provider'
            ),
        }
    if token_data.get('used'):
        return {
            'error': 'token_already_used',
            'message': 'payment_token has already been used',
        }
    if token_data.get('expires_at', 0) < int(time.time()):
        return {
            'error': 'token_expired',
            'message': 'payment_token has expired',
        }

    agent_provider_pub = _get_agent_provider_public_key()
    if not agent_provider_pub:
        return {
            'error': 'agent_provider_key_missing',
            'message': (
                'Agent-provider public key not found — cannot verify mandate chain'
            ),
        }

    try:
        payloads = MandateClient().verify(
            token=checkout_mandate,
            key_or_provider=lambda _token: agent_provider_pub,
            expected_aud='merchant',
            expected_nonce=checkout_nonce,
        )
        _logger.info('complete_checkout: Mandate verified successfully')
        chain = CheckoutMandateChain.parse(payloads)
        violations = chain.verify(
            checkout_jwt=chain.closed_mandate.checkout_jwt,
        )
    except (
        ValueError,
        json.JSONDecodeError,
        InvalidSignature,
        ValidationError,
    ) as exc:
        return {
            'error': 'verification_failed',
            'message': str(exc),
        }
    if violations:
        return {
            'error': 'verification_failed',
            'message': '; '.join(violations),
        }

    checkout_jwt = chain.closed_mandate.checkout_jwt
    if not checkout_jwt:
        return {
            'error': 'invalid_mandate',
            'message': 'checkout_mandate_chain must contain checkout_jwt',
        }

    try:
        parts = checkout_jwt.split('.')
        payload_b64 = parts[1] if len(parts) >= 2 else ''
        payload_json = b64url_decode(payload_b64).decode()
        payload = json.loads(payload_json)
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        return {
            'error': 'jwt_decode_failed',
            'message': f'could not decode checkout_jwt payload: {e}',
        }

    total_cents = int(payload.get('total', 0))
    cart_id = payload.get('cart_id', '')
    cart = _CART_STORE.get(cart_id)
    currency = cart.get('currency', 'USD') if cart else 'USD'

    token_data['used'] = True
    order_id = str(uuid.uuid4())
    token_data['order_id'] = order_id
    token_data['amount_charged'] = total_cents
    token_data['currency'] = currency
    # checkout_mandate is a dSD-JWT chain joined by '~~'.  parse_token only
    # handles a single SD-JWT, so extract the open-mandate segment (first hop)
    # before parsing.  The trailing '~' is stripped when the chain is assembled,
    # so restore it if missing.
    open_segment = checkout_mandate.split('~~')[0]
    if not open_segment.endswith('~'):
        open_segment += '~'
    open_checkout_hash = compute_sd_hash(parse_token(open_segment))
    _logger.info(
        'DEBUG: complete_checkout checkout_mandate=%s', checkout_mandate
    )
    _logger.info(
        'DEBUG: complete_checkout open_checkout_hash=%s', open_checkout_hash
    )
    token_data['open_checkout_hash'] = open_checkout_hash
    checkout_jwt_hash = compute_sha256_b64url(checkout_jwt)
    token_data['checkout_jwt_hash'] = checkout_jwt_hash
    token_store[payment_token] = token_data
    _save_token_store(token_store)

    flow = os.environ.get('FLOW', 'x402')
    if flow == 'x402':
        bundled_payload = token_data.get('bundled_payload')
        bundled_token = json.dumps(bundled_payload) if bundled_payload else None
        reference = compute_sha256_b64url(
            MandateClient().get_closed_mandate_jwt(checkout_mandate)
        )

        checkout_receipt_content = ReceiptClient().create_checkout_receipt(
            merchant=payload['merchant']['website'],
            reference=reference,
            order_id=order_id,
        )
        mpp_key = _get_merchant_signing_key()
        jwk_dict = json.loads(mpp_key.export())
        kid = jwk_dict.get('kid')
        header = {'alg': 'ES256', 'typ': 'JWT'}
        if kid:
            header['kid'] = kid

        checkout_receipt = create_jwt(
            header=header,
            payload=checkout_receipt_content.model_dump(),
            private_key=mpp_key,
        )
        result = {
            'status': 'success',
            'order_id': order_id,
            'checkout_receipt': checkout_receipt,
        }
        if bundled_token:
            result['payment_token'] = bundled_token

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                _logger.info('Calling x402 PSP settle_payment')
                psp_url = 'http://localhost:8084/settle-payment'
                response = await client.post(
                    psp_url,
                    json={
                        'payment_token': bundled_token,
                        'checkout_jwt_hash': checkout_jwt_hash,
                        'open_checkout_hash': open_checkout_hash,
                    },
                )
                response.raise_for_status()
                psp_result = response.json()
                _logger.info('Response from x402 PSP: %s', psp_result)
                result['payment_receipt'] = psp_result.get('receipt')
                result['tx_hash'] = psp_result.get('tx_hash')
        except Exception as e:
            _logger.warning('Failed to call x402 PSP: %s', e)
            return {'error': 'PSP_call_failed', 'message': str(e)}

        _logger.info(
            'complete_checkout (x402) result: order_id=%s, total_cents=%s',
            order_id,
            total_cents,
        )
        return result

    # Card flow: call the legacy payment processor HTTP endpoint.
    _logger.info(
        'complete_checkout: Calling initiate_payment_with_payment_processor'
    )
    result = await _initiate_payment_with_payment_processor(
        payment_token,
        checkout_jwt_hash,
        open_checkout_hash,
    )
    _logger.info(
        'complete_checkout: initiate_payment_with_payment_processor returned'
    )
    if 'error' in result:
        error_msg = result.get('message') or result.get('details') or ''
        raise ValueError(
            f'Payment initiation failed: {result["error"]}. Details: {error_msg}'
        )

    reference = compute_sha256_b64url(
        MandateClient().get_closed_mandate_jwt(checkout_mandate)
    )

    checkout_receipt_content = ReceiptClient().create_checkout_receipt(
        merchant=payload['merchant']['website'],
        reference=reference,
        order_id=order_id,
    )
    checkout_receipt = create_jwt(
        header={'alg': 'ES256', 'typ': 'JWT', 'kid': 'merchant-key-1'},
        payload=checkout_receipt_content.model_dump(),
        private_key=_get_merchant_signing_key(),
    )

    result = {
        'status': 'success',
        'order_id': order_id,
        'checkout_receipt': checkout_receipt,
    }
    _logger.info(
        'complete_checkout result: order_id=%s, amount_charged=%s',
        order_id,
        total_cents,
    )
    return result


if __name__ == '__main__':
    mcp.run()
