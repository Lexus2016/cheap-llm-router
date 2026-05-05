## Cheap LLM delegation

When reading 3+ files only for context (not to edit), prefer
`cheap read F1 F2 ... -q "question"` (returns ~600-token summary).
Skip when: editing those files, non-trivial debugging,
security-sensitive code (auth/crypto/secrets/input validation),
architectural decisions, cross-file refactor.
NEVER pass files that may contain secrets (`.env`, `*.key`,
credentials, private certs) and NEVER use `--include-sensitive` to
bypass the guard for an LLM call. The guard exists to catch
mistakes; bypassing it sends secrets to a third party.
When unsure → don't delegate.
