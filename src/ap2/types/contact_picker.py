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

"""Objects from the W3C Contact Picker API.

The W3C Payment Request API utilizes several objects from this API.  By
extension, the Agent Payments Protocol utilizes these same objects.

There is no published python package for this API, so we define them here.

Specification:
https://www.w3.org/TR/contact-picker/
"""

from pydantic import BaseModel


CONTACT_ADDRESS_DATA_KEY = 'contact_picker.ContactAddress'


class ContactAddress(BaseModel):
    """The ContactAddress interface represents a physical address.

    Specification:
    https://www.w3.org/TR/contact-picker/#contact-address
    """

    city: str | None = None
    country: str | None = None
    dependent_locality: str | None = None
    organization: str | None = None
    phone_number: str | None = None
    postal_code: str | None = None
    recipient: str | None = None
    region: str | None = None
    sorting_code: str | None = None
    address_line: list[str] | None = None
