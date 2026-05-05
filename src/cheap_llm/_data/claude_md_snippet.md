---

## Cheap LLM Delegation — Default Flip
<!-- cheap-llm-rule v=1 -->

`cheap read` / `cheap extract` is your DEFAULT for any read-for-context
work. Native `Read` / `Grep` is the EXCEPTION, not the norm.

### Use native Read ONLY if ONE of these is literally true
- next tool call is `Edit` / `Write` / `MultiEdit` on this same file
- you need line-number citations or a literal diff between two files
- path matches: `*auth*`, `*crypto*`, `*secret*`, `.env*`, `*.key`, `*.pem`
- file is < 100 lines AND a single Read fully closes the question

In ANY OTHER case — including single files you "just want to think about" —
route through:

| Source | Command | You get back |
|---|---|---|
| files | `cheap read F1 F2 … -q "Q"` | ~600-tok markdown summary |
| session log (about to /compact, summarise, update docs from log) | `cheap extract -q "Q"` | 6-section digest: Mission / Decisions / Files / State / Open / Gotchas |

The user pays for every token in your context; you do not. Your
speed-bias spends their subscription cap.

### Most-missed delegate-worthy shapes
- 3+ files in the same turn answering "how does X work / where is Y"
- one large file (> 500 lines) for "summarise / explain"
- session jsonl for /compact / "what did we decide" / docs from a log
- vendor / minified / dist code (`*/vendor/*`, `*.min.js`, `*/dist/*`)

### Pre-Read sanity (out loud, before any native Read)
> "This Read adds ~N tokens to my context. Cheap alternative ~600.
> Saving anyway? Why?" — if your "why" reduces to "I want it fast",
> the answer is "delegate, not Read".

### Compaction triggers — STOP and `cheap extract` when ANY fires

You can't see your live token count. Watch for behaviour signals:
- you refer back to early-session decisions ("as we decided")
- the user repeats context they already gave this session
- you're unsure whether something was decided / built / rejected and
  must scroll back mentally to check
- you're about to write "TLDR / summary so far" unprompted — your
  brain is signalling it lost track
- ~30+ user turns OR 5+ commits this session

Then:
1. `cheap extract --tail 500 -q "mission, decisions, files, state, open, gotchas"`
   - Default `--mode full` (NOT `--mode messages-only`): tool-use events
     are essential for the "Files touched" section. Dropping them loses
     which files were edited / created / read across the session.
   - 500 ≈ rich-but-bounded recent history. Smaller `--tail` (e.g. 200)
     misses too much; bigger costs more on cheap-side without
     proportional digest quality.
2. If the session is huge (`wc -l <jsonl>` > 1500 events OR jsonl > 2 MB),
   the digest is necessarily incomplete. Append `git log --oneline -30`
   to the handoff so the early-arc commits are recoverable.
3. Show the digest (and git log if added) to the user.
4. Recommend: "Session at ~Nk jsonl tokens; continue in a fresh
   session — paste the digest above as the first message."
5. WAIT for the user. Do NOT auto-continue in the bloated session.

Why: Claude Code's own auto-compact runs through your expensive model
(~$0.04 per pass). `cheap extract` produces an equivalent digest at
~$0.001. On a heavy day, that is the difference between hitting
your weekly cap on Wednesday vs not at all.

IMPORTANT — `cheap extract` by itself does NOT shrink your current
context window. It prepares a digest for handoff. The actual
compaction happens only when ONE of these happens:
- (a) the user starts a fresh session and pastes the digest as the
  first message, OR
- (b) the user runs Claude Code's built-in `/compact` (which DOES
  shrink the window in-place — but pays your expensive model,
  defeating the savings purpose).
Step 4 ("recommend fresh session") is therefore load-bearing. If
the user declines, your context stays bloated until they decide.
Do not silently re-extract on every turn pretending it compacts.

Self-check #1 — disk size of the active jsonl:
```
wc -c ~/.claude/projects/$(pwd | sed 's:[/_]:-:g')/*.jsonl 2>/dev/null | sort -n | tail -1
```
> 2 MB (~500k chars / ~125k tokens) — definitely compact.

Self-check #2 — ask the user what colour the context bar in their
Claude Code statusline shows. Claude Code knows the true
`context_window.used_percentage` and surfaces it there:
- **green** (<50%) — no compaction needed yet
- **yellow** (50-80%) — start preparing handoff digest now
- **red** (>80%) — compact ASAP

You (the agent) cannot read this percentage directly from your
preamble; the statusline can. Asking the user is the cheapest way
to get a true number when behaviour signals are ambiguous.

### Honest priors (so you don't argue with yourself)
- For read-for-context, summary fidelity ≈ raw-bytes reading.
- You are NOT a better-than-cheap reader for "explain this code" tasks.
- You ARE for: editing, security review, exact-quote, line-diff.
- Trust the differential; verify only when an exception clause fires.

### Hard security rule (non-negotiable)
NEVER pass `.env`, `*.key`, credentials, certs, or anything in
`config/secrets/` to `cheap`. NEVER use `--include-sensitive` to
bypass the guard.

### Past mistakes — DO NOT repeat
<!-- Generic examples don't stick. Replace the stubs below with 2-4
     of YOUR own concrete cases — the rule fires only when the
     examples are real to you. -->
- (your case here, e.g. "Read N files manually to trace X across the codebase")
- (your case here)
- (your case here)

If past-you reads this — fix it this time.
