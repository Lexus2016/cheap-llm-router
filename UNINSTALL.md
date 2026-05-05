# Uninstall — cheap-llm-router

Reverse exactly what `INSTALL.md` did. You can stop after any step —
the steps are independent. The order below removes from the lightest
touch (just disable in Claude) to a complete wipe (no trace left).

## 1. Disable the CLAUDE.md rule (so Claude stops calling `cheap`)

The rule lives between `## Cheap LLM delegation` and the next `## `
heading in `~/.claude/CLAUDE.md`. Two options:

**a) Manual edit** — open the file and delete that section:

```bash
$EDITOR ~/.claude/CLAUDE.md
```

**b) `sed` removal** — automated, also makes a backup:

```bash
cp ~/.claude/CLAUDE.md ~/.claude/CLAUDE.md.bak
python3 - <<'PY'
import re, pathlib
p = pathlib.Path.home() / ".claude" / "CLAUDE.md"
text = p.read_text(encoding="utf-8")
m = re.search(r"^## Cheap LLM delegation\s*$", text, re.MULTILINE)
if m:
    start = m.start()
    rest = text[m.end():]
    nm = re.search(r"^##\s", rest, re.MULTILINE)
    end = m.end() + nm.start() if nm else len(text)
    text = (text[:start].rstrip() + "\n") if (text[:start].strip()) else ""
    text += rest[nm.start():] if nm else ""
    p.write_text(text, encoding="utf-8")
    print("removed")
else:
    print("section not present — nothing to do")
PY
```

Verify nothing remains:

```bash
grep -n "Cheap LLM delegation" ~/.claude/CLAUDE.md || echo "clean"
```

After this, the CLI still works if invoked manually but Claude no
longer auto-delegates.

## 2. Remove the user config

```bash
rm -rf ~/.config/cheap-llm
```

Verify:

```bash
test -e ~/.config/cheap-llm && echo "still there" || echo "gone"
```

This deletes `config.yaml`. There is no other state — `cheap` writes
no logs, no caches, no databases.

## 3. Uninstall the CLI

```bash
pipx uninstall cheap-llm-router
```

Verify:

```bash
which cheap || echo "gone"
pipx list | grep -i cheap-llm-router || echo "not in pipx"
```

If you used `pipx install --editable`, the same command removes it.

If you installed with plain `pip` instead:

```bash
pip uninstall -y cheap-llm-router
```

If you ever installed the package globally as root (rare), use
`sudo pip uninstall -y cheap-llm-router`.

## 4. Remove the OPENROUTER_API_KEY env var

Edit your shell profile and delete the `export OPENROUTER_API_KEY=...`
line you added during install:

```bash
$EDITOR ~/.zshrc        # or ~/.bashrc, ~/.config/fish/config.fish, etc.
```

Reload the shell or open a new terminal. Verify:

```bash
echo "${OPENROUTER_API_KEY:-(unset)}"
# → (unset)
```

(Optional but recommended: rotate / revoke the key in the OpenRouter
dashboard so an old shell session can't reuse it.)

## 5. (Optional) Delete the source tree

```bash
rm -rf /Users/admin/_Projects/cheap-llm-router
```

Verify:

```bash
test -e /Users/admin/_Projects/cheap-llm-router && echo "still there" || echo "gone"
```

This removes the spec, tests, fixtures, source, README, INSTALL,
UNINSTALL, and `.git` history. After this, no trace of the project
remains on disk.

## Roll-back checklist

If you completed all 5 steps, this should be true:

```bash
which cheap                                             # → command not found
test -e ~/.config/cheap-llm && echo "config" || echo "config gone"
grep -c "Cheap LLM delegation" ~/.claude/CLAUDE.md      # → 0
echo "${OPENROUTER_API_KEY:-(unset)}"                    # → (unset)
test -e /Users/admin/_Projects/cheap-llm-router \
  && echo "source tree" || echo "source tree gone"
```

All five lines should report "gone" / "0" / "(unset)" / "command not
found".

## Roll-back from a partial install

You can run the steps in any order and stop at any time. The CLI
writes nothing outside of:

- `~/.local/bin/cheap` (installed by pipx — removed by step 3)
- `~/.config/cheap-llm/config.yaml` (auto-created on first run — removed by step 2)
- `~/.claude/CLAUDE.md` (only modified if you ran `cheap install-claude-rule` — see step 1)

No system-wide files, no daemons, no scheduled jobs, no network
side-effects beyond the OpenRouter API calls you triggered yourself.
