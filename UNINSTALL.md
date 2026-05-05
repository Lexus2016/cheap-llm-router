# Uninstall — cheap-llm-router

🌐 **Languages:** **English** · [Українська](UNINSTALL.uk.md) · [Русский](UNINSTALL.ru.md)

Reverses what [INSTALL.md](INSTALL.md) did. The steps are independent — stop at any point. They're listed from "lightest touch" (just stop using it) to "no trace left".

## Step 1 — Stop Claude / Codex from auto-using `cheap`

The rule lives in `~/.claude/CLAUDE.md` between `## Cheap LLM Delegation — Mandatory Checkpoint` and the next `## ` heading. Two options:

**(a) Edit by hand** — open the file and delete that section:

```bash
$EDITOR ~/.claude/CLAUDE.md
```

**(b) Automatic, with backup** — copy-paste this whole block into the terminal:

```bash
cp ~/.claude/CLAUDE.md ~/.claude/CLAUDE.md.bak
python3 - <<'PY'
import re, pathlib
p = pathlib.Path.home() / ".claude" / "CLAUDE.md"
text = p.read_text(encoding="utf-8")
m = re.search(r"^##\s+Cheap LLM\b.*$", text, re.MULTILINE | re.IGNORECASE)
if m:
    start = m.start()
    rest = text[m.end():]
    nm = re.search(r"^##\s", rest, re.MULTILINE)
    body_end = m.end() + nm.start() if nm else len(text)
    new = text[:start].rstrip() + "\n"
    if nm:
        new += "\n" + text[body_end:]
    p.write_text(new, encoding="utf-8")
    print("removed")
else:
    print("section not present — nothing to do")
PY
```

If you also have an `AGENTS.md` (for Codex) with the same section, repeat the same on it.

Verify nothing remains:

```bash
grep -n "Cheap LLM" ~/.claude/CLAUDE.md || echo "clean"
```

After this, the `cheap` command still works if you call it yourself, but Claude / Codex no longer use it automatically.

## Step 2 — Delete the config file

```bash
rm -rf ~/.config/cheap-llm
```

This removes `config.yaml`. There's no other state — `cheap` doesn't keep logs, caches, or databases of its own.

## Step 3 — Remove the `cheap` command

```bash
pipx uninstall cheap-llm-router
```

Verify:

```bash
which cheap || echo "gone"
```

If you installed it some other way:

```bash
pip uninstall -y cheap-llm-router      # plain pip
sudo pip uninstall -y cheap-llm-router # if installed system-wide as root
```

## Step 4 — Remove the API key from your shell

Open the rc file you edited during install:

```bash
$EDITOR ~/.zshrc        # or ~/.bashrc, ~/.config/fish/config.fish
```

Delete the `export OPENROUTER_API_KEY=…` line, then open a new terminal.

Verify:

```bash
echo "${OPENROUTER_API_KEY:-(unset)}"
# → (unset)
```

**Recommended bonus:** rotate or revoke the key at <https://openrouter.ai/keys> so an old saved copy can't be reused.

## Step 5 (Optional) — Delete the source tree

If you cloned the repo locally and want it gone:

```bash
rm -rf /path/to/cheap-llm-router
```

Removes the README, INSTALL/UNINSTALL guides, source code, tests, design docs, and `.git` history. After this, no trace of the project remains on disk.

## Quick check that everything's gone

If you did all 5 steps, this should print all five "gone"-ish lines:

```bash
which cheap                                                  # → not found
test -e ~/.config/cheap-llm && echo "config" || echo "config gone"
grep -c "Cheap LLM" ~/.claude/CLAUDE.md                       # → 0
echo "${OPENROUTER_API_KEY:-(unset)}"                         # → (unset)
test -e /path/to/cheap-llm-router && echo "src" || echo "src gone"
```

## Where the project does and doesn't write

For peace of mind — `cheap` writes only to:

- `~/.local/bin/cheap` (the command itself; removed by step 3)
- `~/.config/cheap-llm/config.yaml` (created on first run; removed by step 2)
- `~/.claude/CLAUDE.md` and / or `AGENTS.md` (only if you ran `install-claude-rule`; removed by step 1)

No system files, no daemons, no scheduled jobs, no network calls beyond the OpenRouter API requests you trigger yourself.
