# SXR-AUD-012: Negative row limits are accepted inconsistently

P3 · Open · Audited working tree based on `48b11c6`

A malformed calculated limit silently changes output instead of reporting the mistake.

**Expected:** A negative row count is a usage error, as already enforced by find and skills.

**Observed:** list, show, prompts, errors, tools, stats and cmds all accept -n -1 and exit 0. Some slice off a row, some emit none and some ignore the value.

**Requirement basis:** Inferred consistency requirement with existing find/skills validation

Reproduce from the repository root. The harness uses temporary synthetic files and records each CLI exit code, stdout and stderr. A failing contract makes the harness exit 1.

```bash
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check USAGE-negative-limit- --output /private/tmp/sxr-audit-repro.json
```

| Check | Recorded result |
|---|---|
| `USAGE-negative-limit-list` | AssertionError: expected exit 2; got 0:  |
| `USAGE-negative-limit-show` | AssertionError: expected exit 2; got 0:  |
| `USAGE-negative-limit-prompts` | AssertionError: expected exit 2; got 0:  |
| `USAGE-negative-limit-errors` | AssertionError: expected exit 2; got 0:  |
| `USAGE-negative-limit-tools` | AssertionError: expected exit 2; got 0:  |
| `USAGE-negative-limit-stats` | AssertionError: expected exit 2; got 0:  |
| `USAGE-negative-limit-cmds` | AssertionError: expected exit 2; got 0:  |

Recorded CLI calls (fixture paths are placeholders):

| Command | Exit |
|---|---|
| `sxr list -n -1 --file '<fixture-root>/claude/projects/-sxr-audit-project/aaa-main.jsonl'` | 0 |
| `sxr show -n -1 --file '<fixture-root>/claude/projects/-sxr-audit-project/aaa-main.jsonl'` | 0 |
| `sxr prompts -n -1 --file '<fixture-root>/claude/projects/-sxr-audit-project/aaa-main.jsonl'` | 0 |
| `sxr errors -n -1 --file '<fixture-root>/claude/projects/-sxr-audit-project/aaa-main.jsonl'` | 0 |
| `sxr tools -n -1 --file '<fixture-root>/claude/projects/-sxr-audit-project/aaa-main.jsonl'` | 0 |
| `sxr stats -n -1 --file '<fixture-root>/claude/projects/-sxr-audit-project/aaa-main.jsonl'` | 0 |
| `sxr cmds -n -1 --file '<fixture-root>/claude/projects/-sxr-audit-project/aaa-main.jsonl'` | 0 |

Full output is retained under the check IDs in [contracts.json](../evidence/contracts.json).

Source locations:

- [src/sxr/flags.py:66](../../../src/sxr/flags.py#L66) `merge`
- [src/sxr/flags.py:19](../../../src/sxr/flags.py#L19) `LimitF`

Acceptance criteria:

- [ ] Validate shared limits centrally as integers >= 0.
- [ ] Apply validation at every supported flag position.
- [ ] Retain the documented zero meaning.

Feature IDs: `CLI-NEGATIVE-LIMIT`
