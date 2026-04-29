"""Cart model for the browsing phase of AP2.

A Cart represents a merchant's product offer before mandate creation.
It contains display information for the user to browse and select from.
The checkout JWT is created only after the user selects a cart.
"""

from pydantic import BaseModel, Field


CART_DATA_KEY = 'ap2.cart'


class Cart(BaseModel):
    """A product offer from the merchant during the browsing phase."""

    cart_id: str = Field(..., description='Unique identifier for this cart.')
    item_label: str = Field(..., description='Human-readable product name.')
    amount: float = Field(..., description='Price in major currency units.')
    currency: str = Field(default='USD', description='ISO 4217 currency code.')
