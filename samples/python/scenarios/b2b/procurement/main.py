# main.py
import json
import uuid
import secrets
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# AP2 types
from ap2.types.mandate import (
    IntentMandate,
    CartContents,
    CartMandate,
    PaymentMandate,
    PaymentMandateContents,
)
from ap2.types.payment_request import (
    PaymentCurrencyAmount,
    PaymentItem,
    PaymentDetailsInit,
    PaymentMethodData,
    PaymentRequest,
    PaymentResponse,
)

# --- Paths / data dirs ---
SCENARIO_DIR = Path(__file__).parent
CATALOG_PATH = SCENARIO_DIR / "catalog.json"
MANDATES_DIR = SCENARIO_DIR / "mandates"
STATIC_DIR = SCENARIO_DIR / "static"

MANDATES_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# load catalog
if not CATALOG_PATH.exists():
    raise FileNotFoundError(f"Catalog not found at {CATALOG_PATH}")
with open(CATALOG_PATH, "r", encoding="utf-8") as f:
    CATALOG = json.load(f)

app = FastAPI(title="B2B Procurement Agent (AP2) - Demo")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# --- Helper functions ---
def save_mandate(prefix: str, mand_dict: dict, id_str: str) -> str:
    fname = f"{prefix}_{id_str}.json"
    path = MANDATES_DIR / fname
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(mand_dict, fh, indent=2)
    print(f"[MANDATE] saved {prefix} -> {path}")
    return str(path)


# --- Request models ---
class IntentIn(BaseModel):
    user: str
    query: str
    require_confirmation: bool = True


class CartIn(BaseModel):
    intent_id: str
    item_id: str


class PaymentRequestIn(BaseModel):
    cart_id: str
    method: str = "card"
    card_number: Optional[str] = None
    card_holder: Optional[str] = None
    expiry: Optional[str] = None
    cvv: Optional[str] = None


class PaymentConfirmIn(BaseModel):
    otp_token: str
    otp: str


# Simple in-memory OTP store (demo-only)
OTP_STORE: Dict[str, Dict] = {}


# --- Endpoints ---


@app.post("/intent")
def create_intent(payload: IntentIn):
    """Create an AP2 IntentMandate and return candidate catalog items."""
    # parse "under 1200" or "under $1200"
    m = re.search(r"under\s*\$?(\d+)", payload.query.lower())
    budget = int(m.group(1)) if m else None
    category = "laptop" if "laptop" in payload.query.lower() else None

    candidates = [
        item for item in CATALOG
        if (not category or category in item.get("category", ""))
        and (not budget or item.get("price", 0) <= budget)
    ]
    if not candidates:
        candidates = CATALOG[:3]

    intent_id = str(uuid.uuid4())
    intent_mandate = IntentMandate(
        user_cart_confirmation_required=payload.require_confirmation,
        natural_language_description=payload.query,
        merchants=None,
        skus=None,
        requires_refundability=False,
        intent_expiry=(datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
    )
    mandate_dict= intent_mandate.model_dump()
    save_mandate("intent", mandate_dict, intent_id)
    return {"intent_id": intent_id, "mandate": mandate_dict, "candidates": candidates}


@app.post("/cart")
def create_cart(body: CartIn):
    """Create an AP2 CartMandate for the selected item."""
    item = next((i for i in CATALOG if i["id"] == body.item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    amount = PaymentCurrencyAmount(currency="USD", value=item["price"])
    payment_item = PaymentItem(label=item["title"], amount=amount)
    payment_details = PaymentDetailsInit(
        id=str(uuid.uuid4()), display_items=[payment_item], total=payment_item
    )
    payment_request = PaymentRequest(
        method_data=[PaymentMethodData(supported_methods="mock_invoice")],
        details=payment_details,
    )

    contents = CartContents(
        id=str(uuid.uuid4()),
        user_cart_confirmation_required=True,
        payment_request=payment_request,
        cart_expiry=(datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        merchant_name=item["vendor"],
    )

    cart_mandate = CartMandate(contents=contents)
    mand_dict = cart_mandate.model_dump()
    save_mandate("cart", mand_dict, contents.id)
    return {"cart_id": contents.id, "mandate": mand_dict}


@app.post("/payment")
def initiate_payment(body: PaymentRequestIn):
    """Initiate payment - returns otp_token (demo-only)."""
    cart_path = MANDATES_DIR / f"cart_{body.cart_id}.json"
    if not cart_path.exists():
        raise HTTPException(status_code=404, detail="Cart mandate not found (save cart first)")

    otp_token = secrets.token_urlsafe(12)
    OTP_STORE[otp_token] = {"cart_id": body.cart_id, "method": body.method}
    return {
        "otp_required": True,
        "otp_token": otp_token,
        "notice": "Demo OTP is 123 — enter 123 to confirm (demo only).",
    }


@app.post("/payment/confirm")
def confirm_payment(body: PaymentConfirmIn):
    """Confirm OTP and create PaymentMandate (demo)."""
    entry = OTP_STORE.get(body.otp_token)
    if not entry:
        raise HTTPException(status_code=400, detail="Invalid or expired otp_token")

    if body.otp != "123":
        raise HTTPException(status_code=400, detail="Invalid OTP (demo expects 123)")

    cart_id = entry["cart_id"]
    cart_path = MANDATES_DIR / f"cart_{cart_id}.json"
    if not cart_path.exists():
        raise HTTPException(status_code=404, detail="Cart mandate not found")

    cart_json = json.loads(cart_path.read_text(encoding="utf-8"))
    try:
        total_info = cart_json["contents"]["payment_request"]["details"]["total"]
        amount_val = float(total_info["amount"]["value"])
    except (KeyError, TypeError, ValueError) as e:
        raise HTTPException(
            status_code=500,
            detail=f"Malformed cart mandate file: {e}"
        )

    tx = {"transaction_id": str(uuid.uuid4()), "amount": amount_val, "status": "success", "method": entry["method"]}

    response = PaymentResponse(
        request_id=str(uuid.uuid4()),
        method_name=entry["method"],
        details={"transaction_id": tx["transaction_id"], "status": tx["status"]},
    )

    pmc = PaymentMandateContents(
        payment_mandate_id=str(uuid.uuid4()),
        payment_details_id=str(uuid.uuid4()),
        payment_details_total=PaymentItem(
            label="Total",
            amount=PaymentCurrencyAmount(currency="USD", value=amount_val),
        ),
        payment_response=response,
        merchant_agent=cart_json["contents"]["merchant_name"],
    )

    payment_mandate = PaymentMandate(payment_mandate_contents=pmc)
    mand_dict = payment_mandate.model_dump()
    saved = save_mandate("payment", mand_dict, pmc.payment_mandate_id)

    del OTP_STORE[body.otp_token]
    return {
        "status": "Payment approved and order placed (demo)",
        "transaction": tx,
        "payment": mand_dict,
        "saved_file": saved,
    }


@app.get("/")
def root():
    index_file = SCENARIO_DIR / "static" / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "B2B Procurement Agent API. Visit /docs for Swagger UI."}
