---

## Cheap LLM Delegation — Default Flip

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
