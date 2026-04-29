import {useEffect, useRef, useState} from 'react';
import './App.scss';
import {MandateViewer} from './components/MandateViewer';
import {MessageRenderer} from './components/MessageRenderer';
import {TypingIndicator} from './components/TypingIndicator';
import {DEFAULT_CHAT_STARTER_MESSAGE} from './config';
import {type ChatState, useChat} from './hooks/useChat';

// ==========================================
// SUB-COMPONENTS
// ==========================================

const AppHeader = ({usedServers}: {usedServers: Set<string>}) => {
  const servers = [
    {
      label: 'Shopping Agent',
      key: 'Shopping Agent',
      className: 'server-shopping',
    },
    {label: 'Merchant MCP', key: 'Merchant MCP', className: 'server-merchant'},
    {
      label: 'Credential Provider MCP',
      key: 'Credential Provider MCP',
      className: 'server-credential',
    },
  ];

  const flow = (import.meta as {env?: {VITE_FLOW?: string}}).env?.VITE_FLOW;

  return (
    <div className="app-header">
      <div className="logo-container">
        <span>🛒</span>
      </div>
      <div className="title-container">
        <div className="title">
          Delegated Shopper
          {flow === 'x402' && <span className="flow-badge x402">x402</span>}
          {flow === 'card' && <span className="flow-badge card">Card</span>}
        </div>
        <div className="subtitle">
          A2A · Human-not-present · Merchant MCP · Credential Provider MCP
        </div>
      </div>
      <div className="server-badges">
        {servers.map((b) => (
          <div
            key={b.key}
            className={`server-badge ${usedServers.has(b.key) ? 'active' : ''} ${b.className}`}>
            <div className="dot" />
            <span className="label">{b.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

type TabKey = 'chat' | 'mandates';

const TabBar = ({
  activeTab,
  onChange,
  mandateCount,
}: {
  activeTab: TabKey;
  onChange: (t: TabKey) => void;
  mandateCount: number;
}) => (
  <div className="tab-bar">
    <button
      type="button"
      className={`tab ${activeTab === 'chat' ? 'active' : ''}`}
      onClick={() => onChange('chat')}>
      Chat
    </button>
    <button
      type="button"
      className={`tab ${activeTab === 'mandates' ? 'active' : ''}`}
      onClick={() => onChange('mandates')}>
      Mandates
      {mandateCount > 0 && <span className="tab-count">{mandateCount}</span>}
    </button>
  </div>
);

const EmptyChatState = () => (
  <div className="empty-state">
    <div className="icon">🛒</div>
    <div className="title">Delegated Shopper</div>
    <div className="subtitle">
      Full flow: product preview → mandate signing → availability monitoring →
      autonomous purchase
      <br />
      via Merchant MCP + Credential Provider MCP
    </div>
    <p className="suggestion">
      Try:{' '}
      <em>
        &quot;When is the SuperShoe limited edition Gold sneaker drop? I need size 9
        women&apos;s.&quot;
      </em>
    </p>
    <p className="suggestion-enter-hint">
      or just press <kbd>Enter</kbd> to start
    </p>
  </div>
);

type ChatInputProps = Pick<
  ChatState,
  'handleSend' | 'input' | 'loading' | 'setInput'
>;

const ChatInput = ({input, setInput, handleSend, loading}: ChatInputProps) => (
  <div className="input-area">
    <input
      value={input}
      onChange={(e) => setInput(e.target.value)}
      onKeyDown={(e) =>
        e.key === 'Enter' &&
        !loading &&
        handleSend({fallbackIfEmpty: DEFAULT_CHAT_STARTER_MESSAGE})
      }
      placeholder="e.g. When is the SuperShoe limited edition Gold sneaker drop? I need size 9 women's."
      disabled={loading}
      className="chat-input"
    />
    <button
      type="button"
      onClick={() =>
        handleSend({fallbackIfEmpty: DEFAULT_CHAT_STARTER_MESSAGE})
      }
      disabled={loading}
      className="send-button">
      Send
    </button>
  </div>
);

// ==========================================
// MAIN APP COMPONENT
// ==========================================

export default function App() {
  const chatState: ChatState = useChat();
  const {messages} = chatState;
  const [activeTab, setActiveTab] = useState<TabKey>('chat');
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (activeTab === 'chat') {
      bottomRef.current?.scrollIntoView({behavior: 'smooth'});
    }
  }, [messages, activeTab]);

  return (
    <div className="app-container">
      <AppHeader usedServers={chatState.usedServers} />
      <TabBar
        activeTab={activeTab}
        onChange={setActiveTab}
        mandateCount={chatState.mandates.length}
      />

      {activeTab === 'chat' ? (
        <>
          <div className="messages-container">
            {chatState.messages.length > 0 ? (
              <div className="messages-list">
                {chatState.messages.map((msg) => (
                  <MessageRenderer
                    key={msg.id}
                    msg={msg}
                    chatState={chatState}
                  />
                ))}
                {chatState.loading && (
                  <div className="msg-agent">
                    <TypingIndicator />
                  </div>
                )}
              </div>
            ) : (
              <>
                <EmptyChatState />
                {chatState.loading && (
                  <div className="msg-agent">
                    <TypingIndicator />
                  </div>
                )}
              </>
            )}
            <div ref={bottomRef} />
          </div>

          <ChatInput
            input={chatState.input}
            setInput={chatState.setInput}
            handleSend={chatState.handleSend}
            loading={chatState.loading}
          />
        </>
      ) : (
        <div className="mandate-tab-container">
          <MandateViewer mandates={chatState.mandates} />
        </div>
      )}
    </div>
  );
}
