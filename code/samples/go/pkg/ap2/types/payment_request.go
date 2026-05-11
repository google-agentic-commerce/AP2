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

const PaymentMethodDataDataKey = "payment_request.PaymentMethodData"

type PaymentCurrencyAmount struct {
	Currency string  `json:"currency"`
	Value    float64 `json:"value"`
}

type PaymentItem struct {
	Label        string                `json:"label"`
	Amount       PaymentCurrencyAmount `json:"amount"`
	Pending      *bool                 `json:"pending,omitempty"`
	RefundPeriod int                   `json:"refund_period,omitempty"`
}

func NewPaymentItem() *PaymentItem {
	return &PaymentItem{
		RefundPeriod: 30,
	}
}

func (pi *PaymentItem) GetRefundPeriod() int {
	if pi.RefundPeriod == 0 {
		return 30
	}
	return pi.RefundPeriod
}

type PaymentShippingOption struct {
	ID       string                `json:"id"`
	Label    string                `json:"label"`
	Amount   PaymentCurrencyAmount `json:"amount"`
	Selected *bool                 `json:"selected,omitempty"`
}

func NewPaymentShippingOption() *PaymentShippingOption {
	return &PaymentShippingOption{
		Selected: boolPtr(false),
	}
}

func (pso *PaymentShippingOption) IsSelected() bool {
	if pso.Selected == nil {
		return false
	}
	return *pso.Selected
}

type PaymentOptions struct {
	RequestPayerName  *bool   `json:"request_payer_name,omitempty"`
	RequestPayerEmail *bool   `json:"request_payer_email,omitempty"`
	RequestPayerPhone *bool   `json:"request_payer_phone,omitempty"`
	RequestShipping   *bool   `json:"request_shipping,omitempty"`
	ShippingType      *string `json:"shipping_type,omitempty"`
}

func NewPaymentOptions() *PaymentOptions {
	return &PaymentOptions{
		RequestPayerName:  boolPtr(false),
		RequestPayerEmail: boolPtr(false),
		RequestPayerPhone: boolPtr(false),
		RequestShipping:   boolPtr(true),
	}
}

func (po *PaymentOptions) GetRequestPayerName() bool {
	if po.RequestPayerName == nil {
		return false
	}
	return *po.RequestPayerName
}

func (po *PaymentOptions) GetRequestPayerEmail() bool {
	if po.RequestPayerEmail == nil {
		return false
	}
	return *po.RequestPayerEmail
}

func (po *PaymentOptions) GetRequestPayerPhone() bool {
	if po.RequestPayerPhone == nil {
		return false
	}
	return *po.RequestPayerPhone
}

func (po *PaymentOptions) GetRequestShipping() bool {
	if po.RequestShipping == nil {
		return true
	}
	return *po.RequestShipping
}

type PaymentMethodData struct {
	SupportedMethods string                 `json:"supported_methods"`
	Data             map[string]interface{} `json:"data,omitempty"`
}

func NewPaymentMethodData(supportedMethods string) *PaymentMethodData {
	return &PaymentMethodData{
		SupportedMethods: supportedMethods,
		Data:             make(map[string]interface{}),
	}
}

func (pmd *PaymentMethodData) GetData() map[string]interface{} {
	if pmd.Data == nil {
		return make(map[string]interface{})
	}
	return pmd.Data
}

type PaymentDetailsModifier struct {
	SupportedMethods       string                 `json:"supported_methods"`
	Total                  *PaymentItem           `json:"total,omitempty"`
	AdditionalDisplayItems []PaymentItem          `json:"additional_display_items,omitempty"`
	Data                   map[string]interface{} `json:"data,omitempty"`
}

type PaymentDetailsInit struct {
	ID              string                   `json:"id"`
	DisplayItems    []PaymentItem            `json:"display_items"`
	ShippingOptions []PaymentShippingOption  `json:"shipping_options,omitempty"`
	Modifiers       []PaymentDetailsModifier `json:"modifiers,omitempty"`
	Total           PaymentItem              `json:"total"`
}

type PaymentRequest struct {
	MethodData      []PaymentMethodData `json:"method_data"`
	Details         PaymentDetailsInit  `json:"details"`
	Options         *PaymentOptions     `json:"options,omitempty"`
	ShippingAddress *ContactAddress     `json:"shipping_address,omitempty"`
}

type PaymentResponse struct {
	RequestID       string                 `json:"request_id"`
	MethodName      string                 `json:"method_name"`
	Details         map[string]interface{} `json:"details,omitempty"`
	ShippingAddress *ContactAddress        `json:"shipping_address,omitempty"`
	ShippingOption  *PaymentShippingOption `json:"shipping_option,omitempty"`
	PayerName       *string                `json:"payer_name,omitempty"`
	PayerEmail      *string                `json:"payer_email,omitempty"`
	PayerPhone      *string                `json:"payer_phone,omitempty"`
}
