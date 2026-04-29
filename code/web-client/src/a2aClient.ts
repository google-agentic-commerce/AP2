// A2A JSON-RPC client. Mirrors the pattern from UCP a2a/chat-client.
import type {A2AArtifact, A2ATaskStatus, OutgoingDataPayload} from './types';

const LOCAL_STORAGE_SESSION_KEY = 'a2a_session_id';

// ==========================================
// INTERFACES & TYPES
// ==========================================

interface StreamStatusResult {
  type: 'status';
  status: A2ATaskStatus;
}

interface StreamArtifactResult {
  type: 'artifact';
  artifact: A2AArtifact;
}

type StreamYieldResult = StreamStatusResult|StreamArtifactResult;


interface JsonRpcResponse {
  result?: {
    status?: A2ATaskStatus;
    artifact?: A2AArtifact;
    artifacts?: A2AArtifact[];
    lastChunk?: boolean;
  };
}

// ==========================================
// CLASS IMPLEMENTATION
// ==========================================

export class A2AClient {
  private baseUrl: string;
  private sessionId: string;

  constructor(agentUrl: string) {
    this.baseUrl = agentUrl.replace(/\/$/, '');
    this.sessionId = this.initializeSessionId();
  }

  /**
   * Safely retrieves or generates a persistent session ID.
   */
  private initializeSessionId(): string {
    try {
      if (typeof localStorage === 'undefined') {
        return crypto.randomUUID();
      }

      const stored = localStorage.getItem(LOCAL_STORAGE_SESSION_KEY);
      if (stored && stored.length > 0) {
        return stored;
      }

      const newId = crypto.randomUUID();
      localStorage.setItem(LOCAL_STORAGE_SESSION_KEY, newId);
      return newId;
    } catch {
      return crypto.randomUUID();
    }
  }

  /**
   * Generates a truncated summary of the message for debugging purposes.
   */
  private getMessageSummary(message: string | OutgoingDataPayload): string {
    if (typeof message === 'string') {
      return message.slice(0, 80);
    }

    if (typeof message === 'object' && message !== null) {
      const msgObj = message as unknown as Record<string, unknown>;
      return `{type: ${msgObj.type}, item_id: ${msgObj.item_id ?? '?'}, price_cap: ${msgObj.price_cap ?? '?'}}`;
    }

    return JSON.stringify(message).slice(0, 80);
  }

  /**
   * Send a message and receive a streaming SSE response.
   * Uses A2A JSON-RPC method "message/stream" - POST to rpc_url (baseUrl).
   */
  async *
      sendMessage(message: string | OutgoingDataPayload, taskId?: string):
          AsyncGenerator<StreamYieldResult> {
    const id = taskId ?? crypto.randomUUID();
    const parts = typeof message === 'string' ?
        [{kind: 'text' as const, text: message}] :
        [{kind: 'data' as const, data: message, mimeType: 'application/json'}];

    const jsonRpcRequest = {
      jsonrpc: '2.0',
      id,
      method: 'message/stream',
      params: {
        message: {
          role: 'user' as const,
          parts,
          messageId: crypto.randomUUID(),
        },
        configuration: {historyLength: 20},
        metadata: {sessionId: this.sessionId},
      },
    };

    console.debug('[A2A] sendMessage', {
      taskId: id,
      sessionId: this.sessionId,
      message: this.getMessageSummary(message),
    });

    const response = await fetch(this.baseUrl, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(jsonRpcRequest),
    });

    if (!response.ok || !response.body) {
      throw new Error(`A2A error: ${response.status} ${response.statusText}`);
    }

    // Delegate stream processing to a dedicated private generator
    yield* this.processStream(response.body.getReader());
  }

  /**
   * Parses the Server-Sent Events (SSE) stream and yields mapped results.
   */
  private async *
      processStream(reader: ReadableStreamDefaultReader<Uint8Array>):
          AsyncGenerator<StreamYieldResult> {
    const decoder = new TextDecoder();
    let buffer = '';
    const DATA_PREFIX = 'data: ';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        if (!line.startsWith(DATA_PREFIX)) continue;

        try {
          // Slice using the known prefix length rather than a magic number
          const jsonString = line.slice(DATA_PREFIX.length);
          const jsonRpc = JSON.parse(jsonString) as JsonRpcResponse;
          const result = jsonRpc.result;

          if (!result) continue;

          if (result.status) {
            yield {type: 'status', status: result.status};
          }

          if (result.artifact) {
            yield {
              type: 'artifact',
              artifact: {
                index: 0,
                parts: result.artifact.parts ?? [],
                lastChunk: result.lastChunk,
              },
            };
          }

          for (const artifact of result.artifacts ?? []) {
            yield {type: 'artifact', artifact};
          }
        } catch {
          // skip malformed SSE lines
        }
      }
    }
  }
}
