# SXR-AUD-010: Empty show selections exit successfully only in text mode

P2 · Open · Audited working tree based on `48b11c6`

Scripts that use the documented exit code treat missing evidence as a successful result.

**Expected:** An empty selection returns exit 1 regardless of output format.

**Observed:** show --type does-not-exist exits 0, while the same command with --json exits 1.

**Requirement basis:** README and CLI help

Reproduce from the repository root. The harness uses temporary synthetic files and records each CLI exit code, stdout and stderr. A failing contract makes the harness exit 1.

```bash
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check SHOW-empty --output /private/tmp/sxr-audit-repro.json
```

| Check | Recorded result |
|---|---|
| `SHOW-empty` | AssertionError: empty selection exits text=0, JSON=1 |

Recorded CLI calls (fixture paths are placeholders):

| Command | Exit |
|---|---|
| `sxr show --type does-not-exist --file '<fixture-root>/claude/projects/-sxr-audit-project/aaa-main.jsonl'` | 0 |
| `sxr show --type does-not-exist --json --file '<fixture-root>/claude/projects/-sxr-audit-project/aaa-main.jsonl'` | 1 |

Full output is retained under the check IDs in [contracts.json](../evidence/contracts.json).

Source locations:

- [src/sxr/views_read.py:141](../../../src/sxr/views_read.py#L141) `show`

Acceptance criteria:

- [ ] Return the same empty-result status for text and JSON.
- [ ] Check empty type, range and around selections.

Feature IDs: `SHOW-EMPTY`
