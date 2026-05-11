import './TypingIndicator.scss';

export function TypingIndicator() {
  return (
    <div className="typing-indicator">
      {[0, 1, 2].map((i) => (
        <div key={i} className="dot" />
      ))}
    </div>
  );
}
