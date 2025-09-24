# B2B Procurement Agent Demo (AP2)

This sample demonstrates how to apply **Google’s Agent Payment Protocol (AP2)** in a **B2B procurement workflow**.  
It extends the existing consumer **cards** demo by simulating enterprise purchasing:

- **Intent Mandate**: created from a natural language request (e.g. “Request a laptop under $1200”).
- **Cart Mandate**: built from a procurement catalog (`catalog.json`) with vendor and SKU details.
- **Payment Mandate**: mock card entry + OTP flow (OTP = `123`) to simulate enterprise payment authorization.

All mandates are constructed using the **AP2 Pydantic types** in `src/ap2/types/` and are saved as JSON under the `mandates/` folder.

---

## 🚀 Run the Demo

From the repo root:

```bash
bash samples/python/scenarios/b2b/procurement/run.sh
