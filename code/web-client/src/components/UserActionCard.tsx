import './UserActionCard.scss';

interface Props {
  label: string;
  sublabel?: string;
}

export function UserActionCard({label, sublabel}: Props) {
  return (
    <div className="user-action-container">
      <div className="action-badge">
        <div className="check-icon">
          <svg width="8" height="8" viewBox="0 0 8 8">
            <title>Action confirmed</title>
            <path
              d="M1.5 4l2 2 3-3"
              stroke="white"
              strokeWidth="1.5"
              fill="none"
              strokeLinecap="round"
            />
          </svg>
        </div>
        <span className="label">{label}</span>
        {sublabel && <span className="sublabel">{sublabel}</span>}
      </div>
    </div>
  );
}
