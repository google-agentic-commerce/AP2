/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * ADK web entry: a dedicated agents directory so `adk web src/web-agents`
 * lists the app under the folder name ("shopping-agent") instead of the
 * generic "agent" you get when pointing adk web directly at an agent folder.
 * Pointing adk web at src/roles is not viable — its heterogeneous siblings
 * (the *-mcp stdio servers and shopping-agent-v2) collide in ADK's loader.
 */

export { rootAgent, shoppingAgent } from '../../roles/shopping-agent/agent.js';
