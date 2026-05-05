# cheap-llm-router

**Save your Claude (or Codex) subscription tokens by letting a cheaper model do the file-reading for you.**

🌐 **Languages:** **English** · [Українська](README.uk.md) · [Русский](README.ru.md)

---

## What it does, in plain words

When Claude Code or OpenAI Codex CLI opens files for you, every line of those files gets fed into your expensive subscription model. Five-file reads alone burn around 8 000 tokens. A few of those per day and you bump into the weekly limit.

`cheap-llm-router` adds one small command: **`cheap`**. It sends those files to a much cheaper model (DeepSeek, Kimi, Gemini Flash, your pick) and gets back a short summary — typically 600 tokens. Your expensive model receives the **answer**, not the raw bytes.

Same idea for the chat history: when you're about to compact a long session or update docs from what you just did, `cheap extract` summarises the session log so the expensive model doesn't have to re-read it.

## Why you might want this

- **Hit the weekly limit less often.** Or never.
- **Same workflow.** You keep typing in Claude or Codex; `cheap` plugs in via a one-line rule in `CLAUDE.md` / `AGENTS.md`.
- **Any cheap model.** Works with anything OpenAI-compatible. Default is `deepseek/deepseek-v4-pro` (~$0.005 per call, 1M-token context window).
- **Two CLIs supported.** Claude Code and OpenAI Codex CLI, with auto-detection of which one you're in.
- **Honest about what it doesn't do.** It won't help with debugging, security audits, or tasks where you need exact text — for those it tells the expensive model to read the files itself.

## Quick start (3 steps)

### 1. Install

```bash
pipx install git+https://github.com/Lexus2016/cheap-llm-router.git
```

(`pipx` instead of `pip` so it gets its own clean Python environment. On macOS: `brew install pipx`.)

### 2. Set your OpenRouter key

Sign up free at <https://openrouter.ai/>, top up a few dollars, copy your key, then:

```bash
echo 'export OPENROUTER_API_KEY=sk-or-v1-...' >> ~/.zshrc
source ~/.zshrc
cheap config check       # → OK
```

### 3. Tell Claude / Codex about it

```bash
cheap install-claude-rule
```

That's it. From now on, when Claude or Codex is about to read a bunch of files just to gain context, it will use `cheap` automatically.

## The two main commands

### `cheap read FILE…`

Summarises a list of files. Use it when you have a **question** about the code, not a task to do.

```bash
cheap read src/auth.py src/db.py src/api.py -q "how does login work?"
```

You'll get a 600-token markdown summary on stdout, and one line on stderr telling you exactly what it cost:

```
[cheap] files=3 input_chars=15823 output_tokens=587 model=deepseek/deepseek-v4-pro elapsed_ms=2143
```

### `cheap extract`

Summarises **the current session's chat history**. Most useful right before `/compact` in Claude or when you're about to update documentation from what you just did.

```bash
cheap extract -q "what did we decide today?"
```

It figures out automatically whether you're in Claude Code or OpenAI Codex CLI and finds the right session file. Pass `--mode messages-only` to keep only chat turns (skip tool noise), or `--tail 50` to keep only the last 50 messages.

## Where the API key lives

Two supported placements — pick one.

| Where | When to use |
|---|---|
| **`OPENROUTER_API_KEY` shell env var** | **Recommended.** Key never enters a file. |
| **`api_key:` field** in `~/.config/cheap-llm/config.yaml` | Sandboxed shells, GUI launchers, restricted setups. |

If both are set, the YAML wins (explicit beats indirect).

When the key sits in the YAML, `cheap config show` masks it automatically as `***REDACTED***`. But `cat $(cheap config path)` does not — keep that file out of git, iCloud / Dropbox sync, and screenshots.

## Supported tools

- **Claude Code** (Pro / Max subscription) — primary target.
- **OpenAI Codex CLI** — full support: same `extract` command works on Codex's session JSONL via the `CODEX_THREAD_ID` env var.
- Anything else that reads `CLAUDE.md` or `AGENTS.md` — drop the rule there and you're done.

## Frequently asked questions

**Q: Will the AI know when to use `cheap` and when not to?**
A: Yes — `cheap install-claude-rule` writes a precise checklist into `CLAUDE.md` (and `AGENTS.md`). The rule says: *use `cheap` only when the question wants an answer, not exact text. Skip it for editing, security audits, or anything where the AI needs to quote or compare exact lines.*

**Q: Is it safe with secrets?**
A: `cheap read` refuses by default to send any file whose name matches `.env*`, `*.key`, `*.pem`, `id_rsa`, `credentials.json`, etc. Override with `--include-sensitive` (writes a warning), but please don't.

**Q: Where does my data actually go?**
A: To OpenRouter, then to whichever provider you picked (DeepSeek, Moonshot, Google…). If you already use Claude or Codex, your code already goes through one third-party AI vendor — this adds one more, but does not change the model qualitatively.

**Q: How much does it actually save?**
A: For a typical 5-file context-read: ~600 tokens of cheap-model output replace ~8 000 tokens of expensive-model context window. Roughly 13× cheaper per such operation. Real numbers depend on your workflow — `cheap` writes one telemetry line per call so you can do the math yourself.

**Q: I don't use Claude. Can I use this with just any shell?**
A: Yes — `cheap read` and `cheap extract` are plain shell commands. Type them yourself, pipe results around, do whatever you want. The `install-claude-rule` step is optional.

## Documentation

- [Install guide](INSTALL.md) — [Українська](INSTALL.uk.md) · [Русский](INSTALL.ru.md)
- [Uninstall guide](UNINSTALL.md) — [Українська](UNINSTALL.uk.md) · [Русский](UNINSTALL.ru.md)
- [Design notes](docs/superpowers/specs/2026-05-05-cheap-llm-router-design.md) (English, technical — for contributors)

## License

MIT — see [LICENSE](LICENSE).
