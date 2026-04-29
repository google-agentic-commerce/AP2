import {useState} from 'react';
import type {TrustedSurface} from '../trustedSurface';
import type {MandateApprovalData, MandateRequest} from '../types';
import './MandateApproval.scss';

interface Props {
  mandate: MandateRequest;
  trustedSurface: TrustedSurface;
  onApprove: (mandateRequest: MandateApprovalData) => void;
  onReject: () => void;
  itemName?: string;
  currentPrice?: number;
}

export function MandateApproval({
  mandate,
  trustedSurface,
  onApprove,
  onReject,
  itemName,
  currentPrice,
}: Props) {
  const [state, setState] = useState<'idle' | 'signing' | 'signed'>('idle');

  async function handleSign() {
    setState('signing');
    try {
      const authOk = await trustedSurface.requestBiometricAuth();
      if (!authOk) {
        setState('idle');
        return;
      }
      const mandateRequest: MandateApprovalData = {
        item_id: mandate.item_id,
        item_name: mandate.item_name,
        price_cap: mandate.price_cap,
        qty: mandate.qty ?? 1,
        constraints: {
          price_lt: mandate.constraints?.price_lt ?? mandate.price_cap,
        },
        matches: mandate.matches?.map((m) => ({
          item_id: m.item_id,
          name: m.name,
        })),
      };
      setState('signed');
      setTimeout(() => onApprove(mandateRequest), 300);
    } catch {
      setState('idle');
    }
  }

  const priceCap = mandate.price_cap ?? 0;
  const qty = mandate.qty ?? 1;
  const current = currentPrice ?? mandate.current_price;
  const hasCurrentPrice = current != null && current > 0;
  const gap = hasCurrentPrice ? current - priceCap : 0;
  const pct = hasCurrentPrice ? Math.round((priceCap / current) * 100) : 0;

  const availabilityMode =
    mandate.constraint_focus === 'availability' ||
    (mandate.constraint_focus == null && mandate.available === false);

  return (
    <div className="msg-agent mandate-approval-container">
      <div className="mandate-card">
        {/* Header */}
        <div className="mandate-header">
          <div className="icon-wrapper">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <title>Mandate</title>
              <path
                d="M8 2L10.5 6.5H14L10.5 9L12 13.5L8 11L4 13.5L5.5 9L2 6.5H5.5L8 2Z"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <div className="title-container">
            <div className="title">Trusted Surface For Mandates</div>
            <div className="subtitle">AP2 · Open Mandates</div>
          </div>
        </div>

        {/* Body */}
        <div className="mandate-body">
          <div className="item-section">
            <div className="section-label">Item</div>
            <div className="item-name">
              {itemName ?? mandate.item_name ?? mandate.item_id}
            </div>
            <div className="item-id item-id-muted">{mandate.item_id}</div>
          </div>

          {availabilityMode ? (
            <>
              <div className="details-grid details-grid-availability">
                {[
                  {
                    label: 'Budget (max)',
                    value: `$${priceCap}`,
                    accent: '#60a5fa',
                  },
                  {
                    label: 'Availability',
                    value: mandate.available
                      ? 'In stock'
                      : 'Not yet — awaiting drop',
                    accent: mandate.available ? '#34d399' : '#fbbf24',
                  },
                  {label: 'Qty', value: String(qty), accent: '#94a3b8'},
                ].map((f) => (
                  <div key={f.label} className="grid-item">
                    <div className="item-label">{f.label}</div>
                    <div className="item-value" style={{color: f.accent}}>
                      {f.value}
                    </div>
                  </div>
                ))}
              </div>

              <div className="gap-indicator gap-indicator-availability">
                <div className="gap-header">
                  <span className="gap-label">Trigger condition</span>
                  <span className="gap-status pending">
                    Availability + budget
                  </span>
                </div>
                <p className="gap-prose">
                  Agent will purchase when the item becomes available and price
                  is within your <span className="highlight">${priceCap}</span>{' '}
                  budget.
                </p>
              </div>

              {hasCurrentPrice && (
                <div className="reference-price-note">
                  Reference price: ${current?.toFixed(2) ?? "0.00"} (list)
                </div>
              )}
            </>
          ) : (
            <>
              <div className="details-grid">
                {[
                  {
                    label: 'Max Price',
                    value: `$${priceCap}`,
                    accent: '#60a5fa',
                  },
                  {
                    label: 'Current',
                    value: hasCurrentPrice ? `$${current?.toFixed(2) ?? "0.00"}` : '—',
                    accent: '#f87171',
                  },
                  {label: 'Qty', value: String(qty), accent: '#94a3b8'},
                ].map((f) => (
                  <div key={f.label} className="grid-item">
                    <div className="item-label">{f.label}</div>
                    <div className="item-value" style={{color: f.accent}}>
                      {f.value}
                    </div>
                  </div>
                ))}
              </div>

              {hasCurrentPrice && (
                <div className="gap-indicator">
                  <div className="gap-header">
                    <span className="gap-label">Price gap to trigger</span>
                    <span
                      className={`gap-status ${gap <= 0 ? 'met' : 'pending'}`}>
                      {gap <= 0
                        ? `✓ condition met`
                        : `-$${gap.toFixed(2)} needed`}
                    </span>
                  </div>
                  <div className="progress-track">
                    <div
                      className={`progress-bar ${gap <= 0 ? 'met' : 'pending'}`}
                      style={{width: `${Math.min(Math.max(pct, 0), 100)}%`}}
                    />
                  </div>
                </div>
              )}
            </>
          )}

          {/* Payment method row */}
          <div className="fop-row">
            <svg width="32" height="20" viewBox="0 0 32 20" fill="none">
              <title>Payment card</title>
              <rect
                width="32"
                height="20"
                rx="3"
                fill="#1a1f3c"
                stroke="#2d3555"
                strokeWidth="0.5"
              />
              <rect
                x="0"
                y="4"
                width="32"
                height="3"
                fill="#ca8a04"
                opacity="0.6"
              />
              <rect
                x="4"
                y="11"
                width="10"
                height="2"
                rx="0.5"
                fill="#4b5563"
              />
              <rect
                x="4"
                y="14.5"
                width="6"
                height="1.5"
                rx="0.5"
                fill="#374151"
              />
            </svg>
            <div className="fop-details">
              <span className="fop-name">
                {mandate.payment_method === 'x402'
                  ? mandate.payment_method_description ||
                    'x402 ••• USDC (Base Sepolia)'
                  : 'Card •••4242'}
              </span>
              <span className="fop-badge">
                {mandate.payment_method === 'x402' ? 'USDC (Base)' : 'Default'}
              </span>
            </div>
          </div>

          <div className="info-banner">
            Approving creates a cryptographic mandate. The agent will purchase
            autonomously when{' '}
            {availabilityMode ? 'the item is available and within' : 'price ≤'}{' '}
            <span className="highlight">${priceCap}</span>
            {availabilityMode ? ' budget' : ''}. You can close this window.
          </div>

          {state === 'idle' && (
            <div className="action-buttons">
              <button type="button" className="approve-button" onClick={handleSign}>
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <title>Approve</title>
                  <path
                    d="M7 1L8.8 4.8L13 5.3L10 8.2L10.7 12.4L7 10.5L3.3 12.4L4 8.2L1 5.3L5.2 4.8L7 1Z"
                    stroke="white"
                    strokeWidth="1.2"
                    fill="rgba(255,255,255,.2)"
                    strokeLinejoin="round"
                  />
                </svg>
                Approve & Sign
              </button>
              <button type="button" className="reject-button" onClick={onReject}>
                Reject
              </button>
            </div>
          )}

          {state === 'signing' && (
            <div className="signing-state">
              <div className="spinner" />
              Signing with ECDSA P-256…
            </div>
          )}

          {state === 'signed' && (
            <div className="signed-state">
              <div className="success-badge">
                <svg width="10" height="10" viewBox="0 0 10 10">
                  <title>Signed</title>
                  <path
                    d="M2 5l2 2 4-4"
                    stroke="white"
                    strokeWidth="1.5"
                    fill="none"
                    strokeLinecap="round"
                    strokeDasharray="24"
                    strokeDashoffset="0"
                  />
                </svg>
              </div>
              <span className="status-text">Mandate signed</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
