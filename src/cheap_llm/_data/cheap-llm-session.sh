#!/bin/bash
# cheap-llm-session.sh — Claude Code SessionStart hook.
#
# Lets `cheap extract` (without --session-id) find the current
# session's transcript deterministically, instead of falling back to
# the cwd-slug newest-mtime heuristic.
#
# How it works:
#   - Claude Code runs this script on SessionStart and pipes a JSON
#     payload on stdin. The payload contains `transcript_path` —
#     the absolute path to the JSONL of the session that just started.
#   - $PPID inside this script is the PID of the parent `claude`
#     process. The same PID will be visible to any Bash command Claude
#     later runs (Bash tool calls inherit it as their $PPID).
#   - We write the transcript path into
#     ${XDG_CACHE_HOME:-$HOME/.cache}/cheap-llm/sessions/<PPID>.txt .
#   - When `cheap extract` runs from inside the Bash tool, it reads
#     that file by its own $PPID and uses the path directly.
#
# Failure mode: this script must NEVER block Claude startup. Any
# error (jq missing, write fails, JSON malformed) → exit 0 silently.
# `cheap extract` then falls back to its built-in resolver heuristic
# the same way it does without the hook.

set -u  # NOT -e: we tolerate failures by design.

CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/cheap-llm/sessions"

# Read the JSON payload from stdin. We don't depend on jq because
# Claude Code users may not have it; a tiny grep extracts the field.
PAYLOAD=$(cat 2>/dev/null) || exit 0

# Extract the value of "transcript_path" from a JSON object. Tolerant
# of whitespace and surrounding fields. If `jq` is on PATH we prefer
# it (handles escapes properly); otherwise fall back to a regex.
TRANSCRIPT_PATH=""
if command -v jq >/dev/null 2>&1; then
    TRANSCRIPT_PATH=$(printf '%s' "$PAYLOAD" | jq -r '.transcript_path // empty' 2>/dev/null)
fi
if [ -z "$TRANSCRIPT_PATH" ]; then
    TRANSCRIPT_PATH=$(printf '%s' "$PAYLOAD" \
        | grep -oE '"transcript_path"[[:space:]]*:[[:space:]]*"[^"]*"' \
        | head -1 \
        | sed -E 's/.*"transcript_path"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/')
fi

[ -z "$TRANSCRIPT_PATH" ] && exit 0

# Ensure cache dir exists; tolerate failure.
mkdir -p "$CACHE_DIR" 2>/dev/null || exit 0

# Write the path into a per-PPID file. $PPID == claude PID.
printf '%s\n' "$TRANSCRIPT_PATH" > "$CACHE_DIR/$PPID.txt" 2>/dev/null || true

exit 0
