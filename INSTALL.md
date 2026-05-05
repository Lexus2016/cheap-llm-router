# Install — cheap-llm-router

Step-by-step setup. Each step is independent — if anything goes wrong,
`UNINSTALL.md` lists how to roll back exactly that step.

## 0. Prerequisites

- macOS or Linux.
- Python **3.11+** (`python3 --version`).
- `pipx` (`brew install pipx` on macOS, `python3 -m pip install --user pipx` elsewhere).
- An **OpenRouter** API key (or any other OpenAI-compatible endpoint
  + key — DeepSeek, Moonshot direct, local Ollama, etc.). Get one at
  <https://openrouter.ai/>.

## 1. Install the CLI

```bash
pipx install /Users/admin/_Projects/cheap-llm-router
```

This puts a `cheap` binary on your `PATH` (under `~/.local/bin/cheap`).

Verify:

```bash
cheap --help
which cheap     # → ~/.local/bin/cheap
```

To upgrade after editing the source:

```bash
pipx reinstall cheap-llm-router
```

For development (editable install, picks up source changes immediately):

```bash
pipx install --editable /Users/admin/_Projects/cheap-llm-router
```

## 2. Provide the provider API key

Add to your shell profile (`~/.zshrc`, `~/.bashrc`, `~/.config/fish/config.fish` …):

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
```

Reload your shell or `source ~/.zshrc`.

Verify the CLI sees it:

```bash
cheap config check
# → OK
# (exit code 0)
```

If it prints `missing env: OPENROUTER_API_KEY`, the env var is not in
the new shell — re-source your profile or open a fresh terminal.

## 3. (Optional) Adjust the default config

The first time any `cheap …` subcommand runs, it auto-creates
`~/.config/cheap-llm/config.yaml` from the embedded default. To
inspect or edit:

```bash
cheap config path     # prints the path
cheap config show     # prints the file (env vars NOT substituted; safe to paste)
$EDITOR "$(cheap config path)"
```

You may want to change:

- `provider.model` — switch to `deepseek/deepseek-chat-v3`,
  `google/gemini-2.5-flash`, etc.
- `read.max_summary_tokens` — raise/lower the target summary size.
- `secrets_guard.patterns` — add patterns specific to your repos.

## 4. Install the CLAUDE.md rule

Tells Claude Code when to delegate to `cheap read`. Idempotent — safe
to re-run.

```bash
cheap install-claude-rule
```

Result: a new `## Cheap LLM delegation` section is appended to
`~/.claude/CLAUDE.md` (or the file is created if missing).

Re-running prints `already installed at ...` and changes nothing. Use
`--force` to overwrite the section with the canonical snippet:

```bash
cheap install-claude-rule --force
```

## 5. Smoke test

Without burning the API:

```bash
# Secrets guard refuses .env on purpose:
cheap read tests/fixtures/.env.test \
           tests/fixtures/sample_module/auth.py
# → exit 2, "refused (matches secrets_guard.patterns)"
```

A real summary call (≈ \$0.005 on Kimi K2):

```bash
cheap read tests/fixtures/sample_module/auth.py \
           tests/fixtures/sample_module/db.py \
           -q "explain shared state and the public API"
# → markdown summary on stdout
# → [cheap] files=2 input_chars=N output_tokens=N model=... elapsed_ms=N on stderr
```

## 6. (Optional) Run the full test suite

```bash
cd /Users/admin/_Projects/cheap-llm-router
python3 -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/pytest -q
# → 22 passed, 2 skipped (integration gated)

# To run the integration test against a real OpenRouter call:
RUN_INTEGRATION=1 .venv/bin/pytest -k integration
```

## 7. Use it in Claude Code

In any Claude Code session, when Claude is about to read 3+ files only
to gain context, the CLAUDE.md rule will tell it to call:

```bash
cheap read src/foo.py src/bar.py src/baz.py -q "explain the auth flow"
```

That's it. Watch the per-call telemetry on stderr to see real savings.
