import readline from "node:readline";
import { v4 as uuidv4 } from "uuid";

import type {
  MessageSendParams,
  TaskStatusUpdateEvent,
  TaskArtifactUpdateEvent,
  Message,
  Task,
  TaskState,
  FilePart,
  DataPart,
  AgentCard,
  Part,
} from "@a2a-js/sdk";
import { A2AClient } from "@a2a-js/sdk/client";
import { AGENTS } from "./agents/index.js";

// Custom error class to signal clean exit (no error, just stop execution)
class ExitSignal extends Error {
  constructor(public readonly code: number = 0) {
    super(code === 0 ? "Clean exit" : `Exit with code ${code}`);
    this.name = "ExitSignal";
  }
}

const colors = {
  reset: "\x1b[0m",
  bright: "\x1b[1m",
  dim: "\x1b[2m",
  red: "\x1b[31m",
  green: "\x1b[32m",
  yellow: "\x1b[33m",
  blue: "\x1b[34m",
  magenta: "\x1b[35m",
  cyan: "\x1b[36m",
  gray: "\x1b[90m",
} as const;

type ColorKey = keyof typeof colors;

function colorize(color: ColorKey, text: string): string {
  return `${colors[color]}${text}${colors.reset}`;
}

interface ClientState {
  currentTaskId?: string;
  currentContextId?: string;
  serverUrl: string;
  client?: A2AClient;
  agentName: string;
  lastStatusMessageHash?: string;
}

function initializeState(): ClientState {
  const serverUrl = process.argv[2] || AGENTS.SHOPPING_AGENT;

  if (process.argv[2] === "--help" || process.argv[2] === "-h") {
    console.log(colorize("bright", "A2A Terminal Client for AP2"));
    console.log("\nUsage: node dist/cli.js [agent-url]\n");
    console.log(colorize("cyan", "Available agents:"));
    Object.entries(AGENTS).forEach(([name, url]) => {
      console.log(`  ${colorize("green", name.padEnd(25))} ${url}`);
    });
    console.log("\nCommands:");
    console.log("  /new   - Start a new session (clear task and context)");
    console.log("  /exit  - Exit the client");
    throw new ExitSignal(0);
  }

  return {
    currentTaskId: undefined,
    currentContextId: undefined,
    serverUrl,
    client: undefined,
    agentName: "Agent",
  };
}

const state = initializeState();

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
  prompt: colorize("cyan", "You: "),
});

function printAgentEvent(
  event: TaskStatusUpdateEvent | TaskArtifactUpdateEvent,
  agentName: string
): void {
  const timestamp = new Date().toLocaleTimeString();
  const prefix = colorize("magenta", `\n${agentName} [${timestamp}]:`);

  if (event.kind === "status-update") {
    printStatusUpdate(event, prefix);
  } else if (event.kind === "artifact-update") {
    printArtifactUpdate(event, prefix);
  }
}

function printStatusUpdate(
  update: TaskStatusUpdateEvent,
  prefix: string
): void {
  const { state: taskState, message } = update.status;
  const { stateEmoji, stateColor } = getStateDisplay(taskState);

  console.log(
    `${prefix} ${stateEmoji} Status: ${colorize(stateColor, taskState)} ` +
      `(Task: ${update.taskId}, Context: ${update.contextId}) ` +
      `${update.final ? colorize("bright", "[FINAL]") : ""}`
  );

  if (message) {
    printMessageContent(message);
  }
}

function printArtifactUpdate(
  update: TaskArtifactUpdateEvent,
  prefix: string
): void {
  const { artifact, taskId, contextId } = update;
  console.log(
    `${prefix} 📄 Artifact: ${artifact.name || "(unnamed)"} ` +
      `(ID: ${artifact.artifactId}, Task: ${taskId}, Context: ${contextId})`
  );

  // Display artifact parts
  printParts(artifact.parts);
}

function getStateDisplay(state: TaskState): {
  stateEmoji: string;
  stateColor: ColorKey;
} {
  const displays: Record<
    TaskState,
    { stateEmoji: string; stateColor: ColorKey }
  > = {
    working: { stateEmoji: "⏳", stateColor: "blue" },
    "input-required": { stateEmoji: "🤔", stateColor: "yellow" },
    "auth-required": { stateEmoji: "🔒", stateColor: "magenta" },
    unknown: { stateEmoji: "ℹ️", stateColor: "dim" },
    completed: { stateEmoji: "✅", stateColor: "green" },
    canceled: { stateEmoji: "⏹️", stateColor: "gray" },
    failed: { stateEmoji: "❌", stateColor: "red" },
    submitted: { stateEmoji: "📤", stateColor: "cyan" },
    rejected: { stateEmoji: "🚫", stateColor: "red" },
  };

  return displays[state] || { stateEmoji: "ℹ️", stateColor: "dim" };
}

function printMessageContent(message: Message): void {
  printParts(message.parts);
}

function printParts(parts: Part[]): void {
  const textParts = parts.filter((p) => p.kind === "text");
  const isSimpleTextMessage = parts.length === 1 && textParts.length === 1;

  parts.forEach((part, index) => {
    if (part.kind === "text") {
      if (isSimpleTextMessage) {
        console.log(`  ${part.text}`);
      } else {
        const partPrefix = colorize("dim", `  [${index + 1}]`);
        console.log(`${partPrefix} ${part.text}`);
      }
    } else if (part.kind === "file") {
      const partPrefix = colorize("dim", `  [${index + 1}]`);
      printFilePart(part, partPrefix);
    } else if (part.kind === "data") {
      const partPrefix = colorize("dim", `  [${index + 1}]`);
      printDataPart(part, partPrefix);
    } else {
      const partPrefix = colorize("dim", `  [${index + 1}]`);
      console.log(
        `${partPrefix} ${colorize("yellow", "⚠️ Unsupported part:")}`,
        part
      );
    }
  });
}

function printFilePart(filePart: FilePart, prefix: string): void {
  const { file } = filePart;
  const source = "bytes" in file ? "Inline (bytes)" : file.uri;
  console.log(
    `${prefix} ${colorize("blue", "📄")} ` +
      `${file.name || "File"} (${file.mimeType || "unknown type"}) - ${source}`
  );
}

function printDataPart(dataPart: DataPart, prefix: string): void {
  const dataKeys = Object.keys(dataPart.data || {});
  if (dataKeys.length === 0) return;

  // Show a summary instead of full JSON dump
  console.log(
    `${prefix} ${colorize("yellow", "📊")} Data: {${dataKeys.join(", ")}}`
  );
}

async function initializeClient(state: ClientState): Promise<void> {
  console.log(colorize("dim", `Connecting to agent: ${state.serverUrl}`));

  try {
    state.client = await A2AClient.fromCardUrl(state.serverUrl);
    const card: AgentCard = await state.client.getAgentCard();
    state.agentName = card.name || "Agent";

    console.log(colorize("green", "✓ Connected to Agent:"));
    console.log(`  Name:        ${colorize("bright", state.agentName)}`);

    if (card.description) {
      console.log(`  Description: ${card.description}`);
    }

    console.log(`  Version:     ${card.version || "N/A"}`);

    if (card.capabilities?.streaming) {
      console.log(`  Streaming:   ${colorize("green", "✓ Supported")}`);
    } else {
      console.log(`  Streaming:   ${colorize("yellow", "⚠️ Not Supported")}`);
    }
  } catch (error: unknown) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error(colorize("red", "✗ Failed to connect to agent:"));
    console.error(colorize("red", `  ${errorMessage}`));

    const errorWithCause = error as { cause?: { code?: string } };
    if (errorWithCause.cause?.code === "ECONNREFUSED") {
      console.error(
        colorize(
          "yellow",
          "\n💡 Tip: Make sure the agent server is running at:"
        )
      );
      console.error(colorize("yellow", `     ${state.serverUrl}`));
    }

    throw error;
  }
}

function getStatusMessageHash(event: TaskStatusUpdateEvent): string {
  const msg = event.status.message;
  if (!msg) return "";
  const textParts = msg.parts
    .filter((p): p is { kind: "text"; text: string } => p.kind === "text")
    .map((p) => p.text)
    .join("");
  return `${event.taskId}:${event.status.state}:${textParts.substring(0, 200)}`;
}

function processStreamEvent(
  event: TaskStatusUpdateEvent | TaskArtifactUpdateEvent | Message | Task,
  state: ClientState
): void {
  const timestamp = new Date().toLocaleTimeString();
  const prefix = colorize("magenta", `\n${state.agentName} [${timestamp}]:`);

  if (event.kind === "status-update" || event.kind === "artifact-update") {
    if (event.kind === "status-update") {
      const hash = getStatusMessageHash(event);
      if (hash && hash === state.lastStatusMessageHash) {
        return;
      }
      state.lastStatusMessageHash = hash;
    }

    printAgentEvent(event, state.agentName);

    if (
      event.kind === "status-update" &&
      event.final &&
      event.status.state !== "input-required"
    ) {
      console.log(
        colorize(
          "yellow",
          `   Task ${event.taskId} is final. Clearing current task ID.`
        )
      );
      state.currentTaskId = undefined;
    }
  } else if (event.kind === "message") {
    const msg = event as Message;
    console.log(`${prefix} ${colorize("green", "✉️ Message Event:")}`);
    printMessageContent(msg);

    if (msg.taskId && msg.taskId !== state.currentTaskId) {
      console.log(colorize("dim", `   Task ID updated to ${msg.taskId}`));
      state.currentTaskId = msg.taskId;
    }
    if (msg.contextId && msg.contextId !== state.currentContextId) {
      console.log(colorize("dim", `   Context ID updated to ${msg.contextId}`));
      state.currentContextId = msg.contextId;
    }
  } else if (event.kind === "task") {
    const task = event as Task;
    console.log(
      `${prefix} ${colorize("blue", "ℹ️ Task Event:")} ` +
        `ID: ${task.id}, Context: ${task.contextId}, Status: ${task.status.state}`
    );

    if (task.id !== state.currentTaskId) {
      console.log(
        colorize(
          "dim",
          `   Task ID updated from ${state.currentTaskId || "N/A"} to ${
            task.id
          }`
        )
      );
      state.currentTaskId = task.id;
    }
    if (task.contextId && task.contextId !== state.currentContextId) {
      console.log(
        colorize(
          "dim",
          `   Context ID updated from ${state.currentContextId || "N/A"} to ${
            task.contextId
          }`
        )
      );
      state.currentContextId = task.contextId;
    }

    if (task.status.message) {
      console.log(colorize("gray", "   Task message:"));
      printMessageContent(task.status.message);
    }

    if (task.artifacts && task.artifacts.length > 0) {
      console.log(
        colorize(
          "gray",
          `   Task includes ${task.artifacts.length} artifact(s).`
        )
      );
    }
  } else {
    console.log(prefix, colorize("yellow", "⚠️ Unknown event type:"), event);
  }
}

async function sendMessageToAgent(
  input: string,
  state: ClientState
): Promise<void> {
  if (!state.client) {
    console.error(colorize("red", "Error: Client not initialized"));
    return;
  }

  const messagePayload: Message = {
    messageId: uuidv4(),
    kind: "message",
    role: "user",
    parts: [{ kind: "text", text: input }],
  };

  if (state.currentTaskId) {
    messagePayload.taskId = state.currentTaskId;
  }
  if (state.currentContextId) {
    messagePayload.contextId = state.currentContextId;
  }

  const params: MessageSendParams = {
    message: messagePayload,
  };

  try {
    console.log(colorize("dim", "→ Sending message..."));
    state.lastStatusMessageHash = undefined;
    const stream = state.client.sendMessageStream(params);

    for await (const event of stream) {
      processStreamEvent(event, state);
    }

    console.log(colorize("dim", "--- End of response stream ---\n"));
  } catch (error: unknown) {
    const timestamp = new Date().toLocaleTimeString();
    const prefix = colorize(
      "red",
      `\n${state.agentName} [${timestamp}] ERROR:`
    );

    const errorMessage = error instanceof Error ? error.message : String(error);
    const errorWithMeta = error as {
      code?: string;
      data?: unknown;
      stack?: string;
    };

    console.error(prefix, "Error communicating with agent:");
    console.error(colorize("red", `  ${errorMessage}`));

    if (errorWithMeta.code) {
      console.error(colorize("gray", `  Code: ${errorWithMeta.code}`));
    }
    if (errorWithMeta.data) {
      console.error(
        colorize("gray", `  Data: ${JSON.stringify(errorWithMeta.data)}`)
      );
    }
    if (!(errorWithMeta.code || errorWithMeta.data) && errorWithMeta.stack) {
      const stackLines = errorWithMeta.stack.split("\n").slice(1, 3).join("\n");
      console.error(colorize("gray", stackLines));
    }
  }
}

function handleNewCommand(state: ClientState): void {
  state.currentTaskId = undefined;
  state.currentContextId = undefined;
  console.log(
    colorize("bright", "✨ New session started. Task and Context IDs cleared.")
  );
}

async function handleUserInput(
  input: string,
  state: ClientState
): Promise<boolean> {
  const trimmedInput = input.trim();

  if (!trimmedInput) {
    return true; // Continue
  }

  // Handle commands
  if (trimmedInput.toLowerCase() === "/new") {
    handleNewCommand(state);
    return true;
  }

  if (trimmedInput.toLowerCase() === "/exit") {
    return false; // Exit
  }

  // Send message to agent
  await sendMessageToAgent(trimmedInput, state);
  return true;
}

async function main() {
  console.log(colorize("bright", "A2A Terminal Client for AP2"));
  console.log(colorize("dim", `Agent URL: ${state.serverUrl}`));
  console.log();

  try {
    await initializeClient(state);
  } catch {
    console.error(colorize("red", "\nFailed to initialize client. Exiting."));
    throw new ExitSignal(1);
  }

  console.log();
  console.log(
    colorize(
      "dim",
      "No active task or context initially. Use '/new' to start fresh or send a message."
    )
  );
  console.log(
    colorize(
      "green",
      "Enter messages, or use '/new' to start a new session. '/exit' to quit."
    )
  );
  console.log();

  rl.setPrompt(colorize("cyan", `${state.agentName} > You: `));
  rl.prompt();

  rl.on("line", async (line) => {
    const shouldContinue = await handleUserInput(line, state);

    if (!shouldContinue) {
      rl.close();
      return;
    }

    rl.setPrompt(colorize("cyan", `${state.agentName} > You: `));
    rl.prompt();
  });

  rl.on("close", () => {
    console.log(
      colorize("yellow", "\nExiting A2A Terminal Client. Goodbye! 👋")
    );
  });
}

main().catch((err) => {
  if (err instanceof ExitSignal) {
    // Clean exit requested - exit code is in err.code
    // For ExitSignal(0), this is normal termination (e.g., --help)
    if (err.code !== 0) {
      throw err; // Re-throw to signal error exit
    }
    return;
  }
  console.error(colorize("red", "Unhandled error in main:"), err);
  throw err;
});
