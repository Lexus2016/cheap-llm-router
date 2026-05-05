# Install — cheap-llm-router

🌐 **Languages:** **English** · [Українська](INSTALL.uk.md) · [Русский](INSTALL.ru.md)

This walks you through setup. Each step stands on its own — if anything goes wrong, [UNINSTALL.md](UNINSTALL.md) tells you how to undo exactly that step.

## Before you start

You'll need:

- **macOS or Linux.** Windows isn't tested.
- **Python 3.11 or newer.** Check with `python3 --version`.
- **`pipx`.** Installs CLI tools in their own clean environment so they don't fight your system Python.
  - macOS: `brew install pipx`
  - Linux: `python3 -m pip install --user pipx && pipx ensurepath`
- **An OpenRouter account and API key.** Free signup at <https://openrouter.ai/>, then top up a few dollars and copy the key. It looks like `sk-or-v1-…`. (You can also use any other OpenAI-compatible provider — DeepSeek directly, a local Ollama, etc.)

## Step 1 — Install the `cheap` command

```bash
pipx install git+https://github.com/Lexus2016/cheap-llm-router.git
```

After this, the `cheap` command is on your PATH:

```bash
cheap --help
which cheap          # → ~/.local/bin/cheap (or similar)
```

If `cheap` isn't found, your shell might not have `~/.local/bin` on PATH. Run `pipx ensurepath` and open a new terminal.

## Step 2 — Tell `cheap` where to find your API key

The simplest way — paste this line into your shell startup file (`~/.zshrc` for zsh, `~/.bashrc` for bash, `~/.config/fish/config.fish` for fish):

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Then reload it:

```bash
source ~/.zshrc        # or open a new terminal
cheap config check     # → OK
```

If you see `missing env: OPENROUTER_API_KEY` instead, the export isn't visible — open a fresh terminal or check that you saved the right rc file.

**Alternative if env vars are awkward** — put the key directly in the config file:

```bash
$EDITOR "$(cheap config path)"
```

Find the `api_key_env: OPENROUTER_API_KEY` line, comment it out (`# api_key_env: ...`), and add right below:

```yaml
api_key: "sk-or-v1-..."
```

This works the same way, but the secret now lives in a YAML file. Keep it out of git, iCloud, Dropbox, and screenshots. `cheap config show` will mask it automatically; `cat` will not.

## Step 3 — Tell Claude / Codex about the new tool

This adds a section to `~/.claude/CLAUDE.md` (and to `AGENTS.md` for Codex if you have one) telling the AI when to use `cheap`. Safe to re-run — it won't duplicate.

```bash
cheap install-claude-rule
```

Re-running prints `already installed at …` and changes nothing. To overwrite the section with the latest rule text:

```bash
cheap install-claude-rule --force
```

## Step 4 — Try it out

Run a real summary on a small file from the project:

```bash
cheap read tests/fixtures/sample_module/auth.py -q "what does this do?"
```

You'll get a markdown summary on stdout and a telemetry line on stderr that looks like:

```
[cheap] files=1 input_chars=4255 output_tokens=587 model=deepseek/deepseek-v4-pro elapsed_ms=2143
```

That's it. From now on, when Claude or Codex would have read 3+ files just for context, the rule tells it to call `cheap` first.

## (Optional) Step 5 — Run the test suite

If you cloned the source tree and want to verify everything works:

```bash
cd /path/to/cheap-llm-router
python3 -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/pytest -q
# → 65 passed
```

To also run the live-network integration test (costs ~$0.01 against your OpenRouter balance):

```bash
RUN_INTEGRATION=1 .venv/bin/pytest -k integration
```

## Common issues

| Problem | What to do |
|---|---|
| `command not found: cheap` | Run `pipx ensurepath`, open a new terminal. |
| `missing env: OPENROUTER_API_KEY` | The export isn't in the current shell. `source ~/.zshrc` or open a new terminal. |
| `provider call failed: ... 401` | Wrong or revoked API key. Check at <https://openrouter.ai/keys>. |
| `provider call failed: ... 402` | Out of credits. Top up at <https://openrouter.ai/credits>. |
| `cheap install-claude-rule` adds the rule again | You're on an older version. Upgrade with `pipx reinstall cheap-llm-router`. |

## Updating later

If you installed from GitHub:

```bash
pipx reinstall cheap-llm-router
```

If you installed from a local clone:

```bash
cd /path/to/cheap-llm-router
git pull
pipx reinstall cheap-llm-router
```

If you installed with `--editable`, just `git pull` is enough — your local changes are picked up immediately.
