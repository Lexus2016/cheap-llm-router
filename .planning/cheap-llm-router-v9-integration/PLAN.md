# cheap-llm-router → CLAUDE.md v9.0 — Integration Plan

> Date: 2026-05-07
> Project: `/Users/admin/_Projects/cheap-llm-router` @ v0.7.0
> Source handoff: TQMemory note `4a940ea70b46477a` (global)
> Reference: `~/.claude/CLAUDE.md` (v9.0) vs `~/.claude/CLAUDE.md.v8.bak`

## Plan revision — 2026-05-07 (post-critique)

After self-critique against "would I do this for myself" filter, scope was
trimmed. **Authoritative scope = below.** Outdated text in §3-§7 is left
in place for traceability but is overridden by these deltas:

- **A2 DROPPED.** Existing heading regex is correct for our own blocks;
  A1's v9-native guard fixes the only real collision. A2 was defense-in-depth
  without a real threat.
- **A4 SCALED DOWN.** Hook message gets **one** added line —
  `Reference: ~/.claude/CLAUDE.md PRE-FLIGHT #3 (Cheap-first reads).`
  No bypass-list duplication (CLAUDE.md already has it).
- **A5 marker simplified.** Marker stays `<!-- cheap-llm-rule v=3 -->`;
  do NOT add `pkg={CHEAP_LLM_VERSION}`. `__version__` exposed for
  `cheap version` / `cheap diagnose` only.
- **A6 trimmed to ~7 tests.** Drop the heading-without-preflight edge case
  and the marker-includes-pkg-version test (no longer applicable).
- **B5 trimmed to 6 checks, 7 tests.** Merge `claude.md` + `preflight` into
  one check; drop the `rule.marker` info-only check; drop tests for
  invalid-RULES.json edge and verbose-extras. Keep security test (#8) — non-negotiable.
- **Order:** A5 → A1 → A3 → A4 → A6 (level-A green) → B5.1 → B5.2 → B5.3 → version bump → commit.
- **Estimate:** ~4-5h total, not 6-7h.

---

## 0. Context — what changed

**v8.0 architecture** (CLAUDE.md, single file):
- One long markdown doc; `cheap install-rule` injected a self-contained
  "Cheap LLM Delegation — Default Flip" section (`<!-- cheap-llm-rule v=2 -->`).
- Section duplicated/replaced equivalent v8 native content where present.

**v9.0 architecture** (multi-file, machine-mirrorable):
- `~/.claude/CLAUDE.md` v9.0 — leads with **ABSOLUTE PRE-FLIGHT** (5 ordered checks).
  Rules now native: PRE-FLIGHT #3 = cheap-first reads, full reference in
  "Cheap LLM Delegation — full reference" section, "Compaction Triggers" section.
- `~/.claude/RULES.json` — machine-readable mirror consumed by hooks.
- `~/.claude/ACTIVATION.md` — spec for activation token
  `[STATE] lang=uk | cheap=on | automem=off | ssot_triggered={yes|no} | self_check=passed`.
- `~/.claude/MCP.md`, `~/.claude/RTK.md` — short reference files.

**Key collision risk:**
v9.0 CLAUDE.md natively contains a section titled
**"Cheap LLM Delegation — full reference"**. Current `install_rule.py` heading regex
`_HEADING_RE = re.compile(r"^## Cheap LLM\b.*$", re.MULTILINE | re.IGNORECASE)`
**WILL match the native v9.0 heading** as if it were a legacy `v=1` (no marker)
install. With `--force`, it would overwrite the user's hand-written v9.0 rules.
Without `--force`, it would print a misleading "upgrade hint".

**This is the showstopper that level A must fix first.**

---

## 1. Scope and non-scope

### In scope (this plan)

- **Level A** — critical fixes so cheap-llm-router coexists with v9.0:
  - A1. Detect v9.0 native CLAUDE.md and refuse to overwrite native rule sections.
  - A2. Disambiguate marker detection: only blocks with our `<!-- cheap-llm-rule v=N -->`
    marker count as "ours".
  - A3. Bump rule template to **v=3** — slimmed-down supplement, not duplicate.
  - A4. Refresh hook block messages to point at PRE-FLIGHT #3 exception list.
  - A5. Unified versioning: expose `__version__` from package metadata,
    embed in template marker and CLI.
  - A6. Targeted regression tests for the above.
- **Level B#5** — `cheap diagnose` command reporting on the new v9.0 surface:
  - B5.1. New `commands/diagnose.py`.
  - B5.2. Wire into `cli.py`.
  - B5.3. Tests.

### Out of scope (deferred / forbidden)

- **Forbidden to touch** (per user, this session):
  `src/cheap_llm/commands/read.py`, `src/cheap_llm/client.py`,
  `src/cheap_llm/transcript/*`. Tests in `tests/` are the safety net.
- **Deferred** (later sessions / level B/C from handoff):
  - Level B: `rules-sync` command, `cheap extract` "recommend fresh session"
    block formulation.
  - Level C: `install-activation`, TQMemory integration, Stop-hook for sync drift.

---

## 2. Current state — what was learned from research

| File | LOC | Role |
|---|---|---|
| `pyproject.toml` | 34 | `version = "0.7.0"`, entry `cheap = "cheap_llm.cli:app"` |
| `src/cheap_llm/__init__.py` | 0 | **EMPTY** — no `__version__` exposed |
| `src/cheap_llm/cli.py` | 211 | Typer subcommands: read, extract, install-rule, install-hook, pretooluse-hook, install-claude-rule (alias), config (path/show/check), usage (path) |
| `src/cheap_llm/_data/rule_template.md` | 108 | Template body, marker `<!-- cheap-llm-rule v=2 -->`, vars `{AGENT_NAME}`, `{AGENT_COMPACT_REF}`, `{JSONL_PATH_CMD}`, `{STATUSLINE_BLOCK}` |
| `src/cheap_llm/commands/install_rule.py` | 317 | `_HEADING_RE`, `_VERSION_RE`, `resolve_targets()`, `install_into()`, `run()` |
| `src/cheap_llm/commands/install_claude_rule.py` | 27 | Deprecated alias forwarding to `install_rule.run(target="claude")` |
| `src/cheap_llm/commands/install_hook.py` | 143 | Edits `~/.claude/settings.json`; modes block/soft |
| `src/cheap_llm/hook_pretool_read.py` | 315 | PreToolUse hook; multi-Read + large-Read block messages |

**Key constants today:**
```python
# install_rule.py
_HEADING_PREFIX = "## Cheap LLM"
_HEADING_RE     = re.compile(rf"^{re.escape(_HEADING_PREFIX)}\b.*$",
                              re.MULTILINE | re.IGNORECASE)
_VERSION_RE     = re.compile(r"<!--\s*cheap-llm-rule\s+v=(\d+)\s*-->")
```

**Today's hook messages** (`hook_pretool_read.py:144-175`):
- `🚫 Multi-file Read blocked ({n+1} full reads in last {WINDOW} turns). Run: cheap read <files> -q '<question>'.`
- `🚫 Large-file Read blocked ({n_lines} lines). Run: cheap read {file_path} -q '<question>' or retry Read with offset+limit.`
- Plus longer "additional context" agent messages with `Read BLOCKED.` / `ACTION:` prefix.

**Existing tests confirm the ABI we must not break:**
- `tests/test_install_rule.py` — version handling, force, multi-target,
  template rendering (16+ tests).
- `tests/test_hook_pretool_read.py` — asserts presence of substrings
  `"Large-file Read blocked"`, `"Multi-file Read blocked"`,
  `"Read BLOCKED"`, `"cheap read"`, `"offset+limit"`.
- `tests/test_install_hook.py` — idempotency, soft/block, malformed JSON,
  preserve unrelated hooks.

---

## 3. Level A — task breakdown

### A1. v9.0 native CLAUDE.md detection (safety fix)

**Problem.** Running `cheap install-rule` (with or without `--force`) on a v9.0
CLAUDE.md misidentifies the native "## Cheap LLM Delegation — full reference"
section as a legacy unmarked block.

**Solution.** Add a v9.0 fingerprint check that runs *before* heading lookup.

**File:** `src/cheap_llm/commands/install_rule.py`

**Steps:**
1. Add module-level constants:
   ```python
   _V9_PREFLIGHT_MARKER = "## ABSOLUTE PRE-FLIGHT"
   _V9_VERSION_LINE_RE  = re.compile(r"^>\s*Version:\s*9\.\d+\b", re.MULTILINE)
   ```
2. In `install_into()` (currently lines 175–217), insert a guard before
   the heading scan:
   ```python
   if _looks_like_v9_native(existing_text):
       return "skipped:v9-native"
   ```
3. New helper `_looks_like_v9_native(text: str) -> bool`:
   `True` if both `_V9_PREFLIGHT_MARKER` substring is present **and**
   no `<!-- cheap-llm-rule v=N -->` marker exists in the file.
4. `run()` (lines 220–254) handles new return code `"skipped:v9-native"` by
   printing a helpful message:
   `"{path} appears to be v9.0 native (PRE-FLIGHT detected). Native rules already cover cheap-first delegation. Run 'cheap diagnose' to verify."`
5. `--force` does **not** bypass this guard. Bypass requires the explicit
   new flag `--force-overwrite-v9-native` (intentionally awkward).

**Acceptance:**
- `install-rule` on v9.0 CLAUDE.md prints the skip message, exits 0,
  file unchanged.
- `install-rule --force` on v9.0 CLAUDE.md still skips (does not overwrite).
- `install-rule --force-overwrite-v9-native --force` overwrites (escape hatch).

**Risk:** None — the v9.0 fingerprint is specific enough that v8 files
(which never had `## ABSOLUTE PRE-FLIGHT`) won't trigger it.

---

### A2. Disambiguate marker detection

**Problem.** `_HEADING_RE` matches any `## Cheap LLM …` heading, then
`_VERSION_RE` is consulted only afterwards. This is fragile.

**Solution.** Tighten "is this our block?" criteria.

**File:** `src/cheap_llm/commands/install_rule.py`

**Steps:**
1. Rename and narrow `_HEADING_PREFIX`:
   ```python
   _HEADING_PREFIX = "## Cheap LLM Delegation — Default Flip"
   ```
   (matches the literal heading our template has emitted since v=2).
2. Keep a **legacy fallback** matcher for v=1/v=2 blocks that may have
   been edited by users:
   ```python
   _LEGACY_HEADING_RE = re.compile(
       r"^## Cheap LLM Delegation(?:\s*[—-]\s*Default Flip)?\b.*$",
       re.MULTILINE,
   )
   ```
3. A block counts as "ours" only if **either**:
   (a) it has the `<!-- cheap-llm-rule v=N -->` marker within ~10 lines of
   the heading, **or**
   (b) the file has no `_V9_PREFLIGHT_MARKER` and the legacy heading matches
   (preserves v=1 detection for old installs).
4. Update `install_into()` upgrade-detection logic to use the new helper
   `_find_existing_block(text) -> tuple[Match | None, int | None]`
   returning `(match, version_or_None)`.

**Acceptance:**
- Existing v=1 (pre-marker) blocks still detected on old v8 files.
- v9.0 CLAUDE.md's native "## Cheap LLM Delegation — full reference"
  is **not** matched (different heading text).
- Existing tests in `test_install_rule.py` continue to pass after
  test fixtures are tightened (see A6).

**Risk:** A v=1 user who hand-edited the heading from "Default Flip" to
something else (e.g., "Cheap LLM Rules") will lose auto-upgrade detection.
Acceptable — they can use `--force` against an exact path.

---

### A3. Rule template → v=3 (slimmed supplement)

**Problem.** v=2 template duplicates content now native in v9.0
(compaction triggers, cheap-first rationale, security rule).
On a project-local AGENTS.md or older CLAUDE.md it's still useful, but
on v9.0 CLAUDE.md it's wasteful even after A1's guard fires
(install-rule against codex AGENTS.md continues to inject the full thing).

**Solution.** Trim the template; keep what is **not** in v9.0 native.

**File:** `src/cheap_llm/_data/rule_template.md`

**New template (sketch — exact text in commit):**
```
---

## Cheap LLM Delegation — Default Flip
<!-- cheap-llm-rule v=3 pkg={CHEAP_LLM_VERSION} -->

`cheap read` / `cheap extract` is the DEFAULT for read-for-context work.
Native `Read` / `Grep` is the EXCEPTION.

### Use native Read ONLY if ONE applies
- next call is `Edit` / `Write` / `MultiEdit` on the SAME file
- file < 100 lines AND a single Read fully closes the question
- path matches `*auth*` / `*crypto*` / `*secret*` / `.env*` / `*.key` / `*.pem`
- need exact line numbers for citation OR literal diff between two files

### When delegate-worthy
| Source | Command |
|---|---|
| files | `cheap read F1 F2 … -q "Q"` |
| session log | `cheap extract -q "Q"` |

### Compaction signal
If you refer back to early-session decisions or the user repeats context
they already gave: run
`cheap extract --tail 500 -q "mission, decisions, files, state, open, gotchas"`,
show digest, recommend a fresh session, WAIT.

### Hard security rule
NEVER pass `.env`, `*.key`, credentials, certs, or `config/secrets/` to `cheap`.
NEVER use `--include-sensitive` to bypass the guard.

### Past mistakes — replace with YOUR cases
- (your case)
- (your case)

{STATUSLINE_BLOCK}
```

**Diff vs v=2:** drops "Pre-Read sanity", "Honest priors", verbose JSONL
self-check, AGENT_COMPACT_REF mentions, and the long compaction-triggers
prose. Keeps: rule list, security rule, compaction signal (terse), past-mistakes
stub. ~50% smaller.

**Steps:**
1. Rewrite `src/cheap_llm/_data/rule_template.md`.
2. Bump marker to `v=3` and add `pkg={CHEAP_LLM_VERSION}` to the marker line.
3. Update `_RULE_VARS` substitution table in `install_rule.py` to provide
   `CHEAP_LLM_VERSION` (sourced from `__version__`, see A5).
4. Drop `{AGENT_COMPACT_REF}` from `_RULE_VARS` if no longer referenced
   (verify with `grep`).
5. Update upgrade hint text: `v=2 → v=3` rather than `v=1 → v=2`.

**Acceptance:**
- `cheap install-rule --force` on a fresh empty CLAUDE.md emits the new v=3 block.
- `cheap install-rule` on an existing v=2 block prints upgrade hint
  citing v=3 and the line `Run 'cheap install-rule --force' to upgrade`.
- All existing template-render tests in `test_install_rule.py` updated
  to assert against new content (substring checks, not exact-match).

**Risk:** Users actively relying on the long v=2 prose will see less
guidance. Mitigation: that prose is now in v9.0 CLAUDE.md natively;
project-local AGENTS.md targets a non-Claude-Code agent (Codex CLI),
where the slimmed template is more appropriate anyway.

---

### A4. Hook message → PRE-FLIGHT #3 reference

**Problem.** Block messages don't tell agents which CLAUDE.md rule
they're enforcing, so when bypass conditions fire (e.g., file < 100 lines)
the agent doesn't know which exception to invoke.

**File:** `src/cheap_llm/hook_pretool_read.py`

**Steps:**
1. Update multi-Read block (around lines 144–160):
   - Keep first line wording (`🚫 Multi-file Read blocked …`) — preserves
     test substring assertions.
   - In the "additional context" body, append:
     ```
     Reference: ~/.claude/CLAUDE.md PRE-FLIGHT #3 (Cheap-first reads).
     Bypass conditions (use native Read ONLY if ONE applies):
       - next call is Edit / Write / MultiEdit on the SAME file
       - file < 100 lines AND single Read closes the question
       - path matches *auth* / *crypto* / *secret* / .env* / *.key / *.pem
       - need exact line numbers OR literal diff between two files
     ```
2. Same for large-Read block (lines 162–175).
3. Reuse a single helper `_preflight_3_reference()` so wording stays in sync.

**Acceptance:**
- Existing assertions in `test_hook_pretool_read.py` still pass
  (we only **append** text, don't change first-line wording).
- New test asserts `"PRE-FLIGHT #3"` substring is present.

**Risk:** Output gets ~6 lines longer per block. Acceptable —
hook output is one-shot per blocked call.

---

### A5. Unified versioning from `pyproject.toml`

**Problem.** `__init__.py` is empty; rule version (`v=N`) and package version
(`0.7.0`) are tracked in unrelated places.

**File:** `src/cheap_llm/__init__.py` (currently empty)

**Steps:**
1. Populate `__init__.py`:
   ```python
   from importlib.metadata import PackageNotFoundError, version

   try:
       __version__ = version("cheap-llm-router")
   except PackageNotFoundError:  # editable install before metadata exists
       __version__ = "0.0.0+local"

   RULE_TEMPLATE_VERSION = 3
   ```
2. Refactor `install_rule.py`:
   - Replace hard-coded `v=2` references with `cheap_llm.RULE_TEMPLATE_VERSION`.
   - Inject `CHEAP_LLM_VERSION = cheap_llm.__version__` into `_RULE_VARS`.
3. Add a `version` Typer subcommand to `cli.py`:
   ```python
   @app.command("version")
   def version_cmd() -> None:
       """Print package and rule-template versions."""
       from cheap_llm import __version__, RULE_TEMPLATE_VERSION
       typer.echo(f"cheap-llm-router {__version__} (rule template v={RULE_TEMPLATE_VERSION})")
   ```
4. Bump `pyproject.toml` `version` to `"0.8.0"` in the same commit
   (level A is breaking-ish: marker bump v=2→v=3, new behavior on v9.0
   detection, escape-hatch flag added).

**Acceptance:**
- `cheap version` prints `cheap-llm-router 0.8.0 (rule template v=3)`.
- `cheap install-rule --force` produces a marker line containing both
  `v=3` and `pkg=0.8.0`.

**Risk:** `importlib.metadata.version()` requires the package to be
installed (`pip install -e .`). For non-installed bare-source runs,
fallback `0.0.0+local` is used. Acceptable.

---

### A6. Targeted tests

**File:** `tests/test_install_rule.py` (extend), new `tests/test_v9_integration.py`

**New tests:**
1. `test_install_rule_skips_v9_native_claude_md` — fixture file containing
   `## ABSOLUTE PRE-FLIGHT` and `> Version: 9.0 …`; assert install-rule
   prints skip message and leaves file untouched.
2. `test_install_rule_force_still_skips_v9_native` — same fixture,
   `--force` flag, still skipped.
3. `test_install_rule_force_overwrite_v9_native_escape_hatch` —
   with both flags, file is overwritten (escape hatch works).
4. `test_install_rule_does_not_match_v9_native_heading` — fixture with
   only `## Cheap LLM Delegation — full reference\n…` (no PRE-FLIGHT marker
   to bypass safety): assert that the v9 native heading is **not** treated
   as a legacy v=1 block — install-rule appends a new block rather than
   replacing the section.
5. `test_install_rule_v2_to_v3_upgrade_path` — fixture with v=2 marker;
   assert without `--force` the upgrade hint text mentions `v=3` (or
   the current `RULE_TEMPLATE_VERSION`), and with `--force` the marker
   is replaced.
6. `test_marker_includes_package_version` — assert the rendered template
   contains `pkg=0.8.0` (or current `__version__`).
7. `test_template_has_no_unsubstituted_placeholders_v3` — covering new
   `{CHEAP_LLM_VERSION}` substitution.

**File:** `tests/test_hook_pretool_read.py` (extend)
8. `test_block_message_references_preflight_3` — assert blocked output
   contains `"PRE-FLIGHT #3"` substring.
9. `test_block_message_lists_bypass_conditions` — assert the four bypass
   bullets (Edit-next, <100 lines, secret paths, exact-line-numbers) appear.

**File:** `tests/test_version.py` (new, tiny)
10. `test_package_exposes_version` — `from cheap_llm import __version__`,
    assert it parses as a PEP 440 version (`packaging.version.Version`).
11. `test_cheap_version_command` — invoke `cheap version` via Typer
    runner, assert output contains both package version and `v=N`.

**Acceptance:** all 11 new tests pass; full `pytest` suite green
(no regressions in existing 60+ tests).

---

## 4. Level B#5 — `cheap diagnose` command

### B5.1. New command module

**File:** `src/cheap_llm/commands/diagnose.py` (new)

**Public API:**
```python
def run(*, json_output: bool = False, verbose: bool = False) -> int: ...
```

**Checks performed (each returns dict {name, status, detail}):**

| Check | PASS condition | WARN | FAIL |
|---|---|---|---|
| `claude.md` | exists + Version: 9.x detected | exists, v8.x or unknown | missing |
| `claude.md.preflight` | has `## ABSOLUTE PRE-FLIGHT` | — | missing |
| `rules.json` | exists + valid JSON | exists but invalid JSON | missing |
| `activation.md` | exists + token spec line found | exists no spec | missing |
| `settings.json` | exists + valid JSON | exists invalid | missing |
| `hook.pretooluse.read` | installed (block mode) | installed (soft mode) | not installed |
| `cheap.config` | `resolve_api_key()` returns OK | config file missing → template created | API key resolution fails |
| `cheap.version` | package version + rule template version | — | import fails |
| `rule.marker` | (info) which v=N marker present in CLAUDE.md, if any | — | — |

**Implementation sketch:**
```python
from __future__ import annotations
import json, re, sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import typer

from cheap_llm import __version__, RULE_TEMPLATE_VERSION
from cheap_llm import config as config_mod

Status = Literal["PASS", "WARN", "FAIL", "INFO"]

@dataclass
class Check:
    name: str
    status: Status
    detail: str

def _check_claude_md(home: Path) -> list[Check]: ...
def _check_rules_json(home: Path) -> list[Check]: ...
def _check_activation_md(home: Path) -> list[Check]: ...
def _check_settings_and_hook(home: Path) -> list[Check]: ...
def _check_config_and_key() -> list[Check]: ...
def _check_versions() -> list[Check]: ...

def run(*, json_output: bool = False, verbose: bool = False,
        home: Path | None = None) -> int:
    home = home or Path.home()
    checks: list[Check] = []
    checks += _check_versions()
    checks += _check_claude_md(home)
    checks += _check_rules_json(home)
    checks += _check_activation_md(home)
    checks += _check_settings_and_hook(home)
    checks += _check_config_and_key()

    if json_output:
        typer.echo(json.dumps([c.__dict__ for c in checks], indent=2))
    else:
        _render_table(checks, verbose=verbose)

    has_fail = any(c.status == "FAIL" for c in checks)
    return 1 if has_fail else 0
```

**Output format (non-JSON):**
```
cheap-llm-router 0.8.0 (rule template v=3)

CLAUDE.md         PASS  v9.0 detected (~/.claude/CLAUDE.md, 248 lines)
PRE-FLIGHT block  PASS  found at line 9
RULES.json        PASS  valid JSON, 14 keys (~/.claude/RULES.json)
ACTIVATION.md     PASS  token spec found
settings.json     PASS  valid JSON
PreToolUse hook   PASS  installed (block mode)
cheap config      PASS  ~/.config/cheap-llm/config.yaml, model=deepseek-chat-v3-0324
API key           PASS  CHEAP_API_KEY env var

Result: 8/8 checks passed
```

`--verbose` adds: file mtimes, raw line counts, redacted config dump,
rule marker version found in CLAUDE.md.

**Security:** `_check_config_and_key()` MUST use `config_mod.redact_secrets()`
(or never print the key at all — only "OK" / "missing"). No raw key in any
output mode. Replicate the same secrets guard pattern used by `cheap config show`.

---

### B5.2. Wire into `cli.py`

**File:** `src/cheap_llm/cli.py`

**Add (around the existing top-level commands):**
```python
from cheap_llm.commands import diagnose as diagnose_cmd

@app.command("diagnose", help="Diagnose CLAUDE.md / RULES.json / ACTIVATION.md / hook / API key state.")
def diagnose(
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Include extra detail."),
) -> None:
    raise typer.Exit(code=diagnose_cmd.run(json_output=json_output, verbose=verbose))
```

**Acceptance:** `cheap diagnose --help` lists the command and flags;
`cheap diagnose` runs end-to-end with no MCP / network deps.

---

### B5.3. Tests

**File:** `tests/test_diagnose.py` (new)

**Test cases:**
1. `test_diagnose_all_present_passes` — temporary `home` with valid
   v9.0 CLAUDE.md, RULES.json, ACTIVATION.md, settings.json with hook,
   config with mock API key → exit 0, all `PASS`.
2. `test_diagnose_claude_md_missing_fails` — missing CLAUDE.md → exit 1,
   first check is `FAIL`.
3. `test_diagnose_v8_claude_md_warns` — CLAUDE.md with `Version: 8.0` →
   exit 0, claude.md check is `WARN` with upgrade hint substring.
4. `test_diagnose_settings_missing_fails` — missing settings.json → exit 1,
   hook check is `FAIL`.
5. `test_diagnose_hook_soft_mode_warns` — settings.json with soft hook →
   hook check is `WARN`.
6. `test_diagnose_invalid_rules_json_warns` — RULES.json present but
   invalid JSON → `WARN` not `FAIL` (it's optional infra).
7. `test_diagnose_json_output_is_valid_json` — `--json` output parses
   as a JSON list of objects with `name/status/detail` keys.
8. `test_diagnose_does_not_print_api_key` — config has a fake key like
   `sk-test-DO-NOT-LEAK`; assert this literal substring is absent
   from both default and `--verbose` output.
9. `test_diagnose_verbose_includes_extras` — `-v` adds at least one
   detail line that the non-verbose run does not.

**Acceptance:** all 9 tests pass; security test #8 is non-negotiable.

---

## 5. Implementation order (dependencies)

```
A5 (versioning foundation)
  └─→ A1 (v9.0 detection — uses regex constants)
        └─→ A2 (marker disambiguation)
              └─→ A3 (template v=3 — uses CHEAP_LLM_VERSION)
                    └─→ A4 (hook message — independent but small)
                          └─→ A6 (level-A tests)
                                └─→ B5.1 + B5.2 (diagnose command — uses A5 versioning)
                                      └─→ B5.3 (diagnose tests)
                                            └─→ Final pytest run (all green)
                                                  └─→ Bump pyproject to 0.8.0, commit
```

**Estimated effort:**
- Level A: ~3-4h coding + ~1h test/iteration.
- B#5: ~1.5-2h coding + ~30min tests.
- **Total: ~6-7h** of focused work.

---

## 6. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Marker regex change breaks existing v=2 installs | Medium | High | A2's `_LEGACY_HEADING_RE` keeps v=1/v=2 detection; explicit test `test_install_rule_v2_to_v3_upgrade_path` |
| `_looks_like_v9_native()` false-positives on user's project-local CLAUDE.md that happens to mention "ABSOLUTE PRE-FLIGHT" | Low | Medium | Combined check requires PRE-FLIGHT *and* absence of our marker; user can use `--force-overwrite-v9-native` |
| Trimmed v=3 template missing prose users relied on | Low | Low | Content is in v9.0 CLAUDE.md natively; project-local AGENTS.md (Codex) gets a leaner version anyway |
| `importlib.metadata.version()` fails in editable installs without re-install | Medium | Low | Fallback `"0.0.0+local"`; documented; tests cover both paths |
| `cheap diagnose` leaks API key | Low | **Critical** | Test #8 (non-negotiable); reuse `redact_secrets()`; never print raw key |
| Hook message length growth breaks downstream parsers | Low | Low | First-line wording preserved (test asserts substrings, not full match) |
| pyproject version bump 0.7.0 → 0.8.0 surprises CI | Low | Low | Documented in commit message; CHANGELOG.md update if file exists |

---

## 7. Verification (definition of done)

Before declaring level A + B#5 complete:

1. `pytest -q` — all tests green, including 11 new level-A tests +
   9 new B5 tests = 20 new tests minimum.
2. `cheap version` — prints `cheap-llm-router 0.8.0 (rule template v=3)`.
3. `cheap diagnose` — runs end-to-end on the developer's own machine,
   exits 0 if everything is configured.
4. `cheap install-rule` on a real `~/.claude/CLAUDE.md` (v9.0) —
   prints skip message, file unchanged.
5. `cheap install-rule --target codex` (or against an empty fixture
   AGENTS.md) — emits new v=3 block correctly.
6. Manual smoke: trigger PreToolUse hook (multi-Read scenario) —
   block message contains `"PRE-FLIGHT #3"`.
7. `git status` clean except for the changes in this plan;
   no accidental edits to forbidden files
   (`commands/read.py`, `client.py`, `transcript/*`).
8. TQMemory note saved (`kind=lesson`) summarizing key decisions
   (marker scheme, v9.0 detection heuristic, `cheap diagnose` checks).

---

## 8. Files touched (summary)

**Modified:**
- `pyproject.toml` (version bump)
- `src/cheap_llm/__init__.py` (version + RULE_TEMPLATE_VERSION)
- `src/cheap_llm/cli.py` (+ version, + diagnose subcommands)
- `src/cheap_llm/commands/install_rule.py` (v9 detection, marker disambiguation, template v3)
- `src/cheap_llm/_data/rule_template.md` (v=3 slimmed body)
- `src/cheap_llm/hook_pretool_read.py` (block messages)
- `tests/test_install_rule.py` (extend with v9 + v3 cases)
- `tests/test_hook_pretool_read.py` (extend with PRE-FLIGHT #3 assertion)

**Created:**
- `src/cheap_llm/commands/diagnose.py`
- `tests/test_diagnose.py`
- `tests/test_version.py`
- `tests/test_v9_integration.py`

**Forbidden — not touched:**
- `src/cheap_llm/commands/read.py`
- `src/cheap_llm/client.py`
- `src/cheap_llm/transcript/*`

---

## 9. Decisions locked in (2026-05-07)

The five originally-open questions are decided as follows. Implementation
proceeds against these.

1. **Escape-hatch — env var, not a flag.**
   v9.0-native overwrite requires **both** `CHEAP_FORCE_V9_OVERWRITE=1`
   environment variable **and** the `--force` CLI flag.
   Rationale: harder to trigger accidentally; symmetric with existing
   `CHEAP_HOOK_*` env-var pattern; keeps CLI surface clean.
   Implementation: in `install_rule.py`, after the v9 fingerprint
   check, also test `os.environ.get("CHEAP_FORCE_V9_OVERWRITE") == "1"
   and force` before allowing the overwrite path.

2. **Version bump to 0.8.0.**
   Marker v=2→v=3 plus new "skip on v9-native" default behavior is
   user-observable. Pre-1.0 semver convention: minor bump for
   feature + behavior changes. 0.7.1 would mislead.

3. **`cheap diagnose` exit code — exit 1 only on FAIL.**
   `WARN` and `INFO` count as success (exit 0). Diagnose is a
   troubleshooting tool, not a CI gate. A `--strict` flag can be
   added later if a real CI use case appears (YAGNI for now).

4. **`cheap version` — plain text default plus `--short` flag.**
   - Default: `cheap-llm-router 0.8.0 (rule template v=3)`
   - `--short`: `0.8.0` (pipe-friendly, e.g. `$(cheap version --short)`).

5. **Template trimming — ~50%, explicit keep/drop list.**

   **KEEP (still adds value when v9.0 native is absent, e.g. Codex AGENTS.md):**
   - Default-Flip rule statement + 4 native-Read exception bullets
   - Sources → commands table (`cheap read`, `cheap extract`)
   - Compaction signal (terse, 1 paragraph)
   - Hard security rule (NEVER pass `.env`, `*.key`, etc.)
   - Past-mistakes stub (project-specific user-filled examples)
   - `{STATUSLINE_BLOCK}` (agent-specific)

   **DROP (already in v9.0 native CLAUDE.md, or low-signal):**
   - "Pre-Read sanity" verbose self-talk paragraph
   - "Honest priors" philosophical block
   - Multi-step compaction-trigger walkthrough (the 5-step recipe)
   - Cost rationale paragraph (`~$0.04 per pass` vs `~$0.001`)
   - "IMPORTANT — `cheap extract` does NOT shrink context" note
   - Verbose `Self-check #1` / `JSONL_PATH_CMD` block

---

## 10. Next session — execution checklist

When user gives ОК on this plan:

- [ ] Create branch `v9-integration` (optional — user may prefer trunk).
- [ ] A5: implement `__init__.py` versioning + `cheap version`.
- [ ] A1: add `_looks_like_v9_native` + skip path.
- [ ] A2: tighten marker detection.
- [ ] A3: rewrite `rule_template.md` for v=3.
- [ ] A4: refresh hook block messages.
- [ ] A6: add level-A tests.
- [ ] Run `pytest -q` — green.
- [ ] B5.1: implement `commands/diagnose.py`.
- [ ] B5.2: wire into `cli.py`.
- [ ] B5.3: add diagnose tests.
- [ ] Run `pytest -q` — green.
- [ ] Manual smoke (`cheap install-rule` on real CLAUDE.md, `cheap diagnose`).
- [ ] Bump `pyproject.toml` to 0.8.0 (or 0.7.1 per Q#2 above).
- [ ] Commit per logical chunk (A5, A1, A2, A3, A4, A6, B5).
- [ ] Save TQMemory lesson note.

— end of plan —
