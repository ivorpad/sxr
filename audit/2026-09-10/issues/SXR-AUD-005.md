# SXR-AUD-005: show, prompts and errors ignore row limits in JSON mode

P2 · Open · Audited working tree based on `48b11c6`

Consumers cannot bound these read responses and may load an entire large transcript unexpectedly.

**Expected:** -n 1 returns at most one JSONL record, keeping that record complete.

**Observed:** The fixtures return 7 records from show, 3 from prompts, and 2 from errors with --json -n 1. cmds honors the same combination.

**Requirement basis:** README and CLI help

Reproduce from the repository root. The harness uses temporary synthetic files and records each CLI exit code, stdout and stderr. A failing contract makes the harness exit 1.

```bash
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check LIMIT-json-show --output /private/tmp/sxr-audit-repro.json
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check LIMIT-json-prompts --output /private/tmp/sxr-audit-repro.json
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check LIMIT-json-errors --output /private/tmp/sxr-audit-repro.json
```

| Check | Recorded result |
|---|---|
| `LIMIT-json-show` | AssertionError: -n 1 printed 7 records |
| `LIMIT-json-prompts` | AssertionError: -n 1 printed 3 records |
| `LIMIT-json-errors` | AssertionError: -n 1 printed 2 records |

Recorded CLI calls (fixture paths are placeholders):

| Command | Exit |
|---|---|
| `sxr show --json -n 1 --file '<fixture-root>/claude/projects/-sxr-audit-project/aaa-main.jsonl'` | 0 |
| `sxr prompts --json -n 1 --file '<fixture-root>/claude/projects/-sxr-audit-project/aaa-main.jsonl'` | 0 |
| `sxr errors --json -n 1 --file '<fixture-root>/claude/projects/-sxr-audit-project/aaa-main.jsonl'` | 0 |

Full output is retained under the check IDs in [contracts.json](../evidence/contracts.json).

Source locations:

- [src/sxr/views_read.py:141](../../../src/sxr/views_read.py#L141) `show`
- [src/sxr/views_read.py:206](../../../src/sxr/views_read.py#L206) `prompts`
- [src/sxr/views_read.py:246](../../../src/sxr/views_read.py#L246) `errors`

Acceptance criteria:

- [ ] Apply row selection limits before JSON serialization.
- [ ] Keep returned records unmodified.
- [ ] Report omissions through stderr or a documented metadata channel.
- [ ] Verify -n 0 still returns all records.

Feature IDs: `OUTPUT-LIMIT-JSON`
