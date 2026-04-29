import type {MonitoringStatus} from '../types';
import './MonitoringCard.scss';

interface Props {
  status: MonitoringStatus;
  onCheckNow?: () => void;
  triggerCurl?: string;
  pollIntervalSeconds?: number;
  itemName?: string;
}

export function MonitoringCard({
  status,
  onCheckNow,
  triggerCurl,
  pollIntervalSeconds,
  itemName,
}: Props) {
  const current = status.current_price ?? status.price_cap;
  const pct =
    current > 0
      ? Math.min(100, Math.round((status.price_cap / current) * 100))
      : 100;
  const available = status.available ?? false;

  return (
    <div className="msg-agent monitoring-card-container">
      <div className="monitoring-card">
        <div className="monitoring-header">
          <div className="status-dot" />
          <span className="title">Monitoring Board</span>
        </div>
        <div className="item-name">
          {itemName ?? status.item_id}
          {itemName && <span className="item-id">{status.item_id}</span>}
        </div>

        <div className="status-grid">
          <div className="status-cell">
            <span className="cell-label">Price</span>
            <span
              className={`cell-value ${status.current_price != null ? 'has-price' : 'no-price'}`}>
              {status.current_price != null
                ? `$${current.toFixed(2)}`
                : '— checking'}
            </span>
          </div>
          <div className="status-cell">
            <span className="cell-label">Target</span>
            <span className="cell-value target">${status.price_cap}</span>
          </div>
          <div className="status-cell">
            <span className="cell-label">Available</span>
            <span
              className={`cell-value ${available ? 'available-yes' : 'available-no'}`}>
              {available ? '✓ In stock' : '✗ Not yet'}
            </span>
          </div>
        </div>

        <div className="progress-track">
          <div className="progress-bar" style={{width: `${pct}%`}} />
        </div>
        <div className="info-text">
          You can close this window. Purchase will execute automatically when
          the item is available and within budget.
        </div>
        {triggerCurl && (
          <div className="curl-box">
            <div className="curl-label">Simulate drop (price + stock):</div>
            <code className="curl-code">{triggerCurl}</code>
          </div>
        )}
        {pollIntervalSeconds && (
          <p className="poll-text">
            Auto-checking every {pollIntervalSeconds}s
          </p>
        )}
        {onCheckNow && (
          <button type="button" onClick={onCheckNow} className="check-button">
            Check now
          </button>
        )}
      </div>
    </div>
  );
}
