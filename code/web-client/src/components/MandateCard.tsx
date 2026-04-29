import { useMemo, useState } from 'react';
import type { MandateEntry, MandateEntryKind } from '../types';
import {
  decodeJwt,
  decodeSdJwtSync,
  type DecodedJwt,
  type DecodedSdJwt,
} from '../utils/sdJwtDecoder';
import './MandateCard.scss';

interface Props {
  entry: MandateEntry;
}

const KIND_LABELS: Record<MandateEntryKind, { label: string; accent: string }> = {
  mandate_request: { label: 'Mandate Request', accent: '#60a5fa' },
  open_checkout_mandate: { label: 'Open Checkout', accent: '#a78bfa' },
  open_payment_mandate: { label: 'Open Payment', accent: '#a78bfa' },
  checkout_jwt: { label: 'Checkout JWT', accent: '#34d399' },
  closed_checkout_mandate: { label: 'Closed Checkout', accent: '#fbbf24' },
  closed_payment_mandate: { label: 'Closed Payment', accent: '#fbbf24' },
  presentation: { label: 'Presentation', accent: '#f472b6' },
  mandate_chain: { label: 'Mandate Chain', accent: '#fb7185' },
};

function truncate(s: string, n = 48): string {
  return s.length > n ? `${s.slice(0, n)}…` : s;
}

function formatTimestamp(ts: number): string {
  return new Date(ts).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

/** Extract a few human-friendly summary bullets based on entry kind. */
function summarizeEntry(
  entry: MandateEntry,
  sd?: DecodedSdJwt,
  jwt?: DecodedJwt,
): Array<{ label: string; value: string }> {
  const out: Array<{ label: string; value: string }> = [];
  const delegate = (sd?.issuerJwt.payload.delegate_payload as unknown[]) ?? [];
  let first = (delegate[0] ?? {}) as Record<string, unknown>;

  if (
    (!first.vct || (Object.keys(first).length === 1 && first['...'])) &&
    sd?.disclosures
  ) {
    for (const d of sd.disclosures) {
      if (!d.key && typeof d.value === 'object' && d.value !== null) {
        const obj = d.value as Record<string, unknown>;
        if (obj.vct) {
          first = obj;
          break;
        }
      }
    }
  }

  switch (entry.kind) {
    case 'mandate_request': {
      const p = entry.rawPayload ?? {};
      if (typeof p.item_id === 'string')
        out.push({ label: 'Item', value: String(p.item_id) });
      if (typeof p.price_cap === 'number')
        out.push({ label: 'Price Cap', value: `$${p.price_cap}` });
      if (typeof p.qty === 'number')
        out.push({ label: 'Qty', value: String(p.qty) });
      if (typeof p.payment_method === 'string')
        out.push({ label: 'Method', value: String(p.payment_method) });
      break;
    }
    case 'open_checkout_mandate': {
      out.push({ label: 'VCT', value: String(first.vct ?? '—') });
      const constraints = (first.constraints as unknown[]) ?? [];
      const merchants = constraints.find(
        (c) =>
          (c as Record<string, unknown>).type === 'checkout.allowed_merchants',
      ) as Record<string, unknown> | undefined;
      const lineItems = constraints.find(
        (c) => (c as Record<string, unknown>).type === 'checkout.line_items',
      ) as Record<string, unknown> | undefined;
      if (merchants) {
        const arr = (merchants.allowed as unknown[]) ?? [];
        out.push({ label: 'Allowed Merchants', value: String(arr.length) });
      }
      if (lineItems) {
        const items = (lineItems.items as unknown[]) ?? [];
        out.push({ label: 'Line Item Rules', value: String(items.length) });
      }
      break;
    }
    case 'open_payment_mandate': {
      out.push({ label: 'VCT', value: String(first.vct ?? '—') });
      const constraints = (first.constraints as unknown[]) ?? [];
      const amount = constraints.find(
        (c) => (c as Record<string, unknown>).type === 'payment.amount_range',
      ) as Record<string, unknown> | undefined;
      if (amount) {
        const min = amount.min;
        const max = amount.max;
        const cur = amount.currency ?? '';
        out.push({
          label: 'Amount',
          value: `${min ?? 0}–${max ?? '∞'} ${String(cur)}`,
        });
      }
      const payees = constraints.find(
        (c) => (c as Record<string, unknown>).type === 'payment.allowed_payees',
      ) as Record<string, unknown> | undefined;
      if (payees) {
        const arr = (payees.allowed as unknown[]) ?? [];
        out.push({ label: 'Allowed Payees', value: String(arr.length) });
      }
      break;
    }
    case 'checkout_jwt': {
      const payload = jwt?.payload ?? entry.rawPayload ?? {};
      if (payload.cart_id)
        out.push({ label: 'Cart', value: String(payload.cart_id) });
      if (typeof payload.total === 'number')
        out.push({
          label: 'Total',
          value: `$${(payload.total / 100).toFixed(2)}`,
        });
      if (payload.currency)
        out.push({ label: 'Currency', value: String(payload.currency) });
      const merchant = payload.merchant as Record<string, unknown> | undefined;
      if (merchant?.name)
        out.push({ label: 'Merchant', value: String(merchant.name) });
      break;
    }
    case 'closed_checkout_mandate': {
      out.push({ label: 'VCT', value: String(first.vct ?? '—') });
      const ch = first.checkout_hash ?? entry.rawPayload?.checkout_hash;
      if (typeof ch === 'string') {
        out.push({ label: 'Checkout Hash', value: truncate(ch, 32) });
      }
      const inner = first.checkout_jwt;
      if (typeof inner === 'string' && inner.split('.').length === 3) {
        out.push({ label: 'Binds', value: 'Merchant-signed checkout JWT' });
      }
      break;
    }
    case 'closed_payment_mandate': {
      out.push({ label: 'VCT', value: String(first.vct ?? '—') });
      const src = sd ? first : (entry.rawPayload ?? {});
      const tx = src.transaction_id;
      if (typeof tx === 'string') {
        out.push({ label: 'Transaction', value: truncate(tx, 32) });
      }
      const amount = src.amount as Record<string, unknown> | undefined;
      if (amount) {
        const amt = amount.amount;
        const cur = amount.currency ?? '';
        if (typeof amt === 'number') {
          out.push({
            label: 'Amount',
            value: `${(amt / 100).toFixed(2)} ${String(cur)}`,
          });
        }
      }
      const payee = src.payee as Record<string, unknown> | undefined;
      if (payee?.name) out.push({ label: 'Payee', value: String(payee.name) });
      break;
    }
    case 'mandate_chain':
    case 'presentation': {
      if (sd?.kbJwt?.payload) {
        const aud = sd.kbJwt.payload.aud;
        const nonce = sd.kbJwt.payload.nonce;
        if (aud) out.push({ label: 'Audience', value: String(aud) });
        if (nonce)
          out.push({ label: 'Nonce', value: truncate(String(nonce), 24) });
      } else if (entry.rawPayload) {
        const aud = entry.rawPayload.aud;
        const nonce = entry.rawPayload.nonce;
        const chainId = entry.rawPayload.mandate_chain_id;
        if (aud) out.push({ label: 'Audience', value: String(aud) });
        if (nonce)
          out.push({ label: 'Nonce', value: truncate(String(nonce), 24) });
        if (chainId)
          out.push({ label: 'Chain', value: truncate(String(chainId), 24) });
      }
      break;
    }
  }
  return out;
}

function JsonBlock({ value }: { value: unknown }) {
  return (
    <pre className="json-block">
      <code>{JSON.stringify(value, null, 2)}</code>
    </pre>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="copy-button"
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1200);
      }}>
      {copied ? 'Copied' : 'Copy'}
    </button>
  );
}

export function MandateCard({ entry }: Props) {
  const [expanded, setExpanded] = useState(false);

  const { sd, jwt, error } = useMemo(() => {
    if (!entry.rawToken) {
      return { sd: undefined, jwt: undefined, error: undefined };
    }
    const looksLikeJwt =
      entry.rawToken.split('.').length === 3 || entry.rawToken.includes('~');
    if (!looksLikeJwt) {
      return { sd: undefined, jwt: undefined, error: undefined };
    }
    try {
      let tokenToDecode = entry.rawToken;
      if (tokenToDecode.includes('~~')) {
        const parts = tokenToDecode.split(/~~+/);
        tokenToDecode = parts[parts.length - 1];
      }

      if (entry.kind === 'checkout_jwt') {
        return {
          sd: undefined,
          jwt: decodeJwt(tokenToDecode),
          error: undefined,
        };
      }
      if (tokenToDecode.includes('~')) {
        return {
          sd: decodeSdJwtSync(tokenToDecode),
          jwt: undefined,
          error: undefined,
        };
      }
      return { sd: undefined, jwt: decodeJwt(tokenToDecode), error: undefined };
    } catch (e) {
      return { sd: undefined, jwt: undefined, error: (e as Error).message };
    }
  }, [entry.rawToken, entry.kind]);

  const isMandateChain = entry.kind === 'mandate_chain';
  const issuerJwt = sd?.issuerJwt ?? jwt;
  const payloadError = issuerJwt?.payloadError;
  const headerError = issuerJwt?.headerError;
  const rawPayloadString = issuerJwt?.rawPayloadString;

  const kindInfo = KIND_LABELS[entry.kind];
  const summary = summarizeEntry(entry, sd, jwt);
  const payloadForDisplay =
    sd?.issuerJwt.payload ?? jwt?.payload ?? entry.rawPayload;
  const headerForDisplay = sd?.issuerJwt.header ?? jwt?.header;

  return (
    <div className="mandate-viewer-card">
      <button
        className="card-header"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}>
        <div className="left">
          <span
            className="kind-badge"
            style={{ borderColor: kindInfo.accent, color: kindInfo.accent }}>
            {kindInfo.label}
          </span>
          <div className="title-block">
            <div className="title">{entry.title}</div>
            {entry.subtitle && <div className="subtitle">{entry.subtitle}</div>}
          </div>
        </div>
        <div className="right">
          <span className="timestamp">{formatTimestamp(entry.timestamp)}</span>
          <span className={`chevron ${expanded ? 'open' : ''}`}>▸</span>
        </div>
      </button>

      {summary.length > 0 && (
        <div className="summary-grid">
          {summary.map((f) => (
            <div key={f.label} className="summary-item">
              <div className="label">{f.label}</div>
              <div className="value">{f.value}</div>
            </div>
          ))}
        </div>
      )}

      {expanded && (
        <div className="detail-section">
          {error && (
            <div className="decode-error">Could not decode: {error}</div>
          )}
          {headerError && (
            <div className="decode-error">
              Header parse failed: {headerError}
            </div>
          )}
          {payloadError && (
            <div className="decode-error">
              Payload parse failed: {payloadError}
              {rawPayloadString != null && (
                <span className="decode-hint">
                  {' '}
                  · Showing raw decoded string below (token may have been
                  truncated or corrupted in transit).
                </span>
              )}
            </div>
          )}

          {!isMandateChain && (
            <>
              {headerForDisplay && Object.keys(headerForDisplay).length > 0 && (
                <section>
                  <h4>JWT Header</h4>
                  <JsonBlock value={headerForDisplay} />
                </section>
              )}

              {payloadForDisplay &&
                Object.keys(payloadForDisplay).length > 0 && (
                  <section>
                    <h4>JWT Payload</h4>
                    <JsonBlock value={payloadForDisplay} />
                  </section>
                )}

              {payloadError && rawPayloadString && (
                <section>
                  <h4>Raw Decoded Payload</h4>
                  <pre className="json-block">
                    <code>{rawPayloadString}</code>
                  </pre>
                </section>
              )}

              {sd?.disclosures && sd.disclosures.length > 0 && (
                <section>
                  <h4>Disclosures ({sd.disclosures.length})</h4>
                  <div className="disclosure-table">
                    <div className="disclosure-row head">
                      <span>Salt</span>
                      <span>Key</span>
                      <span>Value</span>
                    </div>
                    {sd.disclosures.map((d, i) => (
                      <div key={i} className="disclosure-row">
                        <span className="mono small">
                          {truncate(d.salt, 18)}
                        </span>
                        <span className="mono">{d.key ?? '(array)'}</span>
                        <span
                          className="mono value-cell"
                          style={{ whiteSpace: 'pre-wrap' }}>
                          {typeof d.value === 'object'
                            ? JSON.stringify(d.value, null, 2)
                            : String(d.value)}
                        </span>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {sd?.kbJwt && (
                <section>
                  <h4>Key Binding JWT Header</h4>
                  <JsonBlock value={sd.kbJwt.header} />
                  <h4>Key Binding JWT Payload</h4>
                  <JsonBlock value={sd.kbJwt.payload} />
                </section>
              )}
            </>
          )}

          {entry.rawToken && (
            <section>
              <div className="raw-token-header">
                <h4>Raw Encoded Token</h4>
                <CopyButton text={entry.rawToken} />
              </div>
              <pre className="raw-token">
                <code>{entry.rawToken}</code>
              </pre>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
