import ReactMarkdown from 'react-markdown';
import {MERCHANT_TRIGGER_URL} from '../config';
import type {ChatState} from '../hooks/useChat';
import {TrustedSurface} from '../trustedSurface';
import type {
  ChatMessage,
  ErrorArtifact,
  InventoryOptionsArtifact,
  MandateRequest,
  MonitoringStatus,
  ProductPreviewUnavailable,
  PurchaseComplete,
  ToolCallArtifact,
} from '../types';
import {
  extractCurrentPriceFromText,
  extractErrorFromText,
  extractMandateFromText,
  extractMonitoringFromText,
  removeArtifactJsonFromText,
} from '../utils/parsing';
import {AgentProse} from './AgentProse';
import {ErrorCard} from './ErrorCard';
import {InventoryOptionsCard} from './InventoryOptionsCard';
import {MandateApproval} from './MandateApproval';
import {MonitoringCard} from './MonitoringCard';
import {ProductPreviewUnavailableCard} from './ProductPreviewUnavailableCard';
import {ReceiptCard} from './ReceiptCard';
import {ToolCallCard} from './ToolCallCard';
import {UserActionCard} from './UserActionCard';

const trustedSurface = new TrustedSurface();

const getArtifactType = (artifactData: unknown): string | undefined => {
  if (
    artifactData &&
    typeof artifactData === 'object' &&
    'type' in artifactData
  ) {
    return (artifactData as {type: string}).type;
  }
  return undefined;
};

type MessageRendererChatState = Pick<
  ChatState,
  | 'handleMandateApprove'
  | 'handleMandateReject'
  | 'isMonitoring'
  | 'lastInventoryMatches'
  | 'lastInventoryOptions'
  | 'lastSelectedItemName'
  | 'pendingTaskId'
  | 'sendToAgent'
  | 'setLastSelectedItemName'
>;

export const MessageRenderer = ({
  msg,
  chatState,
}: {
  msg: ChatMessage;
  chatState: MessageRendererChatState;
}) => {
  const {
    lastInventoryOptions,
    pendingTaskId,
    setLastSelectedItemName,
    sendToAgent,
    lastSelectedItemName,
    lastInventoryMatches,
    handleMandateApprove,
    handleMandateReject,
    isMonitoring,
  } = chatState;

  const isUser = msg.role === 'user';
  const isSystem = msg.role === 'system';
  const artifactType = getArtifactType(msg.artifactData);

  // Skip rendering for internal state artifacts that have no accompanying text
  const hiddenArtifactTypes = [
    'mandates_signed',
    'mandates_created',
    'mandate_presented',
    'mandate_chains_fetched',
  ];
  if (artifactType && hiddenArtifactTypes.includes(artifactType) && !msg.text) {
    return null;
  }

  // 1. User Action
  if (msg.role === 'user_action') {
    return (
      <UserActionCard
        label={msg.userActionLabel ?? 'Action'}
        sublabel={msg.userActionSublabel}
      />
    );
  }

  // 2. Tool Call
  const toolCall =
    artifactType === 'tool_call'
      ? (msg.artifactData as ToolCallArtifact)
      : undefined;

  if (toolCall) {
    return (
      <ToolCallCard
        call={{
          type: 'tool_call',
          tool: toolCall.tool,
          server: toolCall.server,
          message: toolCall.message,
        }}
      />
    );
  }

  // 2.5. Product Preview Unavailable (before inventory options)
  if (artifactType === 'product_preview_unavailable') {
    const preview = msg.artifactData as ProductPreviewUnavailable;
    const proseText = msg.text
      ? removeArtifactJsonFromText(msg.text, 'product_preview_unavailable')
      : undefined;
    return (
      <div className="agent-composite-msg">
        {proseText?.trim() && <AgentProse text={proseText} />}
        <ProductPreviewUnavailableCard preview={preview} />
      </div>
    );
  }

  // 3. Inventory Options
  if (artifactType === 'inventory_options') {
    const inv = msg.artifactData as InventoryOptionsArtifact;
    const opts = lastInventoryOptions ?? inv;
    const price_cap = opts?.price_cap;
    const qty = opts?.qty;

    const handleSelect =
      price_cap != null && qty != null && pendingTaskId
        ? (itemId: string) => {
            setLastSelectedItemName(
              inv.matches.find((m) => m.item_id === itemId)?.name,
            );
            sendToAgent(
              {
                type: 'item_selected',
                item_id: itemId,
                price_cap: price_cap,
                qty: qty,
              },
              pendingTaskId,
            );
          }
        : undefined;

    return <InventoryOptionsCard inventory={inv} onSelect={handleSelect} />;
  }

  // 4. Mandate Request
  const mandate =
    artifactType === 'mandate_request'
      ? (msg.artifactData as MandateRequest)
      : msg.text && msg.role === 'agent'
        ? extractMandateFromText(msg.text)
        : undefined;

  if (mandate) {
    const currentPrice =
      mandate.current_price ??
      (msg.text ? extractCurrentPriceFromText(msg.text) : undefined);
    const mandateWithName = {
      ...mandate,
      item_name: mandate.item_name ?? lastSelectedItemName,
      matches: mandate.matches ?? lastInventoryMatches,
    };
    const proseText = msg.text
      ? removeArtifactJsonFromText(msg.text, 'mandate_request')
      : undefined;

    return (
      <div className="agent-composite-msg">
        {proseText?.trim() && <AgentProse text={proseText} />}
        <MandateApproval
          mandate={mandateWithName}
          trustedSurface={trustedSurface}
          onApprove={handleMandateApprove}
          onReject={handleMandateReject}
          itemName={lastSelectedItemName}
          currentPrice={currentPrice}
        />
      </div>
    );
  }

  // 5. Error or Monitoring
  const error =
    artifactType === 'error'
      ? (msg.artifactData as ErrorArtifact)
      : msg.text && msg.role === 'agent'
        ? extractErrorFromText(msg.text)
        : undefined;

  const monitoring =
    artifactType === 'monitoring'
      ? (msg.artifactData as MonitoringStatus)
      : msg.text && msg.role === 'agent'
        ? extractMonitoringFromText(msg.text)
        : undefined;

  if (error || monitoring) {
    const handleCheckNow =
      !error && monitoring
        ? () => {
            sendToAgent(
              {
                type: 'check_product_now',
                item_id: monitoring.item_id,
                price_cap: monitoring.price_cap,
                qty: monitoring.qty ?? 1,
                open_checkout_mandate: monitoring.open_checkout_mandate,
                open_payment_mandate: monitoring.open_payment_mandate,
                message: 'Check product now',
                source: 'manual',
              },
              pendingTaskId,
            );
          }
        : undefined;

    return (
      <div className="error-monitoring-wrapper">
        {monitoring && (
          <MonitoringCard
            status={monitoring}
            onCheckNow={handleCheckNow}
            triggerCurl={`curl -X POST "${MERCHANT_TRIGGER_URL}/trigger-price-drop?item_id=${encodeURIComponent(monitoring.item_id)}&price=${monitoring.price_cap - 1}&stock=10"`}
            pollIntervalSeconds={!error && isMonitoring ? 15 : undefined}
            itemName={lastSelectedItemName}
          />
        )}
        {error && <ErrorCard error={error} />}
      </div>
    );
  }

  // 6. Purchase Complete
  if (artifactType === 'purchase_complete') {
    return (
      <ReceiptCard
        purchase={msg.artifactData as PurchaseComplete}
        itemName={lastSelectedItemName}
      />
    );
  }

  // 7. Standard Text Message Fallback
  return (
    <div className={`message-wrapper ${isUser ? 'user' : 'agent'}`}>
      <div
        className={`message-content ${isUser ? 'user' : isSystem ? 'system' : 'agent'}`}>
        {isUser ? (
          msg.text
        ) : (
          <ReactMarkdown
            components={{
              p: ({children}) => <p>{children}</p>,
              strong: ({children}) => <strong>{children}</strong>,
              ol: ({children}) => <ol>{children}</ol>,
              ul: ({children}) => <ul>{children}</ul>,
              li: ({children}) => <li>{children}</li>,
              code: ({children}) => <code>{children}</code>,
            }}>
            {msg.text ?? ''}
          </ReactMarkdown>
        )}
      </div>
    </div>
  );
};
