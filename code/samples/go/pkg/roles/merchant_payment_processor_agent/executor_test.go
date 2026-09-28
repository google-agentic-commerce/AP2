package merchant_payment_processor_agent

import (
	"bytes"
	"log"
	"strings"
	"testing"

	"github.com/google-agentic-commerce/ap2/samples/go/pkg/ap2/types"
	"github.com/google-agentic-commerce/ap2/samples/go/pkg/common"
)

func TestInitiatePaymentDoesNotLogRiskData(t *testing.T) {
	const secret = "risk-secret-should-not-be-logged"
	var captured bytes.Buffer
	original := log.Writer()
	log.SetOutput(&captured)
	defer log.SetOutput(original)

	updater := common.NewTaskUpdater("test-context")
	err := InitiatePayment([]map[string]interface{}{
		{types.PaymentMandateDataKey: map[string]interface{}{
			"payment_mandate_contents": map[string]interface{}{"payment_mandate_id": "mandate-1"},
		}},
		{"risk_data": map[string]interface{}{"sensitive": secret}},
	}, updater)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(captured.String(), secret) {
		t.Fatal("risk data appeared in logs")
	}
	if !strings.Contains(captured.String(), "mandate-1") || !strings.Contains(captured.String(), "Risk data present: true") {
		t.Fatalf("diagnostic context missing from logs: %q", captured.String())
	}
	if updater.GetTask().Status.State != common.TaskStateCompleted {
		t.Fatal("payment task did not complete")
	}
}
