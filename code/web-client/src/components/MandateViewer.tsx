import type {MandateEntry, MandateEntryKind} from '../types';
import {MandateCard} from './MandateCard';
import './MandateViewer.scss';

interface Props {
  mandates: MandateEntry[];
}

/**
 * Order in which to present phases in the viewer.
 * Mirrors the AP2 flow: Request → Open Mandates → Checkout JWT →
 * Closed Mandates → Presentations.
 */
const PHASE_ORDER: Array<{
  title: string;
  blurb: string;
  kinds: MandateEntryKind[];
}> = [
  {
    title: 'Mandate Request',
    blurb: 'User-facing proposal built by the shopping agent.',
    kinds: ['mandate_request'],
  },
  {
    title: 'Open Mandates',
    blurb:
      'SD-JWTs issued by the credential provider authorizing future actions.',
    kinds: ['open_checkout_mandate', 'open_payment_mandate'],
  },
  {
    title: 'Checkout JWT',
    blurb: 'Merchant-signed checkout payload bound to the cart.',
    kinds: ['checkout_jwt'],
  },
  {
    title: 'Closed Mandates',
    blurb: 'Agent-signed delegate credentials completing the chain.',
    kinds: ['closed_checkout_mandate', 'closed_payment_mandate'],
  },
  {
    title: 'Mandate Chains',
    blurb: 'Full SD-JWT chains containing open and closed mandates.',
    kinds: ['mandate_chain'],
  },
  {
    title: 'Presentations',
    blurb: 'Key-binding presentations to merchant / credential provider.',
    kinds: ['presentation'],
  },
];

export function MandateViewer({mandates}: Props) {
  if (mandates.length === 0) {
    return (
      <div className="mandate-viewer-empty">
        <div className="icon">📝</div>
        <div className="title">No mandates yet</div>
        <div className="subtitle">
          Mandates created during this shopping session will appear here as
          structured cards with full SD-JWT detail.
        </div>
      </div>
    );
  }

  return (
    <div className="mandate-viewer">
      <div className="viewer-header">
        <div className="viewer-title">Mandates</div>
        <div className="viewer-subtitle">
          {mandates.length} mandate{mandates.length === 1 ? '' : 's'} in this
          session · click a card to expand decoded detail
        </div>
      </div>

      {PHASE_ORDER.map((phase) => {
        const entries = mandates.filter((m) => phase.kinds.includes(m.kind));
        if (entries.length === 0) return null;
        return (
          <section key={phase.title} className="phase-section">
            <div className="phase-header">
              <div className="phase-title">{phase.title}</div>
              <div className="phase-blurb">{phase.blurb}</div>
            </div>
            <div className="phase-cards">
              {entries.map((entry) => (
                <MandateCard key={entry.id} entry={entry} />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
