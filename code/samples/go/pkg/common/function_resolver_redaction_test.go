package common

import (
	"bytes"
	"log"
	"strings"
	"testing"
)

func TestFallbackToolSelectionDoesNotLogPrompt(t *testing.T) {
	const secret = "sensitive-payment-token-do-not-log"
	var captured bytes.Buffer
	old := log.Writer()
	log.SetOutput(&captured)
	defer log.SetOutput(old)

	resolver := &FunctionResolver{tools: []ToolInfo{{Name: "initiate_payment"}}}
	got := resolver.fallbackToolSelection("initiate_payment " + secret)
	if got != "initiate_payment" {
		t.Fatalf("unexpected tool: %s", got)
	}
	if strings.Contains(captured.String(), secret) {
		t.Fatal("prompt leaked to log")
	}
	if !strings.Contains(captured.String(), "fallback tool selection") {
		t.Fatal("missing diagnostic context")
	}
}
