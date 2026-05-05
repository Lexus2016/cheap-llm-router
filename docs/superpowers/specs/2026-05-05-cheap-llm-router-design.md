# cheap-llm-router — Design (Phase 1 MVP)

- **Date:** 2026-05-05
- **Status:** Draft (awaiting user review)
- **Author:** designed in collaboration with the user
- **Decision authority:** user has final say; defaults committed below

## 1. Problem

Claude Code on a Pro/Max subscription burns the weekly limit primarily
on **reading raw files into context** (Kunal Bhardwaj, Medium, ~2025):
five-file `Read` ≈ 8 000 tokens of session context, README generation
costs more, while actual reasoning gets the leftovers.

The user has hit weekly limits mid-week and wants to:

1. Reduce session-context burn from large file reads (the **session ceiling** problem).
2. Eventually reduce weekly-token spend overall (the **weekly ceiling** problem).

Constraint: solution must not degrade output quality on tasks where
quality matters (debugging, architecture, security, cross-file refactor).

## 2. Goal & Non-goals

### Goal (Phase 1)

Ship a single CLI command — `cheap read` — that lets Claude Code
delegate **read-for-context** operations (multiple files, summary only)
to a cheap OpenAI-compatible model (Kimi, DeepSeek, Gemini Flash, etc.)
via OpenRouter or any compatible provider.

Acceptance: when Claude Code uses `cheap read` instead of native `Read`
on a 5-file context-summary task, session token usage on that step
drops by ≥10×, and the summary is factually accurate enough that Claude
does not need to re-read the originals.

### Non-goals (Phase 1)

- No HTTP proxy / `ANTHROPIC_BASE_URL` interception. Phase 3 only if
  warranted by usage data.
- No `cheap draft` / `cheap extract`. Phase 2 only if Phase 1 leaves
  meaningful pain unaddressed.
- No automatic classifier deciding "delegate or not" — Claude decides,
  guided by an explicit rule in `~/.claude/CLAUDE.md`.
- No multi-provider failover. Single provider per config; switch by
  editing config.
- No streaming output. Summary is short; one-shot reply is fine.

## 3. Why Phase 1 only

The user's strongest pain matches **session ceiling**, which `cheap
read` addresses directly. The **weekly ceiling** fix (proxy) is
materially harder (transparent SSE forwarding, OAuth-token sourcing
from Keychain, ToS gray area) and may become unnecessary if Phase 1
already restores comfortable headroom. We measure first, expand if
needed.

Phase boundaries:

| Phase | Trigger to start | Scope |
|-------|------------------|-------|
| 1 (now) | Decision made | `cheap read` CLI + CLAUDE.md rule |
| 2 | After ≥1 week using Phase 1, if `draft`/`extract` patterns prove painful in real use | `cheap draft`, `cheap extract` |
| 3 | After Phase 1+2, if weekly-limit pressure persists | Node.js transparent proxy with Anthropic passthrough for `think` |

## 4. Architecture

### 4.1 Component diagram (Phase 1 scope only)

```
┌─────────────────────────────────────────────┐
│ Claude Code (subscription, native)          │
│                                             │
│   [Bash tool] ──► cheap read f1 f2 ... "Q"  │
│                          │                  │
└──────────────────────────┼──────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────┐
        │ cheap_llm.commands.read           │
        │  1. read & concat files           │
        │  2. build summary prompt          │
        │  3. call provider via openai SDK  │
        │  4. print summary to stdout       │
        └──────────────┬───────────────────┘
                       │
                       ▼
       ┌────────────────────────────────────┐
       │ Configurable provider              │
       │ (OpenRouter → Kimi/DeepSeek/Gemini)│
       └────────────────────────────────────┘
```

### 4.2 Repo layout

```
/Users/admin/_Projects/cheap-llm-router/
├── README.md
├── pyproject.toml                # pipx-installable, Python 3.11+
├── src/cheap_llm/
│   ├── __init__.py
│   ├── __main__.py               # `python -m cheap_llm`
│   ├── cli.py                    # Typer dispatcher; registers subcommands
│   ├── config.py                 # Loads ~/.config/cheap-llm/config.yaml
│   ├── client.py                 # Thin wrapper over openai SDK with base_url override
│   └── commands/
│       ├── __init__.py
│       └── read.py               # `cheap read` implementation
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_read_unit.py         # mocked OpenAI client
│   └── test_read_integration.py  # real OpenRouter call, gated by env var
└── docs/
    ├── claude-md-snippet.md      # snippet to paste into ~/.claude/CLAUDE.md
    └── superpowers/specs/
        └── 2026-05-05-cheap-llm-router-design.md   # this file
```

### 4.3 Configuration

File: `~/.config/cheap-llm/config.yaml` (XDG standard).

```yaml
provider:
  base_url: https://openrouter.ai/api/v1
  api_key_env: OPENROUTER_API_KEY      # CLI fails fast if env var unset
  model: moonshotai/kimi-k2            # any OpenAI-compatible model id
  temperature: 0.2
  request_timeout_seconds: 60

read:
  max_summary_tokens: 600              # target output size
  max_input_chars: 400000              # safety cap; refuse oversized concat
  prompt_template: |
    You are a code summarizer. Read the files below and produce a
    factual summary focused on: public API, key data flow, important
    invariants, gotchas. Skip boilerplate. Aim for ~{max_summary_tokens}
    tokens. Use markdown headings per file.

    User question (focus the summary on this if present):
    {question}

    Files:
    {files_block}
```

The CLI auto-creates this file on first run with the template above and
prints the path so the user can edit.

### 4.4 CLI surface

```bash
cheap --help
cheap read FILE [FILE...] [QUESTION]
cheap config path             # print resolved config path
cheap config show             # print resolved (env-substituted) config
```

`cheap read` semantics:

- All positional args ending in a path that exists are treated as files.
- The remaining trailing arg, if any, is the question.
- Files are read as UTF-8; binary files cause a clear error, not a crash.
- Files are concatenated with a `--- FILE: <path> ---` header per file.
- If concatenation exceeds `max_input_chars`, CLI exits with a clear
  error suggesting the user pass fewer files or raise the cap.
- Output: markdown summary on stdout. Errors and metadata on stderr.

### 4.5 CLAUDE.md snippet

Added to `~/.claude/CLAUDE.md` (v8.0) as a new top-level section, kept
short to fit the file's compact style. The exact text lives in
`docs/claude-md-snippet.md`; substantive content:

- Heading: `## Cheap LLM delegation (cheap CLI)`.
- Trigger: when Claude would `Read` 3+ files only to gain context
  (not to edit), prefer `cheap read <file1> <file2> ... ["question"]`.
- Effect: returns a ~600-token markdown summary instead of pulling
  raw files into the session context window.
- "Do NOT delegate" list: about-to-edit, non-trivial debugging,
  security-sensitive code, architectural decisions, cross-file
  refactor that depends on exact identifiers.
- Default rule: when unsure → don't delegate. Cost of a wrong summary
  outweighs tokens saved.

## 5. Quality safeguards

The single biggest risk is the cheap model **fabricating** in the
summary. Mitigations:

1. **Prompt discipline.** Template explicitly says "factual summary",
   names the buckets (API, data flow, invariants, gotchas), and tells
   the model to skip boilerplate. Low temperature (0.2).
2. **Per-file structure.** Output is per-file markdown headings, so
   Claude can spot which file a fact came from. Easier to verify.
3. **Verification test.** `tests/test_read_integration.py` feeds known
   sample files (in `tests/fixtures/`) and asserts that the summary
   contains specific public symbols and omits specific noise. Runs
   only when `RUN_INTEGRATION=1` and `OPENROUTER_API_KEY` set, so it
   does not block normal CI.
4. **Failure mode = visible.** If provider returns an error or empty
   response, CLI exits non-zero with the raw error. Claude's bash tool
   surfaces this; Claude falls back to native `Read`.

## 6. Testing

| Layer | Tool | Scope |
|-------|------|-------|
| Unit | pytest, `respx` or `openai` mock | CLI argparsing, file reading, prompt assembly, error paths |
| Contract | pytest with recorded `openai` response | Confirms request body matches expected shape |
| Integration | pytest, real OpenRouter, gated env | One sample call end-to-end, asserts summary contains known symbol |

CI: GitHub Actions (added in implementation phase if user keeps repo
private/public, otherwise local `pytest` only).

## 7. Installation & usage

```bash
# Install once:
pipx install /Users/admin/_Projects/cheap-llm-router

# First-time setup:
export OPENROUTER_API_KEY=sk-or-...           # add to shell profile
cheap config path                              # creates default config, prints location
$EDITOR ~/.config/cheap-llm/config.yaml        # adjust model if needed

# Add CLAUDE.md snippet:
cat /Users/admin/_Projects/cheap-llm-router/docs/claude-md-snippet.md \
  >> ~/.claude/CLAUDE.md

# Use in Claude Code: rule above tells Claude when to call `cheap read`.
```

## 8. Open questions

None blocking. Phase 1 ships with these defaults; revise after one
week of real use:

- **Model choice default.** Kimi K2 chosen for code-summary quality at
  ~1/100 Anthropic cost. If DeepSeek V3 proves better in practice,
  switch the default.
- **Summary size 600 tokens.** Empirical guess. May need 400 or 1000.
- **`max_input_chars: 400000`.** Roughly 100k tokens; conservative cap
  to avoid surprise OpenRouter charges.

## 9. Out of scope (explicit)

- Web UI or TUI. Library + CLI only.
- Caching of summaries. Each call is fresh; if Claude needs the same
  summary twice, that's Claude's problem (and a sign the workflow
  needs a tweak, not a cache).
- Token-cost telemetry. Nice-to-have for Phase 2; not Phase 1.
- Windows support. macOS + Linux only (matches user environment).
