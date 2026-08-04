// runner_go.go — gowebpki/jcs v1.0.1 runner for AP2 open_mandate_hash v0.
//
// Reads vectors-v0.json, recomputes JCS + SHA-256 for each vector, and verifies
// recomputed hashes match expected_open_mandate_hash and pair expectations.
// For vectors carrying jws_compact, also verifies the decoded JWS payload
// re-canonicalizes to the same hash (envelope invariance; signatures are not
// verified).
//
// Usage:
//
//	go mod init jcs_runner && go get github.com/gowebpki/jcs@v1.0.1
//	go run runner_go.go vectors-v0.json
package main

import (
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"os"
	"strings"

	"github.com/gowebpki/jcs"
)

type vector struct {
	VectorID                string                 `json:"vector_id"`
	MandateBody             map[string]interface{} `json:"mandate_body"`
	JwsCompact              string                 `json:"jws_compact"`
	ExpectedJcsBytesB64     string                 `json:"expected_jcs_bytes_b64"`
	ExpectedOpenMandateHash string                 `json:"expected_open_mandate_hash"`
	Expectation             string                 `json:"expectation"`
}

type artefact struct {
	Vectors []vector `json:"vectors"`
}

func hashVector(body map[string]interface{}) (string, string, error) {
	raw, err := json.Marshal(body)
	if err != nil {
		return "", "", err
	}
	jcsBytes, err := jcs.Transform(raw)
	if err != nil {
		return "", "", err
	}
	sum := sha256.Sum256(jcsBytes)
	return base64.StdEncoding.EncodeToString(jcsBytes),
		hex.EncodeToString(sum[:]), nil
}

// jwsPayloadHash returns the sha256 hex of the canonicalized claims parsed
// from a JWS compact serialization's payload. Envelope invariance check only;
// signatures are not verified.
func jwsPayloadHash(jwsCompact string) (string, error) {
	parts := strings.Split(jwsCompact, ".")
	if len(parts) != 3 {
		return "", fmt.Errorf("jws_compact must have 3 parts, got %d", len(parts))
	}
	payload, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return "", err
	}
	var claims map[string]interface{}
	if err := json.Unmarshal(payload, &claims); err != nil {
		return "", err
	}
	_, sha, err := hashVector(claims)
	return sha, err
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: go run runner_go.go vectors-v0.json")
		os.Exit(2)
	}
	raw, err := ioutil.ReadFile(os.Args[1])
	if err != nil {
		fmt.Fprintf(os.Stderr, "read: %v\n", err)
		os.Exit(2)
	}
	var data artefact
	if err := json.Unmarshal(raw, &data); err != nil {
		fmt.Fprintf(os.Stderr, "parse: %v\n", err)
		os.Exit(2)
	}

	computed := map[string]string{}
	pass, fail := 0, 0
	for _, v := range data.Vectors {
		b64, sha, err := hashVector(v.MandateBody)
		if err != nil {
			fmt.Printf("  FAIL  %s  jcs error: %v\n", v.VectorID, err)
			fail++
			continue
		}
		computed[v.VectorID] = sha
		expectedSha := strings.TrimPrefix(v.ExpectedOpenMandateHash, "sha256:")
		bytesOk := b64 == v.ExpectedJcsBytesB64
		shaOk := sha == expectedSha
		jwsOk := true
		if v.JwsCompact != "" {
			payloadSha, jwsErr := jwsPayloadHash(v.JwsCompact)
			jwsOk = jwsErr == nil && payloadSha == sha
		}
		ok := bytesOk && shaOk && jwsOk
		mark := "OK  "
		if !ok {
			mark = "FAIL"
		}
		fmt.Printf("  %s  %-34s  sha256:%s\n", mark, v.VectorID, sha)
		if !ok {
			if !bytesOk {
				fmt.Println("        bytes mismatch")
			}
			if !shaOk {
				fmt.Printf("        expected sha256:%s\n", expectedSha)
			}
			if !jwsOk {
				fmt.Println("        jws payload hash mismatch (envelope invariance broken)")
			}
			fail++
		} else {
			pass++
		}
	}

	fmt.Println("\n--- pair invariants ---")
	pairFail := 0
	for _, v := range data.Vectors {
		exp := v.Expectation
		if strings.HasPrefix(exp, "same_hash_as:") {
			other := strings.TrimPrefix(exp, "same_hash_as:")
			ok := computed[v.VectorID] == computed[other]
			mark := "OK "
			if !ok {
				mark = "FAIL"
				pairFail++
			}
			fmt.Printf("  %s  %s == %s\n", mark, v.VectorID, other)
		} else if strings.HasPrefix(exp, "different_hash_from:") {
			other := strings.TrimPrefix(exp, "different_hash_from:")
			ok := computed[v.VectorID] != computed[other]
			mark := "OK "
			if !ok {
				mark = "FAIL"
				pairFail++
			}
			fmt.Printf("  %s  %s != %s\n", mark, v.VectorID, other)
		}
	}

	fmt.Printf("\n%d/%d vectors match (gowebpki/jcs v1.0.1)\n", pass, pass+fail)
	fmt.Printf("%d pair-invariant failures\n", pairFail)
	if fail == 0 && pairFail == 0 {
		os.Exit(0)
	}
	os.Exit(1)
}
