// Package sdjwt implements the minimum of SD-JWT needed to verify AP2 mandates.
//
// Why this exists
// ---------------
// As of 2026-10-04 the Go sample in google-agentic-commerce/AP2 ships no signing
// or verification code at all: 2258 lines, zero crypto, a hardcoded FakeJWT in
// code/samples/go/pkg/roles/merchant_agent/tools.go. No Go implementation can
// therefore verify a mandate, which means no Go implementation can be tested.
//
// Standard library only, deliberately. The claim "Go cannot do this" should be
// disproved without adding a dependency.
//
// Wire format, as implemented by the reference Python SDK
// -------------------------------------------------------
//   compact token : "header.payload.signature~disc~disc~...~"
//   issuer_jwt    : parts[0]
//   disclosures   : parts[1:-1]
//   kb_jwt        : parts[-1] when the token does not end with "~"
//   disclosure    : base64url( JSON array [salt, value] or [salt, name, value] )
//   digest        : base64url( sha256( *raw disclosure string* ) )
//   sd_jwt        : issuer_jwt + "~" + strings.Join(disclosures, "~") + "~"
//   sd_hash       : base64url( sha256( sd_jwt string ) )
//
// A delegate item of the form {"...": "<digest>"} is a placeholder: the
// disclosure whose digest matches is decoded and *replaces* that item in place,
// which is why the mandate claims end up at the top level after resolution.
package sdjwt

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"math/big"
	"strings"
)

// PlaceholderKey is the key under which a selectively disclosed whole object is
// referenced inside delegate_payload.
const PlaceholderKey = "..."

// Token is a parsed SD-JWT.
type Token struct {
	Raw         string
	IssuerJWT   string
	Disclosures []string
	KBJWT       string
	Header      map[string]any
	Payload     map[string]any
}

// Parse decodes a compact SD-JWT: "header.payload.signature~disc~...~".
func Parse(raw string) (*Token, error) {
	if raw == "" {
		return nil, errors.New("empty token")
	}
	if strings.HasPrefix(raw, "~") {
		return nil, errors.New("malformed: empty issuer JWT")
	}
	parts := strings.Split(raw, "~")
	t := &Token{Raw: raw, IssuerJWT: parts[0]}

	if strings.HasSuffix(raw, "~") {
		t.Disclosures = parts[1 : len(parts)-1]
	} else {
		t.Disclosures = parts[1 : len(parts)-1]
		t.KBJWT = parts[len(parts)-1]
		if len(strings.Split(t.KBJWT, ".")) != 3 {
			return nil, errors.New("malformed KB-JWT: expected header.payload.signature")
		}
	}
	for i, d := range t.Disclosures {
		if d == "" {
			return nil, fmt.Errorf("malformed: empty disclosure segment %d", i)
		}
	}

	jwtParts := strings.Split(t.IssuerJWT, ".")
	if len(jwtParts) != 3 {
		return nil, fmt.Errorf("issuer JWT must be header.payload.signature, got %d", len(jwtParts))
	}
	hdr, err := decodeObject(jwtParts[0])
	if err != nil {
		return nil, fmt.Errorf("header: %w", err)
	}
	pl, err := decodeObject(jwtParts[1])
	if err != nil {
		return nil, fmt.Errorf("payload: %w", err)
	}
	t.Header, t.Payload = hdr, pl
	return t, nil
}

// Typ reports the JWT typ header.
func (t *Token) Typ() string { s, _ := t.Header["typ"].(string); return s }

// Kid reports the JWT kid header.
func (t *Token) Kid() string { s, _ := t.Header["kid"].(string); return s }

// SDAlg reports the _sd_alg from the payload.
func (t *Token) SDAlg() string { s, _ := t.Payload["_sd_alg"].(string); return s }

// SDJWT is the canonical string of this token including its disclosures. This is
// what a following KB-SD-JWT binds itself to via sd_hash.
func (t *Token) SDJWT() string {
	if len(t.Disclosures) == 0 {
		return t.IssuerJWT + "~"
	}
	return t.IssuerJWT + "~" + strings.Join(t.Disclosures, "~") + "~"
}

// VerifyES256 checks the signature over the issuer JWT portion.
func (t *Token) VerifyES256(pub *ecdsa.PublicKey) error {
	alg, _ := t.Header["alg"].(string)
	if alg != "ES256" {
		return fmt.Errorf("unsupported alg %q, want ES256", alg)
	}
	jwtParts := strings.Split(t.IssuerJWT, ".")
	sig, err := b64Decode(jwtParts[2])
	if err != nil {
		return fmt.Errorf("signature: %w", err)
	}
	if len(sig) != 64 {
		return fmt.Errorf("signature length %d, want 64 for raw r||s", len(sig))
	}
	// JWS signing input is "header.payload", without the signature.
	signingInput := jwtParts[0] + "." + jwtParts[1]
	digest := sha256.Sum256([]byte(signingInput))
	r := new(big.Int).SetBytes(sig[:32])
	s := new(big.Int).SetBytes(sig[32:])
	if !ecdsa.Verify(pub, digest[:], r, s) {
		return errors.New("signature does not verify")
	}
	return nil
}

// DisclosureDigest returns base64url(sha256(raw disclosure string)).
func DisclosureDigest(raw, sdAlg string) (string, error) {
	switch sdAlg {
	case "", "sha-256":
		sum := sha256.Sum256([]byte(raw))
		return base64.RawURLEncoding.EncodeToString(sum[:]), nil
	default:
		return "", fmt.Errorf("unsupported _sd_alg %q", sdAlg)
	}
}

// SDHash is what a following hop stores as sd_hash to bind itself to prev.
func SDHash(prev *Token) (string, error) {
	return DisclosureDigest(prev.SDJWT(), prev.SDAlg())
}

// EffectiveMandate resolves the delegate_payload into the concrete mandate.
// Placeholder items {"...": digest} are replaced by the decoded disclosure.
func (t *Token) EffectiveMandate() (map[string]any, error) {
	dp, ok := t.Payload["delegate_payload"]
	if !ok {
		return nil, errors.New("no delegate_payload claim")
	}
	list, ok := dp.([]any)
	if !ok {
		return nil, fmt.Errorf("delegate_payload is %T, want array", dp)
	}

	var mandate map[string]any
	for _, item := range list {
		resolved, err := t.resolveItem(item)
		if err != nil {
			return nil, err
		}
		if resolved == nil {
			continue
		}
		if mandate != nil {
			return nil, errors.New("expected exactly one disclosed mandate")
		}
		mandate = resolved
	}
	if mandate == nil {
		return nil, errors.New("delegate_payload yielded no mandate")
	}
	return mandate, nil
}

func (t *Token) resolveItem(item any) (map[string]any, error) {
	alg := t.SDAlg()

	switch v := item.(type) {
	case map[string]any:
		// Placeholder form: {"...": "<digest>"}
		if len(v) == 1 {
			if dg, ok := v[PlaceholderKey].(string); ok {
				return t.disclosureDict(dg, alg)
			}
		}
		// Standard form: "_sd": ["<digest>", ...] alongside plain claims.
		out := map[string]any{}
		for k, val := range v {
			if k == "_sd" {
				continue
			}
			out[k] = val
		}
		if arr, ok := v["_sd"].([]any); ok {
			for _, e := range arr {
				dg, _ := e.(string)
				d, err := t.disclosureAny(dg, alg)
				if err != nil {
					return nil, err
				}
				switch val := d.(type) {
				case []any:
					if len(val) == 3 {
						name, _ := val[1].(string)
						out[name] = val[2]
					}
				case map[string]any:
					for k2, v2 := range val {
						out[k2] = v2
					}
				}
			}
		}
		return out, nil

	case string:
		// Digest string referencing an appended disclosure.
		return t.disclosureDict(v, alg)
	}
	return nil, nil
}

func (t *Token) disclosureDict(digest, alg string) (map[string]any, error) {
	val, err := t.disclosureAny(digest, alg)
	if err != nil {
		return nil, err
	}
	m, ok := val.(map[string]any)
	if !ok {
		return nil, fmt.Errorf("disclosure %s does not resolve to an object", digest)
	}
	return m, nil
}

// disclosureAny finds the disclosure matching digest and returns its value.
func (t *Token) disclosureAny(digest, alg string) (any, error) {
	for _, raw := range t.Disclosures {
		got, err := DisclosureDigest(raw, alg)
		if err != nil {
			return nil, err
		}
		if got != digest {
			continue
		}
		arr, err := decodeArray(raw)
		if err != nil {
			return nil, err
		}
		switch len(arr) {
		case 2:
			return arr[1], nil
		case 3:
			return arr[2], nil
		default:
			return nil, fmt.Errorf("disclosure array has %d elements, want 2 or 3", len(arr))
		}
	}
	return nil, fmt.Errorf("no disclosure matches digest %s", digest)
}

// CNFJWK extracts cnf.jwk from a resolved mandate.
func CNFJWK(mandate map[string]any) (map[string]any, bool) {
	cnf, ok := mandate["cnf"].(map[string]any)
	if !ok {
		return nil, false
	}
	jwk, ok := cnf["jwk"].(map[string]any)
	if !ok {
		return nil, false
	}
	return jwk, true
}

// PublicKeyFromJWK reconstructs an ECDSA P-256 public key from a JWK.
func PublicKeyFromJWK(jwk map[string]any) (*ecdsa.PublicKey, error) {
	if kty, _ := jwk["kty"].(string); kty != "EC" {
		return nil, fmt.Errorf("kty %v, want EC", jwk["kty"])
	}
	if crv, _ := jwk["crv"].(string); crv != "P-256" {
		return nil, fmt.Errorf("crv %v, want P-256", jwk["crv"])
	}
	xb, err := b64Decode(mustStr(jwk, "x"))
	if err != nil {
		return nil, fmt.Errorf("x: %w", err)
	}
	yb, err := b64Decode(mustStr(jwk, "y"))
	if err != nil {
		return nil, fmt.Errorf("y: %w", err)
	}
	pub := &ecdsa.PublicKey{
		Curve: elliptic.P256(),
		X:     new(big.Int).SetBytes(xb),
		Y:     new(big.Int).SetBytes(yb),
	}
	if !pub.Curve.IsOnCurve(pub.X, pub.Y) {
		return nil, errors.New("JWK point is not on P-256")
	}
	return pub, nil
}

func decodeObject(seg string) (map[string]any, error) {
	raw, err := b64Decode(seg)
	if err != nil {
		return nil, err
	}
	var out map[string]any
	d := json.NewDecoder(strings.NewReader(string(raw)))
	d.UseNumber()
	if err := d.Decode(&out); err != nil {
		return nil, err
	}
	return out, nil
}

func decodeArray(seg string) ([]any, error) {
	raw, err := b64Decode(seg)
	if err != nil {
		return nil, err
	}
	var out []any
	d := json.NewDecoder(strings.NewReader(string(raw)))
	d.UseNumber()
	if err := d.Decode(&out); err != nil {
		return nil, err
	}
	return out, nil
}

func b64Decode(s string) ([]byte, error) {
	return base64.RawURLEncoding.DecodeString(strings.TrimRight(s, "="))
}

func mustStr(m map[string]any, k string) string {
	s, _ := m[k].(string)
	return s
}