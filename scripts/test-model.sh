#!/usr/bin/env bash
# test-model.sh — verify a model fits cheap-llm-router's needs
#
# Reasoning models (deepseek-v4-pro, kimi-k2.6, glm-5.1, etc.) silently
# burn the cap on hidden thinking tokens and return empty visible output.
# Loosely-tuned models exceed the cap by 3-8×, blowing your token budget.
# Some models drop files on multi-file reads instead of distributing the
# cap across them. This script catches all three failure modes before you
# commit a model as your default.
#
# Usage:
#   scripts/test-model.sh <model-id>
#
# Examples:
#   scripts/test-model.sh deepseek/deepseek-chat-v3-0324
#   scripts/test-model.sh google/gemma-4-31b-it
#   scripts/test-model.sh openai/gpt-5.4-mini
#
# What it does:
#   1. Backs up your current ~/.config/cheap-llm/config.yaml
#   2. Swaps in the requested model
#   3. Runs a single-file test (cap respect, basic speed)
#   4. Runs a 4-file test (coverage, distributed cap, larger input)
#   5. Prints a verdict: PASS / NOT RECOMMENDED with reasons
#   6. Restores your original config (always — even on failure / Ctrl-C)
#
# Cost: ~$0.005-$0.02 per run (one input is ~80k chars, two outputs ~3k tokens).

set -euo pipefail

MODEL="${1:-}"
if [ -z "$MODEL" ]; then
  cat <<EOF
Usage: $0 <model-id>

Examples:
  $0 deepseek/deepseek-chat-v3-0324
  $0 google/gemma-4-31b-it
  $0 openai/gpt-5.4-mini

The model id is whatever you'd put under provider.model in
~/.config/cheap-llm/config.yaml. For OpenRouter it usually looks like
"<provider>/<model-name>". Browse https://openrouter.ai/models for the list.
EOF
  exit 1
fi

# ── Pre-flight ─────────────────────────────────────────────────────────────
command -v cheap >/dev/null 2>&1 || {
  echo "❌ 'cheap' not found on PATH. Install first: pipx install git+https://github.com/Lexus2016/cheap-llm-router.git"
  exit 1
}

cheap config check >/dev/null 2>&1 || {
  echo "❌ 'cheap config check' failed — set OPENROUTER_API_KEY (or api_key in config.yaml) first."
  cheap config check 2>&1 | sed 's/^/   /'
  exit 1
}

CFG="$(cheap config path)"
[ -f "$CFG" ] || { echo "❌ config not found at $CFG"; exit 1; }

REPO="$(cd "$(dirname "$0")/.." && pwd)"
F1="$REPO/src/cheap_llm/client.py"
F2="$REPO/src/cheap_llm/config.py"
F3="$REPO/src/cheap_llm/cli.py"
F4="$REPO/src/cheap_llm/__init__.py"
for f in "$F1" "$F2" "$F3" "$F4"; do
  [ -f "$f" ] || { echo "❌ missing test fixture: $f (run from a checkout of cheap-llm-router)"; exit 1; }
done

# ── Backup + swap ──────────────────────────────────────────────────────────
BACKUP="$CFG.test-model.bak.$$"
cp "$CFG" "$BACKUP"
trap 'mv -f "$BACKUP" "$CFG"; echo; echo "(config restored)"' EXIT INT TERM

CAP=$(grep -E "^\s*max_summary_tokens:" "$BACKUP" | head -1 | awk '{print $2}')
CAP=${CAP:-1500}

python3 -c "
import re
p = '$CFG'
c = open(p).read()
c = re.sub(r'^  model: .*\$', '  model: $MODEL', c, flags=re.M)
open(p, 'w').write(c)
"

echo "▶ Testing model: $MODEL"
echo "  cap: $CAP tokens"
echo "  config (backed up to $BACKUP)"
echo

# ── Test 1: single file ───────────────────────────────────────────────────
echo "── Test 1/2: single file (cap respect, basic latency)"
OUT1=$(mktemp)
START=$(date +%s)
if ! timeout 120 cheap read "$F1" -q "What does this module do? Be brief." >"$OUT1" 2>&1; then
  RC=$?
  DUR=$(($(date +%s)-START))
  echo "  ❌ FAIL — exit=$RC (duration=${DUR}s — likely timeout)"
  rm -f "$OUT1"
  exit 2
fi
DUR1=$(($(date +%s)-START))
TOK1=$(tail -1 "$OUT1" | grep -oE 'output_tokens=[0-9]+' | cut -d= -f2)
TOK1=${TOK1:-0}
BYTES1=$(wc -c < "$OUT1" | tr -d ' ')
echo "  time=${DUR1}s  tokens=$TOK1  bytes=$BYTES1"

# ── Test 2: four files ────────────────────────────────────────────────────
echo "── Test 2/2: 4 files (coverage, distributed cap, larger input)"
OUT2=$(mktemp)
START=$(date +%s)
if ! timeout 180 cheap read "$F1" "$F2" "$F3" "$F4" -q "Describe each file's role. Cite line numbers for public symbols." >"$OUT2" 2>&1; then
  RC=$?
  DUR=$(($(date +%s)-START))
  echo "  ❌ FAIL — exit=$RC (duration=${DUR}s — likely timeout)"
  rm -f "$OUT1" "$OUT2"
  exit 2
fi
DUR2=$(($(date +%s)-START))
TOK2=$(tail -1 "$OUT2" | grep -oE 'output_tokens=[0-9]+' | cut -d= -f2)
TOK2=${TOK2:-0}
BYTES2=$(wc -c < "$OUT2" | tr -d ' ')
COV=0
for fname in client.py config.py cli.py __init__.py; do
  if grep -q "$fname" "$OUT2"; then COV=$((COV+1)); fi
done
echo "  time=${DUR2}s  tokens=$TOK2  bytes=$BYTES2  coverage=$COV/4"

# ── Verdict ───────────────────────────────────────────────────────────────
echo
echo "── Verdict"

CAP_HARD_LIMIT=$((CAP * 12 / 10))   # >20% over cap = broken
PASS=true
REASONS=()

# Empty visible output usually means a reasoning model burned the cap on hidden thinking
if [ "$BYTES2" -lt 1500 ]; then
  PASS=false
  REASONS+=("Output suspiciously short ($BYTES2 bytes for 4 files). Likely a reasoning model that consumed the cap on hidden thinking tokens — visible output is empty.")
fi

# Cap broken means the provider ignored max_tokens / max_completion_tokens
if [ "$TOK2" -gt "$CAP_HARD_LIMIT" ]; then
  PASS=false
  REASONS+=("Cap broken: $TOK2 output tokens vs cap $CAP. Model ignores both max_tokens and max_completion_tokens.")
fi

# Coverage drop means model focused on first files instead of distributing
if [ "$COV" -lt 3 ]; then
  PASS=false
  REASONS+=("Poor file coverage ($COV/4). Model went deep on early files and dropped the rest. Bad for multi-file reads.")
fi

# Slow but acceptable — warn, don't fail
SLOW_WARN=""
if [ "$DUR2" -gt 120 ]; then
  SLOW_WARN="(slow: ${DUR2}s for 4 files — consider faster model for interactive use)"
fi

if $PASS; then
  echo "  ✅ PASS — $MODEL is suitable as a cheap-llm-router default."
  [ -n "$SLOW_WARN" ] && echo "     $SLOW_WARN"
  echo
  echo "  To use permanently, edit $(cheap config path) and set:"
  echo "    provider.model: $MODEL"
else
  echo "  ❌ NOT RECOMMENDED — $MODEL is unsuitable:"
  for r in "${REASONS[@]}"; do echo "     • $r"; done
  [ -n "$SLOW_WARN" ] && echo "     • $SLOW_WARN"
  exit 3
fi

rm -f "$OUT1" "$OUT2"
