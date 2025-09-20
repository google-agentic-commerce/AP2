"""
This module contains tools for simulating peer-to-peer payments and financial requests.
These are mock implementations and do not perform real transactions.
"""
import json
from langchain_core.tools import tool
from pydantic.v1 import BaseModel, Field

# --- Input Schemas for Strong Typing ---

class PayToContactInput(BaseModel):
    contact_name: str = Field(description="The name or phone number of the contact to send money to.")
    amount: float = Field(description="The numerical amount of money to send.")
    currency: str = Field(description="The ISO currency code, e.g., 'USD', 'EUR', 'INR'.")
    reason: str = Field(description="A brief note or reason for the payment.")

class SplitBillInput(BaseModel):
    contact_names: list[str] = Field(description="A list of contact names to split the bill with.")
    total_amount: float = Field(description="The total amount of the bill to be split.")
    reason: str = Field(description="The description of the shared expense (e.g., 'Team Dinner').")

# --- Tool Definitions ---

@tool("pay_to_contact", args_schema=PayToContactInput)
def pay_to_contact(contact_name: str, amount: float, currency: str, reason: str) -> str:
    """
    Use this tool to send a specific amount of money to a single contact.
    It performs a direct peer-to-peer payment.
    """
    # MOCK IMPLEMENTATION
    print(f"--- SIMULATING API CALL to GPay: Sending {amount} {currency} to {contact_name} for '{reason}' ---")
    response = {"status": "success", "transaction_id": "TXN_MOCK_12345", "message": f"Successfully sent {amount} {currency} to {contact_name}."}
    return json.dumps(response)

@tool("split_bill", args_schema=SplitBillInput)
def split_bill(contact_names: list[str], total_amount: float, reason: str) -> str:
    """
    Use this tool to split a bill evenly among a list of contacts.
    It calculates the per-person amount and sends a payment request to each person. The user is included in the split.
    """
    # MOCK IMPLEMENTATION
    num_people = len(contact_names) + 1  # +1 for the user
    amount_per_person = round(total_amount / num_people, 2)
    print(f"--- SIMULATING API CALL to GPay: Splitting '{reason}' bill ({total_amount}) among {num_people} people ---")
    response = {"status": "success", "request_ids": [f"REQ_MOCK_{i}" for i in range(len(contact_names))], "message": f"Successfully sent payment requests of {amount_per_person} to {', '.join(contact_names)} for '{reason}'."}
    return json.dumps(response)
