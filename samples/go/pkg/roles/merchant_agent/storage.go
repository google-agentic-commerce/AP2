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
	"strings"
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

	// Implement smarter product search logic
	var matchingProducts []Product
	queryLower := strings.ToLower(query)

	// Split query into words and filter out common words
	queryWords := strings.Fields(queryLower)
	var significantWords []string

	// Common words to ignore
	stopWords := map[string]bool{
		"a": true, "an": true, "the": true, "of": true, "for": true,
		"and": true, "or": true, "but": true, "in": true, "on": true,
		"at": true, "to": true, "with": true, "pair": true, "set": true,
		"some": true, "any": true,
	}

	for _, word := range queryWords {
		if !stopWords[word] && len(word) > 1 {
			significantWords = append(significantWords, word)
		}
	}

	// Score each product based on matches
	type scoredProduct struct {
		product Product
		score   int
	}

	var scoredProducts []scoredProduct

	for _, product := range s.products {
		nameLower := strings.ToLower(product.Name)
		descLower := strings.ToLower(product.Description)
		categoryLower := strings.ToLower(product.Category)
		score := 0

		// Check each significant word
		for _, word := range significantWords {
			// Higher score for name matches
			if strings.Contains(nameLower, word) {
				score += 3
			}
			// Medium score for description matches
			if strings.Contains(descLower, word) {
				score += 2
			}
			// Lower score for category matches
			if strings.Contains(categoryLower, word) {
				score += 1
			}
		}

		// Also check if the entire query matches (bonus points)
		if strings.Contains(nameLower, queryLower) {
			score += 5
		}

		if score > 0 {
			scoredProducts = append(scoredProducts, scoredProduct{
				product: product,
				score:   score,
			})
		}
	}

	// Sort by score (highest first) - simple bubble sort for small dataset
	for i := 0; i < len(scoredProducts); i++ {
		for j := i + 1; j < len(scoredProducts); j++ {
			if scoredProducts[j].score > scoredProducts[i].score {
				scoredProducts[i], scoredProducts[j] = scoredProducts[j], scoredProducts[i]
			}
		}
	}

	// Extract products from scored results
	for _, sp := range scoredProducts {
		matchingProducts = append(matchingProducts, sp.product)
	}

	if len(matchingProducts) == 0 {
		return []Product{}
	}

	return matchingProducts
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
