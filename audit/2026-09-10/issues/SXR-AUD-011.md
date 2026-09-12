# SXR-AUD-011: --tail 0 returns the entire selected transcript

P3 · Open · Audited working tree based on `48b11c6`

A computed zero tail count can unexpectedly print a large transcript.

**Expected:** Last zero events produces an empty selection; only -n 0 is documented as unlimited.

**Observed:** Python's [-0:] slice returns the complete selection, so --tail 0 --json emits every skeleton record.

**Requirement basis:** Inferred boundary behavior from 'Last N selected events' and the separate -n 0 convention

Reproduce from the repository root. The harness uses temporary synthetic files and records each CLI exit code, stdout and stderr. A failing contract makes the harness exit 1.

```bash
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check SHOW-tail-zero --output /private/tmp/sxr-audit-repro.json
```

| Check | Recorded result |
|---|---|
| `SHOW-tail-zero` | AssertionError: --tail 0 returned the entire skeleton |

Recorded CLI calls (fixture paths are placeholders):

| Command | Exit |
|---|---|
| `sxr show --tail 0 --json --file '<fixture-root>/claude/projects/-sxr-audit-project/aaa-main.jsonl'` | 0 |

Full output is retained under the check IDs in [contracts.json](../evidence/contracts.json).

Source locations:

- [src/sxr/views_read.py:32](../../../src/sxr/views_read.py#L32) `_selected`

Acceptance criteria:

- [ ] Handle zero explicitly or reject it with documented usage guidance.
- [ ] Validate negative tail counts.
- [ ] Keep positive tail order unchanged.

Feature IDs: `SHOW-TAIL-ZERO`
