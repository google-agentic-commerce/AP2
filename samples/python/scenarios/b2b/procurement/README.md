# B2B Procurement Agent Demo (AP2)

This sample demonstrates how to apply **Google’s Agent Payment Protocol (AP2)** in a **B2B procurement workflow**.  
It extends the existing `cards` scenario by adding:

- **Intent Mandate**: created from a natural language request (e.g. “Request a laptop under $1200”).
- **Cart Mandate**: built from a procurement catalog (`catalog.json`) with vendor + SKU info.
- **Payment Mandate**: mock card entry + OTP verification (OTP = `123`) to simulate enterprise payment flows.

All mandates are **real AP2 objects** from `src/ap2/types/mandate.py` and `payment_request.py`.  
They are serialized as JSON into the `mandates/` folder for inspection.

---

## 🚀 Run the Demo

From the repository root:

```bash
bash samples/python/scenarios/b2b/procurement/run.sh
