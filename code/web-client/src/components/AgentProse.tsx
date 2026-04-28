import ReactMarkdown from 'react-markdown';

interface Props {
  text: string;
}

export function AgentProse({text}: Props) {
  return (
    <div className="agent-prose-text">
      <ReactMarkdown
        components={{
          p: ({children}) => <p>{children}</p>,
          strong: ({children}) => <strong>{children}</strong>,
          ol: ({children}) => <ol>{children}</ol>,
          ul: ({children}) => <ul>{children}</ul>,
          li: ({children}) => <li>{children}</li>,
          code: ({children}) => <code>{children}</code>,
        }}>
        {text}
      </ReactMarkdown>
    </div>
  );
}
