// Copyright 2025 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package types

import "time"

const (
	CartMandateDataKey    = "ap2.mandates.CartMandate"
	IntentMandateDataKey  = "ap2.mandates.IntentMandate"
	PaymentMandateDataKey = "ap2.mandates.PaymentMandate"
)

type IntentMandate struct {
	UserCartConfirmationRequired *bool    `json:"user_cart_confirmation_required,omitempty"`
	NaturalLanguageDescription   string   `json:"natural_language_description"`
	Merchants                    []string `json:"merchants,omitempty"`
	SKUs                         []string `json:"skus,omitempty"`
	RequiresRefundability        *bool    `json:"requires_refundability,omitempty"`
	IntentExpiry                 string   `json:"intent_expiry"`
}

func NewIntentMandate() *IntentMandate {
	return &IntentMandate{
		UserCartConfirmationRequired: boolPtr(true),
		RequiresRefundability:        boolPtr(false),
	}
}

func (im *IntentMandate) GetUserCartConfirmationRequired() bool {
	if im.UserCartConfirmationRequired == nil {
		return true
	}
	return *im.UserCartConfirmationRequired
}

func (im *IntentMandate) GetRequiresRefundability() bool {
	if im.RequiresRefundability == nil {
		return false
	}
	return *im.RequiresRefundability
}

func boolPtr(b bool) *bool {
	return &b
}

type CartContents struct {
	ID                           string         `json:"id"`
	UserCartConfirmationRequired bool           `json:"user_cart_confirmation_required"`
	PaymentRequest               PaymentRequest `json:"payment_request"`
	CartExpiry                   string         `json:"cart_expiry"`
	MerchantName                 string         `json:"merchant_name"`
}

type CartMandate struct {
	Contents              CartContents `json:"contents"`
	MerchantAuthorization *string      `json:"merchant_authorization,omitempty"`
}

type PaymentMandateContents struct {
	PaymentMandateID    string          `json:"payment_mandate_id"`
	PaymentDetailsID    string          `json:"payment_details_id"`
	PaymentDetailsTotal PaymentItem     `json:"payment_details_total"`
	PaymentResponse     PaymentResponse `json:"payment_response"`
	MerchantAgent       string          `json:"merchant_agent"`
	Timestamp           string          `json:"timestamp,omitempty"`
}

func NewPaymentMandateContents() *PaymentMandateContents {
	return &PaymentMandateContents{
		Timestamp: time.Now().UTC().Format(time.RFC3339),
	}
}

type PaymentMandate struct {
	PaymentMandateContents PaymentMandateContents `json:"payment_mandate_contents"`
	UserAuthorization      *string                `json:"user_authorization,omitempty"`
}
