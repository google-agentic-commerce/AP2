# AP2 Sample: PII Sanitization Before Autonomous Payment

This sample demonstrates how an autonomous AI agent sanitizes PII from
text using **TrustBoost** before completing an **AP2 + x402** payment.

## Scenario

A shopping agent receives user-generated text containing PII. Before
sending to an LLM or completing an x402 payment, the agent calls
TrustBoost to redact PII and receive immutable proof on Solana.

## Key Features

- Autonomous PII sanitization via TrustBoost x402 protocol
- Proof of Sanitization anchored on Solana mainnet
- 8 languages: EN, ES-LATAM, PT-BR, DE, JA, FR, IT, KO
- EU AI Act compliant (Articles 12, 13, 26)

## Quick Start

```bash
pip install -r requirements.txt
python agent.py
```

## Resources

- [TrustBoost](https://github.com/teodorofodocrispin-cmyk/TrustBoost-PII-Sanitizer)
- [Agent Card](https://api.trustboost.dev/.well-known/agent-card.json)
- [Health](https://api.trustboost.dev/health)
- [AP2 docs](https://ap2-protocol.org)
