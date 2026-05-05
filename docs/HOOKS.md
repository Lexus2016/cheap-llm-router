# Optional: Stronger Session Detection (Claude Code SessionStart hook)

This page is **optional**. Skip it if `cheap extract` already works
for you out of the box.

## Why you might want this

Without the hook, `cheap extract` (run with no `--session-id` /
`--jsonl`) finds the current session by:

1. **Codex CLI** — reads the `CODEX_THREAD_ID` environment variable
   that Codex always exports to its child shells. Fully
   deterministic. Nothing to configure.
2. **Claude Code** — Claude does **not** export a session ID, so
   `cheap extract` falls back to "the newest `.jsonl` under
   `~/.claude/projects/<your-cwd-slug>/`". A `WARNING …` line is
   written to stderr so you know it's a guess.

That fallback is correct in 95% of cases (one Claude session per
working directory). It can pick the wrong file when you have **two
Claude Code sessions running in the same directory** — for example,
two tmux panes both started from the same project root.

The Claude Code SessionStart hook eliminates the guess: it captures
the exact session JSONL path at session start, scoped to the
parent-`claude` PID. `cheap extract` then reads the path
deterministically and the warning disappears.

## What the hook does

Claude Code runs the bundled `cheap-llm-session.sh` script every
time you start a session. The script:

1. Reads the JSON payload Claude Code sends on stdin.
2. Extracts the `transcript_path` field (the absolute `.jsonl`
   path).
3. Writes it to
   `${XDG_CACHE_HOME:-$HOME/.cache}/cheap-llm/sessions/<PPID>.txt`,
   where `<PPID>` is the PID of the parent `claude` process.

When `cheap extract` runs from inside the same Claude session, its
own `$PPID` is the same `claude` PID, so it just reads the file and
uses the path directly.

The script is best-effort: any failure (jq missing, write blocked,
malformed JSON) exits silently with code 0, so it can never block
Claude startup. If the hook fails, `cheap extract` simply uses the
fallback heuristic, exactly as it does without the hook.

## Install (manual — by design)

We deliberately do **not** ship a CLI subcommand that edits
`~/.claude/settings.json` for you. That file is high-blast-radius —
a malformed edit can prevent `claude` from starting at all (we have
seen this in the wild). The 30-second manual install below leaves
no automated edit risk.

### Step 1 — Locate the bundled script

```bash
python3 -c 'from importlib.resources import files; print(files("cheap_llm").joinpath("_data/cheap-llm-session.sh"))'
```

This prints the path to `cheap-llm-session.sh` inside the installed
package (under `~/.local/pipx/venvs/cheap-llm-router/...`). Copy it
somewhere stable so a `pipx reinstall` does not move it:

```bash
SRC=$(python3 -c 'from importlib.resources import files; print(files("cheap_llm").joinpath("_data/cheap-llm-session.sh"))')
mkdir -p ~/.claude/hooks
cp "$SRC" ~/.claude/hooks/cheap-llm-session.sh
chmod +x ~/.claude/hooks/cheap-llm-session.sh
```

### Step 2 — Wire it into `~/.claude/settings.json`

Open the file in your editor:

```bash
$EDITOR ~/.claude/settings.json
```

Find the top-level `"hooks"` object (create it if absent) and add a
`"SessionStart"` entry. The minimal complete settings.json with only
this hook looks like:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash /Users/YOU/.claude/hooks/cheap-llm-session.sh",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

If you already have other `SessionStart` hooks, append a new entry
to the existing array — do not replace it. The schema allows
multiple hooks at the same event.

**Replace `/Users/YOU/` with the actual absolute path printed by the
`mkdir -p ~/.claude/hooks` step above.** Tilde (`~`) does not
expand inside this JSON value.

### Step 3 — Restart Claude Code

Close and reopen Claude Code (or run `/restart` if your version
supports it). On the next session start, the hook fires and writes
`<PPID>.txt`.

### Step 4 — Verify

Run any command that triggers a Bash call inside the session, then
check:

```bash
ls "${XDG_CACHE_HOME:-$HOME/.cache}/cheap-llm/sessions/"
# → expect a file named <some-pid>.txt
```

And run `cheap extract` without arguments — the previous warning

```
cheap extract: WARNING no SessionStart hook output found; …
```

should be gone.

## Uninstall

Remove the entry from `~/.claude/settings.json`, delete
`~/.claude/hooks/cheap-llm-session.sh`, and clean the cache dir:

```bash
rm -f ~/.claude/hooks/cheap-llm-session.sh
rm -rf "${XDG_CACHE_HOME:-$HOME/.cache}/cheap-llm/sessions/"
$EDITOR ~/.claude/settings.json   # remove the SessionStart entry
```

Restart Claude Code. `cheap extract` reverts to the cwd-slug
fallback automatically — no other side effects.
