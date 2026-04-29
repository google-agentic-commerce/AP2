/**
 * Derivation of MandateEntry[] from the current chat message history.
 *
 * The agent surfaces mandate artifacts in a few different shapes:
 *   - `mandate_request` — user-facing mandate proposal (JSON object)
 *   - `monitoring` — carries `open_checkout_mandate` and `open_payment_mandate`
 *     as encoded SD-JWT strings
 *   - `purchase_complete` — may carry `closed_payment_mandate` (SD-JWT string)
 *     and `closed_payment_mandate_content` (JSON object), sometimes also
 *     `checkout_jwt` / `closed_checkout_mandate`.
 *   - Tool calls (`tool_call` artifacts) for `create_checkout_presentation`,
 *     `create_payment_presentation`, and `present_mandate_chain` — these
 *     don't return the raw SD-JWT to the client, but the tool arguments let
 *     us document that the operation happened (embedded checkout JWT, target
 *     audience for a presentation, etc.).
 *
 * We scan the message list once, deduplicate identical tokens, and return a
 * chronologically ordered list suitable for the Mandates tab.
 */

import type {
  ChatMessage,
  MandateChainsFetched,
  MandateEntry,
  MandatesSigned,
  PurchaseComplete,
  ToolCallArtifact,
} from "../types";

type Draft = Omit<MandateEntry, "id">;

/** Stable string key for dedup (same token OR same decoded JSON object). */
function entryKey(d: Draft): string {
  if (d.rawToken) return `${d.kind}:token:${d.rawToken}`;
  if (d.rawPayload) {
    // For tool-call-derived entries, identify by stable discriminators so we
    // don't emit duplicates if the stream replays the same tool invocation.
    const p = d.rawPayload;
    if (typeof p.checkout_hash === "string") {
      return `${d.kind}:hash:${p.checkout_hash}`;
    }
    if (typeof p.transaction_id === "string") {
      return `${d.kind}:tx:${p.transaction_id}`;
    }
    if (typeof p.mandate_chain_id === "string" && typeof p.aud === "string") {
      return `${d.kind}:${p.aud}:${p.mandate_chain_id}`;
    }
    return `${d.kind}:payload:${JSON.stringify(p)}`;
  }
  return `${d.kind}:${d.title}:${d.timestamp}`;
}

function purchaseEntries(msg: ChatMessage, pc: PurchaseComplete): Draft[] {
  const out: Draft[] = [];
  const extra = pc as unknown as Record<string, unknown>;

  // Closed payment mandate -- token form.
  const closedPaymentToken = extra.closed_payment_mandate;
  if (
    typeof closedPaymentToken === "string" &&
    closedPaymentToken.includes("~")
  ) {
    out.push({
      kind: "closed_payment_mandate",
      title: "Closed Payment Mandate",
      subtitle: pc.order_id,
      timestamp: msg.timestamp,
      rawToken: closedPaymentToken,
    });
  }

  // Closed checkout mandate -- token form.
  const closedCheckoutToken = extra.closed_checkout_mandate;
  if (
    typeof closedCheckoutToken === "string" &&
    closedCheckoutToken.includes("~")
  ) {
    out.push({
      kind: "closed_checkout_mandate",
      title: "Closed Checkout Mandate",
      subtitle: pc.order_id,
      timestamp: msg.timestamp,
      rawToken: closedCheckoutToken,
    });
  }

  // Checkout JWT (merchant-signed, not an SD-JWT).
  const checkoutJwt = extra.checkout_jwt;
  if (typeof checkoutJwt === "string" && checkoutJwt.split(".").length === 3) {
    out.push({
      kind: "checkout_jwt",
      title: "Checkout JWT",
      subtitle: pc.order_id,
      timestamp: msg.timestamp,
      rawToken: checkoutJwt,
    });
  }

  return out;
}

function toolCallEntries(_msg: ChatMessage, _tc: ToolCallArtifact): Draft[] {
  const out: Draft[] = [];
  return out;
}

/** Scan the message list and produce a deduplicated, chronological list. */
export function deriveMandateEntries(messages: ChatMessage[]): MandateEntry[] {
  const drafts: Draft[] = [];
  for (const msg of messages) {
    const data = msg.artifactData as { type?: string } | undefined;
    if (!data) continue;

    switch (data.type) {
      case "mandates_signed": {
        const ms = data as unknown as MandatesSigned;
        if (ms.open_checkout_mandate) {
          drafts.push({
            kind: "open_checkout_mandate",
            title: "Open Checkout Mandate",
            timestamp: msg.timestamp,
            rawToken: ms.open_checkout_mandate,
          });
        }
        if (ms.open_payment_mandate) {
          drafts.push({
            kind: "open_payment_mandate",
            title: "Open Payment Mandate",
            timestamp: msg.timestamp,
            rawToken: ms.open_payment_mandate,
          });
        }
        break;
      }
      case "purchase_complete":
        drafts.push(
          ...purchaseEntries(msg, data as unknown as PurchaseComplete)
        );
        break;
      case "tool_call":
        drafts.push(
          ...toolCallEntries(msg, data as unknown as ToolCallArtifact)
        );
        break;
      case "mandate_chains_fetched": {
        const mcf = data as unknown as MandateChainsFetched;
        if (mcf.payment_mandate_chain) {
          drafts.push({
            kind: "mandate_chain",
            title: "Payment Mandate Chain",
            timestamp: msg.timestamp,
            rawToken: mcf.payment_mandate_chain,
          });

          // Extract closed payment mandate
          const parts = mcf.payment_mandate_chain.split("~~");
          const closedToken = parts[parts.length - 1];
          drafts.push({
            kind: "closed_payment_mandate",
            title: "Closed Payment Mandate",
            timestamp: msg.timestamp,
            rawToken: closedToken,
          });
        }
        if (mcf.checkout_mandate_chain) {
          drafts.push({
            kind: "mandate_chain",
            title: "Checkout Mandate Chain",
            timestamp: msg.timestamp,
            rawToken: mcf.checkout_mandate_chain,
          });

          // Extract closed checkout mandate
          const parts = mcf.checkout_mandate_chain.split("~~");
          const closedToken = parts[parts.length - 1];
          drafts.push({
            kind: "closed_checkout_mandate",
            title: "Closed Checkout Mandate",
            timestamp: msg.timestamp,
            rawToken: closedToken,
          });
        }
        break;
      }
      default:
        break;
    }
  }

  const seen = new Set<string>();
  const result: MandateEntry[] = [];
  for (const d of drafts) {
    const key = entryKey(d);
    if (seen.has(key)) continue;
    seen.add(key);
    result.push({ ...d, id: `mandate_${result.length}_${d.timestamp}` });
  }
  return result;
}
