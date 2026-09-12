# SXR-AUD-015: A non-object JSONL record crashes transcript reads

P2 · Open · Audited working tree based on `48b11c6`

One malformed record can make otherwise readable session evidence inaccessible and is reported using the documented empty-result exit code.

**Expected:** A structurally invalid record is skipped or reported through a controlled error without losing source-coordinate integrity.

**Observed:** A valid user record followed by JSON number 42 makes show --full exit 1 with an AttributeError traceback rather than a diagnostic.

**Requirement basis:** Resilience expectation based on supported malformed/torn JSONL handling

Reproduce from the repository root. The harness uses temporary synthetic files and records each CLI exit code, stdout and stderr. A failing contract makes the harness exit 1.

```bash
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check USAGE-invalid-json-record --output /private/tmp/sxr-audit-repro.json
```

| Check | Recorded result |
|---|---|
| `USAGE-invalid-json-record` | AssertionError: non-object JSON record crashes with exit 1 |

Recorded CLI calls (fixture paths are placeholders):

| Command | Exit |
|---|---|
| `sxr show --full --file '<fixture-root>/extras/invalid-shape.jsonl'` | 1 |

Full output is retained under the check IDs in [contracts.json](../evidence/contracts.json).

Source locations:

- [src/sxr/providers/claude_code.py:34](../../../src/sxr/providers/claude_code.py#L34) `_iter_records`
- [src/sxr/providers/claude_code.py:105](../../../src/sxr/providers/claude_code.py#L105) `_record_events`

Acceptance criteria:

- [ ] Validate decoded record shapes before accessing mapping fields.
- [ ] Keep later valid records readable or clearly mark the read incomplete.
- [ ] Apply the same policy to both providers and cache parsing.

Feature IDs: `CLI-RECORD-ERROR`
