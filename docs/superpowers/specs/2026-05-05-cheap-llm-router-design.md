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

Acceptance criteria (objectively verifiable in CI):

1. **Token reduction (context-only use case).** When run against the
   fixture set `tests/fixtures/sample_module/` (≥ 8 000 tokens of
   source, measured with `tiktoken` `cl100k_base` — used as a portable
   proxy since Anthropic's exact tokenizer is not published) — i.e.
   the read-for-context use case where the CLAUDE.md rule applies —
   `cheap read` produces a summary whose `output_tokens` (telemetry
   line on stderr, see §4.5) is ≤ 800. Files Claude plans to edit
   are out of scope for this measurement; those continue to use
   native `Read`.
2. **Fidelity (no fabrication).** Summary text mentions **every**
   public function name from the fixture (extracted via `ast.parse`)
   and contains **no** function name absent from the fixture.
   Implemented as `tests/test_read_integration.py`.
3. **Secrets safety.** Given a fixture file named `.env.test`, the
   CLI exits non-zero with a clear error and does NOT call the
   provider. Implemented as `tests/test_secrets_guard.py`.

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
already restores comfortable headroom. We measure first (§4.5
telemetry), expand if needed.

Phase boundaries:

| Phase | Trigger to start | Scope |
|-------|------------------|-------|
| 1 (now) | Decision made | `cheap read` CLI + CLAUDE.md rule |
| 2 | After ≥1 week using Phase 1, if `draft`/`extract` patterns prove painful in real use, OR if observed adoption rate of the CLAUDE.md rule is low | `cheap draft`, `cheap extract`, possibly a PreToolUse hook on `Read` |
| 3 | After Phase 1+2, if weekly-limit pressure persists | Node.js transparent proxy with Anthropic passthrough for `think` |

## 4. Architecture

### 4.1 Component diagram (Phase 1 scope only)

```
┌─────────────────────────────────────────────┐
│ Claude Code (subscription, native)          │
│                                             │
│   [Bash tool] ──► cheap read f1 f2 ... -q Q │
│                          │                  │
└──────────────────────────┼──────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────┐
        │ cheap_llm.commands.read           │
        │  1. read & concat files           │
        │     (refuses secret-name patterns)│
        │  2. build summary prompt          │
        │  3. call provider via openai SDK  │
        │  4. print summary to stdout       │
        │  5. emit telemetry to stderr      │
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
│   ├── secrets.py                # filename-pattern guard for `cheap read`
│   └── commands/
│       ├── __init__.py
│       ├── read.py               # `cheap read` implementation
│       └── install_claude_rule.py  # `cheap install-claude-rule` (idempotent)
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── sample_module/        # known files for fidelity test
│   │   │   ├── auth.py
│   │   │   ├── db.py
│   │   │   └── handlers.py
│   │   └── .env.test             # used by secrets-guard test
│   ├── test_config.py
│   ├── test_install_rule.py      # idempotency check
│   ├── test_secrets_guard.py     # filename-pattern refusal (acceptance §2.3)
│   ├── test_read_unit.py         # mocked OpenAI client
│   └── test_read_integration.py  # real OpenRouter call, gated by env var
└── docs/
    ├── claude-md-snippet.md      # snippet installed by `cheap install-claude-rule`
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

    For every public symbol you mention, cite as `path/to/file.py:LINE`
    so the reader can verify it. Do NOT invent symbols not present in
    the files; omit anything you are unsure about.

    Focus: {question_or_overview}

    Files:
    {files_block}

secrets_guard:
  # Glob patterns matched against each file's BASENAME via
  # fnmatch.fnmatch. Path-based patterns (e.g. ".aws/credentials")
  # are out of scope for Phase 1 — see §8 calibration points.
  patterns:
    - ".env*"                          # .env, .env.local, .env.production
    - "*.pem"                          # PEM-encoded keys/certs
    - "*.key"                          # bare private keys
    - "*.pfx"                          # PKCS#12 bundles
    - "credentials.json"               # gcloud / generic
    - "credentials.yaml"
    - "credentials.yml"
    - ".npmrc"                         # often holds auth tokens
    - ".pypirc"
    - "id_rsa"                         # exact private-key names
    - "id_dsa"
    - "id_ecdsa"
    - "id_ed25519"
                                       # NOTE: corresponding *.pub files are
                                       # public and intentionally allowed.
```

On first invocation of **any** subcommand (including `cheap read`),
if the config file is missing, the CLI writes the template above to
that path, prints `created default config at <path>` to stderr, and
proceeds — `cheap read` never fails just because config does not yet
exist.

Template substitution uses `str.format_map` with a `dict` subclass
whose `__missing__(key)` returns `"{" + key + "}"` — so user-added
literal `{...}` placeholders in custom prompts are preserved
verbatim instead of raising `KeyError`. Only the three documented
keys (`max_summary_tokens`, `question_or_overview`, `files_block`)
are guaranteed to be substituted; anything else is left as written.

When `-q` is omitted, `{question_or_overview}` is substituted
with the literal string
`(general structural overview — no specific question)`.

### 4.4 CLI surface

```bash
cheap --help
cheap read [-q QUESTION] [--include-sensitive] FILE [FILE...]
cheap config path             # print resolved config path
cheap config show             # print raw config (no env-substitution; api keys never printed)
cheap config check            # validate provider env vars are set; print "OK" or which is missing
cheap install-claude-rule     # idempotently install ~/.claude/CLAUDE.md section
```

`cheap read` semantics:

- All positional args are file paths; non-existent paths fail-fast
  with a clear error (no silent fallback to "this is the question").
- Optional `-q` / `--question` flag focuses the summary; without it,
  the model produces a general structural overview.
- **Secrets guard.** Refuses by default to read files whose
  **basenames** match `secrets_guard.patterns` (see §4.3) using
  `fnmatch.fnmatch` semantics. On match: exits non-zero with the
  offending file name; provider is NOT called. Override with
  `--include-sensitive` (writes a stderr warning naming the files,
  then proceeds). Goal: prevent accidentally forwarding secrets to a
  third-party LLM.
- Files are read as UTF-8; binary files cause a clear error, not a crash.
- Files are concatenated with a `--- FILE: <path> ---` header per file.
- If concatenation exceeds `max_input_chars`, CLI exits with a clear
  error suggesting the user pass fewer files or raise the cap.
- Output: markdown summary on stdout; telemetry + errors on stderr.

`cheap config show` deliberately does NOT substitute environment
variables; it prints the literal config (so `api_key_env:
OPENROUTER_API_KEY` shows as-is). This prevents real API keys ending
up in pasted screenshots, logs, or shared sessions. To verify the
provider is reachable, use `cheap config check` (prints `OK` or
`missing env: OPENROUTER_API_KEY`, never the value; exits 0 / 2
respectively).

`cheap install-claude-rule` semantics:

- Reads `docs/claude-md-snippet.md` shipped with the package.
- Looks in `~/.claude/CLAUDE.md` for heading `## Cheap LLM delegation`.
- If absent → appends snippet (with one blank line separator).
- If present → leaves the file untouched and prints `already installed`.
  No silent overwrite.
- `--force` flag overwrites the existing block (between heading and
  next `##` heading) with the shipped snippet.

### 4.5 Telemetry (stderr only)

Each `cheap read` invocation writes one line to stderr **after** the
provider call (so it does not contaminate stdout, which Claude
captures as the summary):

`[cheap] files=<N> input_chars=<N> output_tokens=<N> model=<id> elapsed_ms=<N>`

Rationale: this is the sole instrument that makes the "measure first"
approach in §3 actionable. No file logs, no remote telemetry, no
opt-out. The line surfaces in Claude Code's bash tool output, where
the user already looks. The `files=<N>` field lets the user later
correlate "how many files per call on average" with observed savings.

### 4.6 CLAUDE.md snippet

Installed (idempotently) by `cheap install-claude-rule`. Verbatim text
lives in `docs/claude-md-snippet.md`. Compact form, matching
`~/.claude/CLAUDE.md` v8.0 style:

> ## Cheap LLM delegation
>
> When reading 3+ files only for context (not to edit), prefer
> `cheap read F1 F2 ... -q "question"` (returns ~600-token summary).
> Skip when: editing those files, non-trivial debugging,
> security-sensitive code (auth/crypto/secrets/input validation),
> architectural decisions, cross-file refactor.
> NEVER pass files that may contain secrets (`.env`, `*.key`,
> credentials, private certs) and NEVER use `--include-sensitive` to
> bypass the guard for an LLM call. The guard exists to catch
> mistakes; bypassing it sends secrets to a third party.
> When unsure → don't delegate.

## 5. Quality safeguards

The single biggest risk is the cheap model **fabricating** in the
summary. A second risk is **secrets exfiltration**. Mitigations:

1. **Prompt discipline.** Template names the buckets (API, data flow,
   invariants, gotchas), forbids inventing symbols, and requires
   `path:LINE` citations for every named symbol so Claude can verify
   against source. Low temperature (0.2).
2. **Per-file structure.** Output is per-file markdown headings, so
   Claude can spot which file a fact came from. Easier to verify.
3. **Verification test.** `tests/test_read_integration.py` feeds the
   `tests/fixtures/sample_module/` files and asserts the summary
   contains every public function name (ground truth via `ast.parse`)
   and no fabricated names. Runs only when `RUN_INTEGRATION=1` and
   `OPENROUTER_API_KEY` set, so it does not block normal CI.
4. **Failure mode = visible.** If provider returns an error or empty
   response, CLI exits non-zero with the raw error. Claude's bash tool
   surfaces this; Claude falls back to native `Read`.
5. **Secrets guard.** `cheap read` refuses by default to read files
   matching `secrets_guard.patterns` from §4.3; explicit
   `--include-sensitive` flag required to override (with stderr
   warning). Independent from the CLAUDE.md rule — defence in depth.
   The provider is never called when a refused file is in the list.
6. **No env substitution in `cheap config show`.** Prevents real API
   keys appearing in pasted output.

## 6. Testing

| Layer | Tool | Scope |
|-------|------|-------|
| Unit | pytest, `respx` or `openai` mock | CLI argparsing, file reading, prompt assembly, error paths, `install-claude-rule` idempotency AND `--force` overwrite-and-replace path |
| Secrets | pytest | `tests/test_secrets_guard.py`: (a) refusal on `.env.test` with exit code 2 and no provider call; (b) `--include-sensitive` override proceeds with a stderr warning naming the file |
| Contract | pytest with recorded `openai` response | Confirms request body matches expected shape |
| Integration | pytest, real OpenRouter, gated env | `cheap read` against `sample_module` fixture, asserts both fidelity & token-reduction acceptance criteria from §2 |

CI: GitHub Actions (added in implementation phase if repo is published;
otherwise local `pytest` only).

## 7. Installation & usage

```bash
# Install once:
pipx install /Users/admin/_Projects/cheap-llm-router

# First-time setup:
export OPENROUTER_API_KEY=sk-or-...           # add to shell profile
cheap config path                              # creates default config, prints location
cheap config check                             # verify env var visible to the CLI
$EDITOR ~/.config/cheap-llm/config.yaml        # adjust model if needed

# Add CLAUDE.md rule (idempotent — safe to re-run):
cheap install-claude-rule

# Use in Claude Code: the rule tells Claude when to call `cheap read`.
```

## 8. Open questions

None block implementation. Calibration points to revisit after ≥1 week
of real use:

- **Model choice default.** Kimi K2 chosen for code-summary quality at
  ~1/100 Anthropic cost. If DeepSeek V3 proves better in practice,
  switch the default.
- **Summary size 600 tokens.** Empirical guess. May need 400 or 1000.
- **`max_input_chars: 400000`.** Roughly 100k tokens; conservative cap
  to avoid surprise OpenRouter charges.
- **Adoption rate.** This delegation is enforced by Claude reading
  `~/.claude/CLAUDE.md`, not by any hook. If observed adoption is low
  (Claude forgets to delegate when it should — checkable by counting
  `[cheap]` telemetry lines in session transcripts), Phase 2 may add
  a PreToolUse hook on `Read` that suggests `cheap read` when ≥3
  files are queued.
- **Secrets-guard pattern list.** Starting set in §4.3 covers obvious
  basenames without false positives on common public files (`*.pub`).
  Path-based patterns (e.g. `.aws/credentials`) require matching
  against the relative path, not just basename — deferred to Phase 2
  along with the guard's content-scanning question (§9).

## 9. Out of scope (explicit)

- Web UI or TUI. Library + CLI only.
- Caching of summaries. Each call is fresh; if Claude needs the same
  summary twice, that's Claude's problem (and a sign the workflow
  needs a tweak, not a cache).
- Cost telemetry beyond per-call stderr line. Roll-ups (daily, weekly
  totals) are nice-to-have for Phase 2.
- Content-based secret scanning (high-entropy strings, credential-like
  patterns inside file contents). Phase 1 only checks file basenames.
  Content scanning is meaningful but heavier; Phase 2 if leaks happen
  through name-only filtering.
- Path-based secret patterns (e.g. `.aws/credentials`, `.config/gcloud/*`).
  Basenames only in Phase 1; revisit with content scanning in Phase 2.
- Windows support. macOS + Linux only (matches user environment).
