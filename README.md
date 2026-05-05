# cheap-llm-router

**Save your Claude (or Codex) subscription tokens by letting a cheaper model do the file-reading for you.**

🌐 **Languages:** **English** · [Українська](README.uk.md) · [Русский](README.ru.md)

> 🤖 **Don't want to install this manually?** Paste this prompt to your AI agent (Claude Code, Codex CLI, Cursor, Gemini, Aider — anything that can read URLs and run shell commands):
>
> > *"Read <https://github.com/Lexus2016/cheap-llm-router> and follow the* ***For AI agents (auto-install)*** *section in the README to install, configure, verify, and confirm `cheap` is running on this machine. Ask me only for my OpenRouter API key when you actually need it."*
>
> The agent will pipx-install, prompt you for the API key once, install the rule into your `CLAUDE.md` / `AGENTS.md`, run a smoke test, and report back. Tested with Claude Code, OpenAI Codex CLI, Gemini CLI, and Cursor.

---

## What it does, in plain words

When Claude Code or OpenAI Codex CLI opens files for you, every line of those files gets fed into your expensive subscription model. Five-file reads alone burn around 8 000 tokens. A few of those per day and you bump into the weekly limit.

`cheap-llm-router` adds one small command: **`cheap`**. It sends those files to a much cheaper model (DeepSeek, Kimi, Gemini Flash, your pick) and gets back a short summary — typically 600 tokens. Your expensive model receives the **answer**, not the raw bytes.

Same idea for the chat history: when you're about to compact a long session or update docs from what you just did, `cheap extract` summarises the session log so the expensive model doesn't have to re-read it.

## Why you might want this

- **Hit the weekly limit less often.** Or never.
- **Same workflow.** You keep typing in Claude or Codex; `cheap` plugs in via a one-line rule in `CLAUDE.md` / `AGENTS.md`.
- **Any cheap model.** Works with anything OpenAI-compatible. Default is `deepseek/deepseek-chat-v3-0324` (~$0.005 per typical 4-file call, 164K-token context window) — the verified non-reasoning model that survives our 17-model regression suite. See [Picking a model](#picking-a-model) for the full table.
- **Two CLIs supported.** Claude Code and OpenAI Codex CLI, with auto-detection of which one you're in.
- **Honest about what it doesn't do.** It won't help with debugging, security audits, or tasks where you need exact text — for those it tells the expensive model to read the files itself.

## Real numbers — how much it actually saves

Computed against the verified default (`deepseek/deepseek-chat-v3-0324` at $0.20 input / $0.77 output per 1M tokens) vs **current Anthropic and OpenAI list prices** (verified 2026-05-05 from OpenRouter):

| Subscription model | Input $/1M | Output $/1M |
|---|---|---|
| Claude Opus 4.7 | $5.00 | $25.00 |
| Claude Sonnet 4.6 | $3.00 | $15.00 |
| Claude Haiku 4.5 | $1.00 | $5.00 |
| GPT-5-codex (Codex CLI) | $1.25 | $10.00 |
| GPT-5.4 | $2.50 | $15.00 |

A typical context-read replaces ~8 000 raw-input tokens of code with a ~600-token summary. The expensive model still gets the answer it needs — only via the summary, not the bytes.

### One typical 5-file read (~8 000 input tokens → ~600-token summary)

| Path | Tokens consumed in your sub model | $ per call |
|---|---|---|
| Opus 4.7 (raw files) | 8 000 input | **$0.040** |
| Sonnet 4.6 (raw files) | 8 000 input | $0.024 |
| Haiku 4.5 (raw files) | 8 000 input | $0.008 |
| GPT-5-codex (raw files) | 8 000 input | $0.010 |
| **`cheap` + Opus 4.7** | 600 input (summary only) | $0.003 + $0.002 cheap call = **$0.005** &nbsp;**↓ 8×** |
| **`cheap` + Sonnet 4.6** | 600 input | $0.0018 + $0.002 = $0.004 &nbsp;**↓ 6×** |
| **`cheap` + GPT-5-codex** | 600 input | $0.00075 + $0.002 = $0.003 &nbsp;**↓ 3×** |
| **`cheap` + Haiku 4.5** | 600 input | $0.0006 + $0.002 = $0.003 &nbsp;**↓ 3×** |

### Heavy coding day — 50 context-reads

| Setup | Tokens consumed in sub model | Daily $ at Opus 4.7 prices |
|---|---|---|
| Without `cheap` | **400 000** | $2.00 |
| With `cheap` | **30 000** | **$0.25** |

You save **$1.75 per day per developer** at Opus 4.7 prices, plus ~$0.10 paid to OpenRouter for the cheap calls. Net: **$1.65/day saved**, ~$45/month per active developer.

### What this means for the weekly subscription cap

Claude Pro/Max and Codex Plus subscriptions ration capacity in **weekly token windows**, not just dollars. A 13× reduction in tokens-per-context-read is roughly **the difference between hitting your weekly cap on Wednesday vs sometime next month**. If you regularly bump into the limit, this is the single biggest fix you can apply without changing your workflow.

The expensive model still does the thinking. The cheap model only handles the "read these files and tell me what's in them" mechanical part — where deep reasoning isn't needed.

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

### Upgrading the rule later

Re-running `cheap install-claude-rule` after a new release stays silent if the local rule is current. When a newer rule version ships, you get an upgrade hint:

```
already installed at /Users/you/.claude/CLAUDE.md (rule v1; v2 available
  — run with --force to upgrade, this REPLACES the block including any
  local edits)
```

`--force` overwrites the entire `## Cheap LLM …` block, so any local edits in it (e.g. your own "Past mistakes" entries) are lost — copy them out first if you want to keep them.

## For AI agents (auto-install)

If you are an AI agent (Claude Code, Codex CLI, Gemini, Cursor, etc.) reading this README to set up `cheap` for your principal, run these steps in order. Stop and ask the user if a step needs information you don't have.

```bash
# 1. Ensure pipx is installed (macOS example):
command -v pipx >/dev/null 2>&1 || brew install pipx
pipx ensurepath

# 2. Install (or force-upgrade) cheap-llm-router:
pipx install --force git+https://github.com/Lexus2016/cheap-llm-router.git

# 3. Check status — will report a missing OPENROUTER_API_KEY:
cheap config check
```

If `cheap config check` reports missing `OPENROUTER_API_KEY`:

1. **STOP and ask the user** for their OpenRouter API key — they create one at <https://openrouter.ai/keys>.
2. Add to the shell profile (preferred — secret never enters a tracked file):
   ```bash
   echo 'export OPENROUTER_API_KEY=sk-or-v1-...' >> ~/.zshrc
   source ~/.zshrc
   ```
   For sandboxed setups, instead edit `~/.config/cheap-llm/config.yaml`, comment out the `# api_key_env:` line, and set `provider.api_key: "sk-or-v1-..."`.

Then continue:

```bash
# 4. Install the rule into ~/.claude/CLAUDE.md and ~/.codex/AGENTS.md:
cheap install-claude-rule

# 5. Smoke test — must print a markdown summary, NOT an empty/short output:
cheap read README.md -q "what is this project about?"
```

**Verify before reporting "done" to the user:**

- `cheap config check` returns `OK`.
- `cheap config show` shows `model: deepseek/deepseek-chat-v3-0324` (or another verified non-reasoning model — see [Picking a model](#picking-a-model)).
- The smoke test returns non-empty content (>500 bytes on stdout).

**If the smoke test returns empty / very short output**, the configured model is reasoning-capable (`deepseek/deepseek-v4-pro`, `kimi-k2.6`, `kimi-k2-thinking`, `glm-5.1`, `glm-4.7-flash`, `mimo-v2.5`) — it spent the entire `max_summary_tokens` cap on hidden thinking, leaving zero visible output. Switch the `model:` line in `~/.config/cheap-llm/config.yaml` to a verified non-reasoning model and re-run the smoke test.

**Before adopting any new model as the default**, run the bundled regression script — it catches all three known failure modes (empty output, cap broken, coverage drop):

```bash
git clone https://github.com/Lexus2016/cheap-llm-router.git /tmp/clr
/tmp/clr/scripts/test-model.sh <provider/model-id>
```

It auto-backs-up the user's config, runs single-file + 4-file tests, prints a PASS / NOT RECOMMENDED verdict with reasons, and restores the original config on exit (even on Ctrl-C).

## The two main commands

### `cheap read FILE…`

Summarises a list of files. Use it when you have a **question** about the code, not a task to do.

```bash
cheap read src/auth.py src/db.py src/api.py -q "how does login work?"
```

You'll get a 600-token markdown summary on stdout, and one line on stderr telling you exactly what it cost:

```
[cheap] files=3 input_chars=15823 output_tokens=587 model=deepseek/deepseek-chat-v3-0324 elapsed_ms=2143
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

## Works with any AI coding agent — the expensive model thinks, the cheap one reads

Your subscription model — Claude Opus, GPT-5, Sonnet, Gemini Pro — costs you weekly token quota whether it's reasoning about code or just reading 5 files for context. **Reading is mechanical work.** There's no reason to pay reasoning prices for it.

`cheap-llm-router` puts a $0.20/M-input model in front of your subscription. The cheap one handles "read these files — what's in them?" — your subscription gets the **answer** (~600 tokens) and spends its precious context on what it's actually good at: thinking, deciding, writing correct code.

**You keep:**
- Your subscription's reasoning quality (Opus / GPT-5 / Gemini Pro still do all the real work)
- Your existing IDE / CLI / chat workflow — `cheap` plugs in via a one-line rule
- Every existing prompt, project rule, habit

**You drop:**
- ~85% of tokens burnt on "read these files" busywork
- Most weekly-limit hits — gain weeks before bumping the cap
- The mental tax of rationing your subscription

**Tested AI agents:** Claude Code · OpenAI Codex CLI · Cursor · Gemini CLI · Aider · Cline · Continue.dev · Plandex · Crush · Goose · OpenCode · aichat. Works with anything else that reads `CLAUDE.md` / `AGENTS.md` rule files or can call shell commands.

> **Don't pay senior-architect rates to photocopy documents.**

## Picking a model

Not every cheap model is suitable. Three failure modes to dodge:

1. **Reasoning models** (e.g. `deepseek/deepseek-v4-pro`, `kimi-k2.6`, `kimi-k2-thinking`, `glm-5.1`, `glm-4.7-flash`, `mimo-v2.5`) — silently spend the whole `max_summary_tokens` cap on hidden thinking, returning empty visible output.
2. **Cap-ignoring models** (e.g. `kimi-k2.5`, `z-ai/glm-4.7`) — exceed the cap by 2-8×, blowing your token budget.
3. **Coverage-dropping models** (e.g. `kimi-k2`, `gpt-5.4-nano`) — focus all the cap on the first 1-2 files and ignore the rest on multi-file reads.

### Verified models (4-file 79K-char input, cap=1500 tokens, 2026-05-05 sweep)

| Model | Time | Tokens | Coverage | Context | $/4-file | Notes |
|---|---|---|---|---|---|---|
| **`deepseek/deepseek-chat-v3-0324`** ★ | **36s** | 1237 | **4/4** | 164K | $0.005 | DEFAULT — consistent, fast |
| `google/gemma-4-31b-it` | 50s | 1500 | 4/4 | 262K | $0.003 | ~35% cheaper, slightly slower |
| `deepseek/deepseek-v4-flash` | 78s | 1500 | 4/4* | 1M | $0.003 | For huge whole-module reads (>200K chars). Coverage was 3/4 in 2 of 3 retests — use only when context size matters. |

\* Use `deepseek/deepseek-v4-flash` only when you need its 1M context window. Pair it with `max_input_chars: 2500000` in `~/.config/cheap-llm/config.yaml`.

### Verify any new model before adopting it

The repository ships a regression script that catches all three failure modes:

```bash
git clone https://github.com/Lexus2016/cheap-llm-router.git /tmp/clr
/tmp/clr/scripts/test-model.sh openai/gpt-5.4-mini      # any provider/model id
```

It backs up your config, runs single-file + 4-file tests, prints a PASS / NOT RECOMMENDED verdict with reasons (empty output, cap broken, files dropped, slow), and restores your config on exit — even on Ctrl-C.

Cost of one run: roughly $0.005-$0.02 depending on the model. Cheaper than discovering a broken default in production.

## Frequently asked questions

**Q: Will the AI know when to use `cheap` and when not to?**
A: Yes — `cheap install-claude-rule` writes a precise checklist into `CLAUDE.md` (and `AGENTS.md`). The rule says: *use `cheap` only when the question wants an answer, not exact text. Skip it for editing, security audits, or anything where the AI needs to quote or compare exact lines.*

**Q: Is it safe with secrets?**
A: `cheap read` refuses by default to send any file whose name matches `.env*`, `*.key`, `*.pem`, `id_rsa`, `credentials.json`, etc. Override with `--include-sensitive` (writes a warning), but please don't.

**Q: Where does my data actually go?**
A: To OpenRouter, then to whichever provider you picked (DeepSeek, Moonshot, Google…). If you already use Claude or Codex, your code already goes through one third-party AI vendor — this adds one more, but does not change the model qualitatively.

**Q: How much does it actually save?**
A: 8× cheaper than feeding files to Claude Opus 4.7 directly, 6× vs Sonnet 4.6, ~3× vs GPT-5-codex. ~$1.65 per active developer per day at Opus 4.7 prices, ~$45/month. See [Real numbers](#real-numbers--how-much-it-actually-saves) above for the full table — `cheap` writes one telemetry line per call so you can verify the math against your own workflow.

**Q: I don't use Claude. Can I use this with just any shell?**
A: Yes — `cheap read` and `cheap extract` are plain shell commands. Type them yourself, pipe results around, do whatever you want. The `install-claude-rule` step is optional.

## Documentation

- [Install guide](INSTALL.md) — [Українська](INSTALL.uk.md) · [Русский](INSTALL.ru.md)
- [Uninstall guide](UNINSTALL.md) — [Українська](UNINSTALL.uk.md) · [Русский](UNINSTALL.ru.md)
- [Design notes](docs/superpowers/specs/2026-05-05-cheap-llm-router-design.md) (English, technical — for contributors)

## License

MIT — see [LICENSE](LICENSE).
