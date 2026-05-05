#!/usr/bin/env bash
# install.sh — automated install of cheap-llm-router.
#
# Mirrors INSTALL.md. Idempotent — safe to re-run.
#
# Env knobs:
#   NO_CLAUDE_RULE=1   skip step 4 (do not modify ~/.claude/CLAUDE.md)
#   EDITABLE=1         use `pipx install --editable` (picks up source changes)

set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
say() { printf "\033[1;34m==>\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m!!\033[0m %s\n" "$*" >&2; }
die() { printf "\033[1;31mxx\033[0m %s\n" "$*" >&2; exit 1; }

# -------- step 0: prereqs --------------------------------------------------
say "Checking prerequisites"

command -v python3 >/dev/null \
    || die "python3 not found. Install Python 3.11+ first."

py_major=$(python3 -c 'import sys; print(sys.version_info[0])')
py_minor=$(python3 -c 'import sys; print(sys.version_info[1])')
if [ "$py_major" -lt 3 ] || { [ "$py_major" -eq 3 ] && [ "$py_minor" -lt 11 ]; }; then
    die "Python 3.11+ required (you have ${py_major}.${py_minor})."
fi

if ! command -v pipx >/dev/null; then
    die "pipx not found. Install with: brew install pipx (macOS) or python3 -m pip install --user pipx"
fi

# -------- step 1: install the CLI ------------------------------------------
say "Installing cheap-llm-router via pipx (source: $SOURCE_DIR)"

if [ "${EDITABLE:-0}" = "1" ]; then
    pipx install --force --editable "$SOURCE_DIR"
else
    pipx install --force "$SOURCE_DIR"
fi

command -v cheap >/dev/null \
    || die "Install seemed to succeed but \`cheap\` is not on PATH. Add ~/.local/bin to PATH."
say "cheap installed at: $(command -v cheap)"

# -------- step 2: provider env var -----------------------------------------
say "Checking provider API key"

if [ -z "${OPENROUTER_API_KEY:-}" ]; then
    warn "OPENROUTER_API_KEY is not set in the current shell."
    cat <<'EOF' >&2

Add this line to your shell profile (~/.zshrc, ~/.bashrc, etc.):

    export OPENROUTER_API_KEY="sk-or-v1-..."

then re-source it (or open a new terminal) and re-run this script —
the rest of the steps need that key to verify the install.

Skipping verification and Claude rule install for now.
EOF
    exit 0
fi

if cheap config check >/dev/null 2>&1; then
    say "API key visible to CLI: cheap config check → OK"
else
    die "OPENROUTER_API_KEY is set in this shell but cheap config check failed. Investigate."
fi

# -------- step 3: ensure default config exists -----------------------------
cfg_path=$(cheap config path)
say "Config: $cfg_path"

# -------- step 4: install CLAUDE.md rule -----------------------------------
if [ "${NO_CLAUDE_RULE:-0}" = "1" ]; then
    warn "NO_CLAUDE_RULE=1 set — skipping CLAUDE.md rule install."
else
    say "Installing CLAUDE.md delegation rule (idempotent)"
    cheap install-claude-rule
fi

# -------- step 5: smoke test -----------------------------------------------
say "Smoke test"
cheap --help >/dev/null
say "All set. Try: cheap read $SOURCE_DIR/tests/fixtures/sample_module/auth.py -q 'what does this do?'"
