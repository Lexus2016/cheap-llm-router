---

## Cheap LLM Delegation — Mandatory Checkpoint

Two commands save subscription tokens. Use them BEFORE reading raw
files or session logs into context.

### Decision rule
Ask: "Do I need the EXACT TEXT, or just the ANSWER hidden in it?"

| If ANSWER, and… | Run | You get back |
|---|---|---|
| 3+ files OR file > 500 lines | `cheap read F1 F2 … -q "Q"` | ~600-tok markdown summary |
| about to /compact, summarise session, update docs from log | `cheap extract -q "Q"` | structured digest (Mission / Decisions / Files / State / Open / Gotchas) |

### Stay with native Read / Grep when
- Editing (Edit/Write needs exact whitespace).
- Quoting verbatim (security review, line numbers, diff).
- File < 500 lines AND a single Read covers it.
- Debugging non-trivial bugs / auth / crypto / secrets — quality > savings.

### Hard security rule
NEVER pass `.env`, `*.key`, credentials, certs, or anything in
`config/secrets/` to `cheap`. NEVER use `--include-sensitive` to
bypass the guard. The guard catches mistakes; bypassing it sends
secrets to a third party.

### Past mistakes — DO NOT repeat
<!-- Generic examples don't stick. Replace the stubs below with 2-4 of
     YOUR own concrete cases — the rule fires only when the examples
     are real to you. -->
- (your case here, e.g. "Read N files manually to trace X across the codebase")
- (your case here)
- (your case here)

If past-you reads this — fix it this time.
