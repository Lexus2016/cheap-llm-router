# cheap-llm-router

Delegate **read-for-context** summaries from Claude Code to a cheap
OpenAI-compatible model (Kimi K2, DeepSeek V3, Gemini Flash, …) via
OpenRouter or any compatible provider — so the expensive Anthropic
subscription is not burned on file reads.

Phase 1 ships exactly one command — `cheap read` — plus a CLAUDE.md
rule that tells Claude when to use it. Proxy and additional commands
are deferred until usage data shows they are needed.

> Full design: `docs/superpowers/specs/2026-05-05-cheap-llm-router-design.md`.

## Install

```bash
pipx install /Users/admin/_Projects/cheap-llm-router
```

For local development:

```bash
pipx install --editable /Users/admin/_Projects/cheap-llm-router
# or
pip install -e ".[test]"
```

## First-time setup

```bash
export OPENROUTER_API_KEY=sk-or-...           # add to your shell profile
cheap config path                              # creates default config, prints location
cheap config check                             # verify the env var is visible
$EDITOR ~/.config/cheap-llm/config.yaml        # adjust model if needed

cheap install-claude-rule                      # idempotent CLAUDE.md install
```

### Where to put the API key

Two supported placements — pick one:

| | Where the key lives | When to use |
|---|---|---|
| **`api_key_env: OPENROUTER_API_KEY`** (default) | Shell environment, e.g. exported in `~/.zshrc` | **Recommended.** Key stays out of dotfiles, screenshots, backups. |
| **`api_key: "sk-or-v1-..."`** (alternative) | Literal value in `~/.config/cheap-llm/config.yaml` | When exporting env vars is inconvenient (sandboxed shells, GUI launchers, restricted environments). |

If both are set, `api_key` wins (explicit beats indirect).

When `api_key:` is used, `cheap config show` automatically redacts the
value as `***REDACTED***`. **`cat` does not** — so treat the YAML
file as sensitive: keep it out of git, iCloud / Dropbox sync, and
screenshots.

## Usage

```bash
cheap read src/auth.py src/db.py src/handlers.py -q "explain shared state"
```

Returns a ~600-token markdown summary on stdout. A telemetry line is
written to stderr after the call:

```
[cheap] files=3 input_chars=15823 output_tokens=587 model=deepseek/deepseek-v4-pro elapsed_ms=2143
```

### Secrets guard

`cheap read` refuses by default to read files whose basenames look
like secrets (`.env*`, `*.key`, `*.pem`, `id_rsa`, `credentials.json`,
`.npmrc`, …). Override with `--include-sensitive` (writes a stderr
warning naming the files) — but please don't.

### CLI

```bash
cheap read [-q QUESTION] [--include-sensitive] FILE [FILE...]
cheap config path             # print resolved config path
cheap config show             # print raw config (no env-substitution)
cheap config check            # validate env vars; OK or "missing env: <NAME>"
cheap install-claude-rule [--force]
```

## Tests

```bash
pip install -e ".[test]"
pytest                        # unit + secrets + install — no network
RUN_INTEGRATION=1 pytest      # also runs the OpenRouter integration test
```

The integration test asserts both Phase 1 acceptance criteria:
1. Summary's `output_tokens` ≤ 800 against an ≥ 8 000-token fixture set.
2. Every public function name in the fixture appears in the summary;
   no fabricated names slip in.

## Design

See `docs/superpowers/specs/2026-05-05-cheap-llm-router-design.md`
for the full Phase 1 design (problem statement, non-goals, phase
boundaries, secrets-guard rationale, calibration points for Phase 2 / 3).

## License

MIT.
