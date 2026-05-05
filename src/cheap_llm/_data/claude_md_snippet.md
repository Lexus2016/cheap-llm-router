---

## Cheap LLM Delegation — Mandatory Checkpoint

**Before EVERY Read that touches 3+ files OR a single file >500 lines
for a question (not for editing) — STOP and route to `cheap read` first.
Same applies right after a Grep returns hits in 3+ files and you are
about to Read each match.**

This is a hard checkpoint, not a tip. If you're explaining file contents,
tracing a function across modules, surveying a vendor bundle, or
summarizing a large file — `cheap read` is the default tool. Native Read
is the fallback for editing, verbatim work, and line-by-line comparison
(see "Direct-Read is ONLY correct when" below for the exhaustive list).

### The one question
Before reading (or before opening 3+ files that a Grep just matched), ask:
> "Do I need the EXACT TEXT of these files, or just the ANSWER hidden in them?"

| Answer | Action |
|--------|--------|
| ANSWER + ≥ 3 files | `cheap read F1 F2 ... -q "specific question"` |
| ANSWER + single file > 500 lines | `cheap read F -q "..."` |
| TEXT (about to Edit / quote / diff) | direct Read |

### Red-flag triggers — when you catch ANY of these, STOP and route to cheap
- About to Read 3+ files in a row to trace one symbol/concept.
- Grep returned hits in 3+ files and you're about to Read each one.
- File is > 500 lines and you have a *question* about it (not editing).
- WH-style questions: "where / which / who / how does / why / summarize / structure".
- Researching upstream Chromium, a vendor's minified JS bundle, or any
  third-party source where you only need the gist.

### Direct-Read is ONLY correct when
- About to use the file path in Edit/Write tool (need exact whitespace/anchors).
- Need to quote verbatim (security audit, code review, exact line numbers).
- Line-by-line diff comparison.
- File < 500 lines AND a single Read covers the question.

### Past mistakes that violated this rule (DO NOT repeat)
<!-- Generic examples don't stick. Replace the stubs below with 2-4 of
     YOUR own concrete cases — the rule fires only when the examples
     are real to you. -->
- (your case here, e.g. "Read N files manually to trace X across the codebase")
- (your case here)
- (your case here)

In every such case `cheap read` was the right tool and would have saved
tens of thousands of tokens. If past-you reads this, fix it this time.

### Hard constraint (security)
NEVER pass `.env`, `*.key`, credentials, certs, or anything in
`config/secrets/` to `cheap read`. NEVER use `--include-sensitive` to
bypass the guard. The guard exists to catch mistakes; bypassing it sends
secrets to a third party.
