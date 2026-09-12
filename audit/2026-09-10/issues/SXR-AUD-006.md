# SXR-AUD-006: errors applies text limits per session and hides omissions

P2 · Open · Audited working tree based on `48b11c6`

Range scans exceed the requested budget and users can mistake a shortened list for the complete set of failures.

**Expected:** The errors -n limit applies to the entire selected scope and a shortened view states the omitted count.

**Observed:** errors @1:@2 -n 1 prints two error rows. A single session with two errors prints one row but only reports a total of two errors, without stating one row was omitted.

**Requirement basis:** README and CLI help

Reproduce from the repository root. The harness uses temporary synthetic files and records each CLI exit code, stdout and stderr. A failing contract makes the harness exit 1.

```bash
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check LIMIT-errors-scope --output /private/tmp/sxr-audit-repro.json
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check LIMIT-errors-notice --output /private/tmp/sxr-audit-repro.json
```

| Check | Recorded result |
|---|---|
| `LIMIT-errors-scope` | AssertionError: -n 1 printed 2 error rows |
| `LIMIT-errors-notice` | AssertionError: omitted error row has no truncation notice |

Recorded CLI calls (fixture paths are placeholders):

| Command | Exit |
|---|---|
| `sxr errors @1:@2 -n 1 --path /sxr-audit-project` | 0 |
| `sxr errors -n 1 --file '<fixture-root>/claude/projects/-sxr-audit-project/aaa-main.jsonl'` | 0 |

Full output is retained under the check IDs in [contracts.json](../evidence/contracts.json).

Source locations:

- [src/sxr/views_read.py:246](../../../src/sxr/views_read.py#L246) `errors`

Acceptance criteria:

- [ ] Track a scope-wide emitted-row count.
- [ ] Show a precise omitted-record notice.
- [ ] Cover multi-session and single-session limits.

Feature IDs: `ERRORS-LIMIT`
