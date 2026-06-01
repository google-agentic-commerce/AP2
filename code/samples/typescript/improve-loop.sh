#!/usr/bin/env bash
#
# Autonomous improve + test loop for the Verifiable Intent TS integration.
#
# Each iteration runs Claude Code headless against improve-loop.prompt.md, which
# completes ONE backlog item, verifies it (typecheck + lint + unit tests), and
# commits it. The loop stops when all gates are green AND BACKLOG.md has no
# unchecked items, or after MAX_ITERS iterations.
#
# Guardrails: --bare (no hooks/plugins), acceptEdits, a scoped tool allowlist
# (only npm/npx/git/node + file tools — no network), and a git commit per
# iteration so any step is one `git reset` away from rollback. e2e tests are
# never run here (they need a Gemini key + live servers).
#
# Usage:  ./improve-loop.sh [max_iterations]      # default 12
#         LOOP_MODEL=opus ./improve-loop.sh 5     # override model
#
set -uo pipefail
cd "$(dirname "$0")"

MAX_ITERS="${1:-12}"
MODEL="${LOOP_MODEL:-sonnet}"
PROMPT_FILE="improve-loop.prompt.md"
ALLOWED="Read,Edit,Write,Glob,Grep,Bash(npm:*),Bash(npx:*),Bash(git:*),Bash(node:*)"

if [ ! -f "$PROMPT_FILE" ]; then
  echo "error: $PROMPT_FILE not found (run from code/samples/typescript)" >&2
  exit 1
fi

gates_green() {
  npx tsc --noEmit >/dev/null 2>&1 \
    && npm run lint >/dev/null 2>&1 \
    && npx vitest run test/unit >/dev/null 2>&1
}

# No unchecked "- [ ]" items remain in the backlog.
backlog_done() {
  ! grep -qE '^[[:space:]]*-[[:space:]]\[ \]' BACKLOG.md
}

for i in $(seq 1 "$MAX_ITERS"); do
  echo "──────────────────────────────────────────────────────────"
  echo "  iteration $i / $MAX_ITERS"
  echo "──────────────────────────────────────────────────────────"

  claude --bare -p "$(cat "$PROMPT_FILE")" \
    --model "$MODEL" \
    --permission-mode acceptEdits \
    --allowedTools "$ALLOWED"

  if gates_green && backlog_done; then
    echo "✅ all gates green and BACKLOG.md fully checked — stopping."
    break
  fi
  echo "… not done yet; continuing to next iteration."
done

echo ""
echo "Loop finished. Recent commits:"
git --no-pager log --oneline -"$MAX_ITERS" 2>/dev/null || true
