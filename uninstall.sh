#!/usr/bin/env bash
# uninstall.sh — automated uninstall of cheap-llm-router.
#
# Mirrors UNINSTALL.md. Refuses to run without --yes (or YES=1) to
# prevent accidental wipes. Safe to re-run after partial removal.
#
# What it touches (and only these):
#   ~/.claude/CLAUDE.md         (only the "## Cheap LLM delegation" section)
#   ~/.config/cheap-llm/        (whole directory)
#   pipx environment for cheap-llm-router
#
# What it does NOT touch:
#   - Your shell profile (you remove the OPENROUTER_API_KEY line yourself)
#   - The source tree at /Users/admin/_Projects/cheap-llm-router/
#     (delete manually with `rm -rf` if you want a complete wipe)

set -euo pipefail

say() { printf "\033[1;34m==>\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m!!\033[0m %s\n" "$*" >&2; }
ok() { printf "\033[1;32mok\033[0m %s\n" "$*"; }

CONFIRMED="no"
case "${1:-}" in
    -y|--yes) CONFIRMED="yes" ;;
esac
[ "${YES:-0}" = "1" ] && CONFIRMED="yes"

if [ "$CONFIRMED" != "yes" ]; then
    cat >&2 <<'EOF'
This will:
  1. Remove the "## Cheap LLM delegation" section from ~/.claude/CLAUDE.md
  2. Delete ~/.config/cheap-llm/
  3. Run `pipx uninstall cheap-llm-router`

It will NOT touch your shell profile or the source tree.

Re-run with --yes (or YES=1 ./uninstall.sh) to proceed.
EOF
    exit 1
fi

# -------- step 1: remove CLAUDE.md section ---------------------------------
claude_md="$HOME/.claude/CLAUDE.md"
if [ -f "$claude_md" ]; then
    say "Removing ## Cheap LLM delegation section from $claude_md (backup: ${claude_md}.bak)"
    cp "$claude_md" "${claude_md}.bak"
    python3 - "$claude_md" <<'PY'
import re, sys, pathlib
p = pathlib.Path(sys.argv[1])
text = p.read_text(encoding="utf-8")
m = re.search(r"^## Cheap LLM delegation\s*$", text, re.MULTILINE)
if not m:
    print("section not present — nothing to do")
    raise SystemExit(0)
start = m.start()
rest = text[m.end():]
nm = re.search(r"^##\s", rest, re.MULTILINE)
end = m.end() + nm.start() if nm else len(text)
prefix = text[:start].rstrip() + ("\n" if text[:start].strip() else "")
suffix = text[end:] if nm else ""
p.write_text(prefix + suffix, encoding="utf-8")
print("removed")
PY
    if grep -q "Cheap LLM delegation" "$claude_md"; then
        warn "Section may still be present — double-check $claude_md"
    else
        ok "section removed"
    fi
else
    say "No $claude_md — nothing to do for step 1"
fi

# -------- step 2: remove user config ---------------------------------------
cfg_dir="$HOME/.config/cheap-llm"
if [ -e "$cfg_dir" ]; then
    say "Removing $cfg_dir"
    rm -rf "$cfg_dir"
    ok "config dir gone"
else
    say "No $cfg_dir — nothing to do for step 2"
fi

# -------- step 3: pipx uninstall -------------------------------------------
if command -v pipx >/dev/null && pipx list 2>/dev/null | grep -q "cheap-llm-router"; then
    say "Running: pipx uninstall cheap-llm-router"
    pipx uninstall cheap-llm-router
    ok "pipx package removed"
elif command -v cheap >/dev/null; then
    warn "\`cheap\` is on PATH but not installed via pipx. Remove it manually:"
    warn "  which cheap → $(command -v cheap)"
    warn "  pip uninstall -y cheap-llm-router    # if installed via pip"
else
    say "cheap-llm-router not installed via pipx — nothing to do for step 3"
fi

# -------- step 4: env var reminder -----------------------------------------
if [ -n "${OPENROUTER_API_KEY:-}" ]; then
    cat >&2 <<'EOF'

OPENROUTER_API_KEY is still set in the current shell.

Manual cleanup:
  1. Edit your shell profile (~/.zshrc, ~/.bashrc, etc.) and delete the
     `export OPENROUTER_API_KEY=...` line you added during install.
  2. Open a new terminal (or `unset OPENROUTER_API_KEY` in this one).
  3. Optional but recommended: rotate / revoke the key in the OpenRouter
     dashboard so an old session can't reuse it.
EOF
fi

ok "uninstall complete"
echo
echo "If you also want to delete the source tree, run:"
echo "  rm -rf $(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
