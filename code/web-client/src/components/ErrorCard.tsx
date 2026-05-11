import type {ErrorArtifact} from '../types';
import './ErrorCard.scss';

interface Props {
  error: ErrorArtifact;
}

export function ErrorCard({error}: Props) {
  return (
    <div className="msg-agent error-card">
      <div className="error-header">
        <div className="error-icon-wrapper">
          <span className="error-icon">!</span>
        </div>
        <span className="error-label">Error</span>
        <div className="error-type">{error.error}</div>
      </div>
      <p className="error-message">{error.message}</p>
    </div>
  );
}
