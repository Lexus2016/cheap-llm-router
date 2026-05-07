---

## Cheap LLM Delegation — Default Flip
<!-- cheap-llm-rule v=3 -->

`cheap read` / `cheap extract` is the DEFAULT for read-for-context work.
Native `Read` / `Grep` is the EXCEPTION.

### Use native Read ONLY if ONE applies
- next tool call is `Edit` / `Write` / `MultiEdit` on the SAME file
- file < 100 lines AND a single Read fully closes the question
- path matches `*auth*` / `*crypto*` / `*secret*` / `.env*` / `*.key` / `*.pem`
- need exact line numbers for citation OR literal diff between two files

### Delegate-worthy shapes
| Source | Command |
|---|---|
| files | `cheap read F1 F2 … -q "Q"` |
| session log | `cheap extract -q "Q"` |

The user pays for every token in your context; you do not.

### Compaction signal
If you refer back to early-session decisions or the user repeats context
they already gave this session, run
`cheap extract --tail 500 -q "mission, decisions, files, state, open, gotchas"`,
show the digest, recommend a fresh session, then WAIT.

{STATUSLINE_BLOCK}

### Hard security rule (non-negotiable)
NEVER pass `.env`, `*.key`, credentials, certs, or anything in
`config/secrets/` to `cheap`. NEVER use `--include-sensitive` to bypass
the guard.

### Past mistakes — replace with YOUR concrete cases
<!-- Generic stubs don't stick. Replace with 2-4 cases real to you. -->
- (your case here, e.g. "Read N files manually to trace X across the codebase")
- (your case here)
- (your case here)

If past-you reads this — fix it this time.
