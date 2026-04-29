import type {ToolCallArtifact} from '../types';
import './ToolCallCard.scss';

interface Props {
  call: ToolCallArtifact;
}

export function ToolCallCard({call}: Props) {
  const serverClass =
    call.server === 'Credential Provider MCP'
      ? 'server-credential'
      : call.server === 'Shopping Agent'
        ? 'server-shopping'
        : call.server === 'Merchant MCP'
          ? 'server-merchant'
          : '';

  return (
    <div className={`mcp-trace ${serverClass}`}>
      <div className="status-dot" />
      <span className="label">
        {call.server} · {call.tool}
        {call.message && <span className="message">— {call.message}</span>}
      </span>
    </div>
  );
}
