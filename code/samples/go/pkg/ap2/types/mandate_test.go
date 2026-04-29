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

import (
	"encoding/json"
	"testing"
)

func TestIntentMandateBudgetOptional(t *testing.T) {
	mandate := &IntentMandate{
		NaturalLanguageDescription: "Red basketball shoes",
		IntentExpiry:               "2026-12-31T00:00:00Z",
	}
	if mandate.Budget != nil {
		t.Errorf("expected Budget to be nil, got %+v", mandate.Budget)
	}
}

func TestIntentMandateBudgetCanBeSet(t *testing.T) {
	budget := &PaymentCurrencyAmount{Currency: "USD", Value: 150.00}
	mandate := &IntentMandate{
		NaturalLanguageDescription: "Red basketball shoes",
		IntentExpiry:               "2026-12-31T00:00:00Z",
		Budget:                     budget,
	}
	if mandate.Budget == nil {
		t.Fatal("expected Budget to be set")
	}
	if mandate.Budget.Currency != "USD" {
		t.Errorf("expected currency USD, got %s", mandate.Budget.Currency)
	}
	if mandate.Budget.Value != 150.00 {
		t.Errorf("expected value 150.00, got %f", mandate.Budget.Value)
	}
}

func TestIntentMandateBudgetSerializesToJSON(t *testing.T) {
	budget := &PaymentCurrencyAmount{Currency: "EUR", Value: 200.00}
	mandate := &IntentMandate{
		NaturalLanguageDescription: "Concert tickets",
		IntentExpiry:               "2026-06-01T00:00:00Z",
		Budget:                     budget,
	}
	data, err := json.Marshal(mandate)
	if err != nil {
		t.Fatalf("json.Marshal failed: %v", err)
	}

	var decoded map[string]interface{}
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("json.Unmarshal failed: %v", err)
	}

	budgetField, ok := decoded["budget"]
	if !ok {
		t.Fatal("expected 'budget' key in JSON output")
	}
	budgetMap, ok := budgetField.(map[string]interface{})
	if !ok {
		t.Fatalf("expected budget to be an object, got %T", budgetField)
	}
	if budgetMap["currency"] != "EUR" {
		t.Errorf("expected currency EUR, got %v", budgetMap["currency"])
	}
	if budgetMap["value"] != 200.00 {
		t.Errorf("expected value 200.00, got %v", budgetMap["value"])
	}
}

func TestIntentMandateBudgetAbsentOmittedFromJSON(t *testing.T) {
	mandate := &IntentMandate{
		NaturalLanguageDescription: "Groceries",
		IntentExpiry:               "2026-01-01T00:00:00Z",
	}
	data, err := json.Marshal(mandate)
	if err != nil {
		t.Fatalf("json.Marshal failed: %v", err)
	}

	var decoded map[string]interface{}
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("json.Unmarshal failed: %v", err)
	}

	if _, ok := decoded["budget"]; ok {
		t.Error("expected 'budget' key to be omitted from JSON when nil")
	}
}

func TestIntentMandateBudgetRoundTrip(t *testing.T) {
	budget := &PaymentCurrencyAmount{Currency: "GBP", Value: 75.50}
	original := &IntentMandate{
		NaturalLanguageDescription: "Books",
		IntentExpiry:               "2026-03-01T00:00:00Z",
		Budget:                     budget,
	}
	serialized, err := json.Marshal(original)
	if err != nil {
		t.Fatalf("json.Marshal failed: %v", err)
	}

	var restored IntentMandate
	if err := json.Unmarshal(serialized, &restored); err != nil {
		t.Fatalf("json.Unmarshal failed: %v", err)
	}

	if restored.Budget == nil {
		t.Fatal("expected restored Budget to be set")
	}
	if restored.Budget.Currency != "GBP" {
		t.Errorf("expected currency GBP, got %s", restored.Budget.Currency)
	}
	if restored.Budget.Value != 75.50 {
		t.Errorf("expected value 75.50, got %f", restored.Budget.Value)
	}
}
