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

package merchant_agent

import (
	"sync"
	"time"

	"github.com/google-agentic-commerce/ap2/samples/go/pkg/ap2/types"
	"github.com/google/uuid"
)

type Product struct {
	SKU         string  `json:"sku"`
	Name        string  `json:"name"`
	Description string  `json:"description"`
	Price       float64 `json:"price"`
	Category    string  `json:"category"`
}

type Storage struct {
	cartMandates map[string]*types.CartMandate
	riskData     map[string]map[string]interface{}
	products     []Product
	mutex        sync.RWMutex
}

var globalStorage = &Storage{
	cartMandates: make(map[string]*types.CartMandate),
	riskData:     make(map[string]map[string]interface{}),
	products: []Product{
		{
			SKU:         "SHOE-RB-001",
			Name:        "Red Basketball Shoes",
			Description: "High-top red basketball shoes, classic style",
			Price:       89.99,
			Category:    "Footwear",
		},
		{
			SKU:         "SHOE-RB-002",
			Name:        "Red Running Shoes",
			Description: "Lightweight red running shoes",
			Price:       69.99,
			Category:    "Footwear",
		},
		{
			SKU:         "SHIRT-B-001",
			Name:        "Blue T-Shirt",
			Description: "Cotton blue t-shirt",
			Price:       19.99,
			Category:    "Apparel",
		},
	},
}

func GetStorage() *Storage {
	return globalStorage
}

func (s *Storage) SearchProducts(query string) []Product {
	s.mutex.RLock()
	defer s.mutex.RUnlock()

	// TODO: Implement actual product search logic based on the query.
	// For this sample, we return all products.
	return s.products
}

func (s *Storage) CreateCartMandate(products []Product) *types.CartMandate {
	s.mutex.Lock()
	defer s.mutex.Unlock()

	cartID := uuid.New().String()

	var displayItems []types.PaymentItem
	var total float64

	for _, product := range products {
		item := types.PaymentItem{
			Label: product.Name,
			Amount: types.PaymentCurrencyAmount{
				Currency: "USD",
				Value:    product.Price,
			},
			RefundPeriod: 30,
		}
		displayItems = append(displayItems, item)
		total += product.Price
	}

	cartMandate := &types.CartMandate{
		Contents: types.CartContents{
			ID:                           cartID,
			UserCartConfirmationRequired: true,
			PaymentRequest: types.PaymentRequest{
				MethodData: []types.PaymentMethodData{
					{
						SupportedMethods: "CARD",
						Data:             make(map[string]interface{}),
					},
				},
				Details: types.PaymentDetailsInit{
					ID:           uuid.New().String(),
					DisplayItems: displayItems,
					Total: types.PaymentItem{
						Label: "Total",
						Amount: types.PaymentCurrencyAmount{
							Currency: "USD",
							Value:    total,
						},
						RefundPeriod: 30,
					},
				},
			},
			CartExpiry:   time.Now().Add(15 * time.Minute).Format(time.RFC3339),
			MerchantName: "Sample Merchant",
		},
	}

	s.cartMandates[cartID] = cartMandate
	return cartMandate
}

func (s *Storage) GetCartMandate(cartID string) *types.CartMandate {
	s.mutex.RLock()
	defer s.mutex.RUnlock()
	return s.cartMandates[cartID]
}

func (s *Storage) StoreRiskData(contextID string, riskData map[string]interface{}) {
	s.mutex.Lock()
	defer s.mutex.Unlock()
	s.riskData[contextID] = riskData
}

func (s *Storage) GetRiskData(contextID string) map[string]interface{} {
	s.mutex.RLock()
	defer s.mutex.RUnlock()
	return s.riskData[contextID]
}
