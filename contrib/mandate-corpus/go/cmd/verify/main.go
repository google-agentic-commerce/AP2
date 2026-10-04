// Command verifier validates signed AP2 mandate fixtures in Go.
//
// This is the piece that does not exist upstream. It verifies a delegation
// chain the same way the Python SDK does: the root SD-JWT with the issuer key,
// then each KB-SD-JWT with the key named in the previous hop's cnf claim.
//
// Usage:
//
//	go run ./cmd/verify            # verify every vector in vectors/
//	go test ./...
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/mrpkk/ap2-mandate-verifier/sdjwt"
)

// Fixture mirrors the JSON corpus files.
type Fixture struct {
	ID          string `json:"id"`
	Description string `json:"description"`
	Expected    string `json:"expected"`
	Issuance    struct {
		IssuerJWK map[string]any `json:"issuer_jwk"`
		AgentJWK  map[string]any `json:"agent_jwk"`
		Aud       string         `json:"aud"`
		Nonce     string         `json:"nonce"`
	} `json:"issuance"`
	RootSDJWT string         `json:"root_sd_jwt"`
	KBSDJWT   string         `json:"kb_sd_jwt"`
	Reference map[string]any `json:"plaintext_payload"`
}

type verdict struct {
	ok       bool
	stage    string
	detail   string
	payload  map[string]any
	chainLen int
}

func verify(f Fixture) verdict {
	// Hop 0: root SD-JWT, verified with the issuer key.
	root, err := sdjwt.Parse(f.RootSDJWT)
	if err != nil {
		return verdict{false, "parse-root", err.Error(), nil, 0}
	}
	issuerPub, err := sdjwt.PublicKeyFromJWK(f.Issuance.IssuerJWK)
	if err != nil {
		return verdict{false, "issuer-key", err.Error(), nil, 0}
	}
	if err := root.VerifyES256(issuerPub); err != nil {
		return verdict{false, "verify-root", err.Error(), nil, 0}
	}
	rootMandate, err := root.EffectiveMandate()
	if err != nil {
		return verdict{false, "root-disclosures", err.Error(), nil, 0}
	}

	// The root cnf must bind the agent key, otherwise the human signed an
	// authorisation nobody can exercise.
	cnf, ok := sdjwt.CNFJWK(rootMandate)
	if !ok {
		return verdict{false, "root-cnf", "root has no cnf.jwk: the mandate is unenforceable", nil, 1}
	}
	if !sameJWK(cnf, f.Issuance.AgentJWK) {
		return verdict{false, "root-cnf", "root cnf does not match the agent key", nil, 1}
	}

	// Hop 1: KB-SD-JWT, verified with the key named in the root's cnf.
	hop, err := sdjwt.Parse(f.KBSDJWT)
	if err != nil {
		return verdict{false, "parse-hop", err.Error(), rootMandate, 1}
	}
	agentPub, err := sdjwt.PublicKeyFromJWK(cnf)
	if err != nil {
		return verdict{false, "agent-key", err.Error(), rootMandate, 1}
	}
	if err := hop.VerifyES256(agentPub); err != nil {
		return verdict{false, "verify-hop", err.Error(), rootMandate, 1}
	}
	hopMandate, err := hop.EffectiveMandate()
	if err != nil {
		return verdict{false, "hop-disclosures", err.Error(), rootMandate, 1}
	}
	// The hop must bind to the root's sd_jwt string.
	wantHash, err := sdjwt.SDHash(root)
	if err != nil {
		return verdict{false, "sd-hash", err.Error(), rootMandate, 1}
	}
	if got, _ := hop.Payload["sd_hash"].(string); got != wantHash {
		return verdict{false, "sd-hash",
			fmt.Sprintf("hop sd_hash %q does not match root sd_hash %q", got, wantHash), rootMandate, 1}
	}

	// The decoded mandate must match the reference payload.
	gotAmt, _ := hopMandate["payment_amount"].(map[string]any)
	wantAmt, _ := f.Reference["payment_amount"].(map[string]any)
	if fmt.Sprint(gotAmt["amount"]) != fmt.Sprint(wantAmt["amount"]) ||
		fmt.Sprint(gotAmt["currency"]) != fmt.Sprint(wantAmt["currency"]) {
		return verdict{false, "amount-mismatch",
			fmt.Sprintf("got %v want %v", gotAmt, wantAmt), rootMandate, 2}
	}

	return verdict{true, "ok",
		fmt.Sprintf("chain valid, cnf=agent key, amount %v %v matches reference",
			gotAmt["amount"], gotAmt["currency"]), rootMandate, 2}
}

// sameJWK compares the EC coordinates of two JWKs.
func sameJWK(a, b map[string]any) bool {
	return fmt.Sprint(a["x"]) == fmt.Sprint(b["x"]) && fmt.Sprint(a["y"]) == fmt.Sprint(b["y"])
}

func main() {
	dir := "vectors"
	if len(os.Args) > 1 {
		dir = os.Args[1]
	}
	entries, err := filepath.Glob(filepath.Join(dir, "*.json"))
	if err != nil || len(entries) == 0 {
		fmt.Fprintln(os.Stderr, "no vectors found in", dir)
		os.Exit(1)
	}
	sort.Strings(entries)

	passed, failed := 0, 0
	for _, p := range entries {
		if strings.HasSuffix(p, "index.json") {
			continue
		}
		raw, err := os.ReadFile(p)
		if err != nil {
			fmt.Printf("  FAIL  %s — %v\n", filepath.Base(p), err)
			failed++
			continue
		}
		var f Fixture
		if err := json.Unmarshal(raw, &f); err != nil {
			fmt.Printf("  FAIL  %s — %v\n", filepath.Base(p), err)
			failed++
			continue
		}
		v := verify(f)
		if v.ok {
			passed++
			fmt.Printf("  OK    %-42s — %s\n", f.ID, v.detail)
		} else {
			failed++
			fmt.Printf("  FAIL  %-42s — %s: %s\n", f.ID, v.stage, v.detail)
		}
	}
	fmt.Printf("\n  total: %d/%d passed verification\n", passed, passed+failed)
	if failed > 0 {
		os.Exit(1)
	}
}