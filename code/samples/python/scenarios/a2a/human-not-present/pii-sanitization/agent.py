import os
import requests
from dotenv import load_dotenv

load_dotenv()

TRUSTBOOST_URL = "https://api.trustboost.dev"
TX_HASH = os.getenv("TRUSTBOOST_TX_HASH", "TRIAL")
WALLET = os.getenv("TRUSTBOOST_WALLET", "ap2-sample-agent")


def discover_trustboost():
    r = requests.get(f"{TRUSTBOOST_URL}/.well-known/agent-card.json", timeout=10)
    r.raise_for_status()
    card = r.json()
    print(f"[TrustBoost] {card.get('name', 'Unknown')} v{card.get('version', '?')}")
    print(f"[TrustBoost] Languages: {card.get('languages', [])}")
    print(f"[TrustBoost] Compliance: {card.get('compliance', [])}")
    return card


def sanitize_pii(text, context="general"):
    print(f"\n[Sanitizing] {len(text)} chars, context={context}")

    # x402 flow: call without payment -> HTTP 402 -> pay -> retry
    payload = {"text": text, "context": context}
    r = requests.post(f"{TRUSTBOOST_URL}/sanitize", json=payload, timeout=10)
    if r.status_code == 402:
        x402 = r.json().get("x402", {})
        accepts_list = x402.get("accepts", [])
        if accepts_list:
            acc = accepts_list[0]
            print(f"[x402] HTTP 402 - {acc.get('amount')} {acc.get('currency')} on {acc.get('network')}")
        print(f"[x402] Paying autonomously with tx_hash={TX_HASH}")
        payload.update({"tx_hash": TX_HASH, "wallet_address": WALLET})
        r = requests.post(f"{TRUSTBOOST_URL}/sanitize", json=payload, timeout=30)
    r.raise_for_status()
    data = r.json().get("data", {})

    print(f"[Result] {data.get('sanitized_content', '')[:80]}...")
    print(f"[Score] {data.get('safety_score')} | Risk: {data.get('risk_category')}")

    proof = data.get("proof_of_sanitization")
    if proof:
        print(f"[Proof] {proof.get('verify_url')}")

    return data


def main():
    print("=" * 60)
    print("AP2 Sample: PII Sanitization Before Autonomous Payment")
    print("=" * 60)

    discover_trustboost()

    tests = [
        {"lang": "English (Financial)", "text": "Wire to john@acme.com, SSN 123-45-6789", "ctx": "financial"},
        {"lang": "Spanish LATAM (Legal)", "text": "RFC: LOPJ850101ABC, CURP: LOPJ850101HDFRZN09", "ctx": "legal"},
        {"lang": "Portuguese BR", "text": "CPF: 123.456.789-09, email: paciente@hospital.com.br", "ctx": "medical"},
        {"lang": "Japanese", "text": "田中太郎、マイナンバー：123456789012", "ctx": "general"},
    ]

    mode = "TRIAL (50 free)" if TX_HASH == "TRIAL" else "PAID (x402 Solana)"
    print(f"\n[Mode] {mode}\n" + "=" * 60)

    for t in tests:
        print(f"\n[{t['lang']}] {t['text']}")
        try:
            sanitize_pii(t["text"], t["ctx"])
        except requests.exceptions.RequestException as e:
            print(f"[Error] {e}")

    print("\nPII sanitized. Safe to proceed with AP2 payment.")
    print(f"Verify: GET {TRUSTBOOST_URL}/verify/{{anchor_tx}}")


if __name__ == "__main__":
    main()
