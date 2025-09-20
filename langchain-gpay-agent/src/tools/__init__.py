from .payment_tools import pay_to_contact, split_bill
from .wallet_tools import save_item_to_wallet

# This master list is used by the agent to know all available tools.
all_tools = [
    pay_to_contact,
    split_bill,
    save_item_to_wallet,
]
