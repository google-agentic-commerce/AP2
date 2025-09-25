# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Custom, structured IntentMandate for the flight booking demo."""

from ap2.types.mandate import IntentMandate
from pydantic import BaseModel, Field


class FlightConstraints(BaseModel):
    """Structured constraints for a flight booking."""
    destination: str = Field(..., description="The flight destination city.")
    max_price: int = Field(..., description="The maximum price for the flight.")
    currency: str = Field(
        "GBP", description="The 3-letter currency code (e.g., GBP)."
    )


class StructuredIntentMandate(IntentMandate):
    """An IntentMandate subclass that includes structured flight constraints."""
    constraints: FlightConstraints
