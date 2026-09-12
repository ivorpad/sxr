# SXR-AUD-003: Counted Claude API errors disappear from the errors view

P2 · Open · Audited working tree based on `48b11c6`

The aggregate error count points to a failure that the dedicated error view cannot retrieve.

**Expected:** A Claude isApiErrorMessage record counted as an error can be inspected with errors and show --errors.

**Observed:** list --json reports errors=1 for the fixture, while errors --json returns no records and exits 1.

**Requirement basis:** Consistency between counted record properties and the errors command

Reproduce from the repository root. The harness uses temporary synthetic files and records each CLI exit code, stdout and stderr. A failing contract makes the harness exit 1.

```bash
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check ERRORS-api-error --output /private/tmp/sxr-audit-repro.json
```

| Check | Recorded result |
|---|---|
| `ERRORS-api-error` | AssertionError: expected exit 0; got 1: no error records in api-erro  |

Recorded CLI calls (fixture paths are placeholders):

| Command | Exit |
|---|---|
| `sxr list --json --file '<fixture-root>/extras/api-error.jsonl'` | 0 |
| `sxr errors --json --file '<fixture-root>/extras/api-error.jsonl'` | 1 |

Full output is retained under the check IDs in [contracts.json](../evidence/contracts.json).

Source locations:

- [src/sxr/providers/claude_code.py:105](../../../src/sxr/providers/claude_code.py#L105) `_record_events`
- [src/sxr/providers/claude_code.py:177](../../../src/sxr/providers/claude_code.py#L177) `_summarize`
- [src/sxr/views_read.py:246](../../../src/sxr/views_read.py#L246) `errors`

Acceptance criteria:

- [ ] Carry isApiErrorMessage into canonical error annotations.
- [ ] Return the original failed record in errors and show --errors.
- [ ] Keep list and stats error counts consistent.

Feature IDs: `ERRORS-API`
