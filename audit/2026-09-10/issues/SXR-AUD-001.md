# SXR-AUD-001: Secret audit misses credentials in Write tool contents

P1 · Open · Audited working tree based on `48b11c6`

A rotation worklist can incorrectly report a clean session containing a stored credential. The same omission can affect other tool input fields hidden by the display summary.

**Expected:** The masked audit finds credentials stored in a recorded Write.content value.

**Observed:** The synthetic Write call contains a password assignment. secrets --json exits 1 with no finding. secrets clean previews one replacement in the same file.

**Requirement basis:** README and CLI help

Reproduce from the repository root. The harness uses temporary synthetic files and records each CLI exit code, stdout and stderr. A failing contract makes the harness exit 1.

```bash
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check SECRETS-write-input --output /private/tmp/sxr-audit-repro.json
```

| Check | Recorded result |
|---|---|
| `SECRETS-write-input` | AssertionError: audit exits 1 with no finding; clean detects the password |

Recorded CLI calls (fixture paths are placeholders):

| Command | Exit |
|---|---|
| `sxr secrets --json --file '<fixture-root>/extras/write-content.jsonl'` | 1 |
| `sxr secrets clean --file '<fixture-root>/extras/write-content.jsonl'` | 0 |

Full output is retained under the check IDs in [contracts.json](../evidence/contracts.json).

Source locations:

- [src/sxr/views_secrets.py:30](../../../src/sxr/views_secrets.py#L30) `secrets_view`
- [src/sxr/providers/claude_code.py:88](../../../src/sxr/providers/claude_code.py#L88) `_tool_arg`

Acceptance criteria:

- [ ] Scan relevant decoded record values rather than only display summaries.
- [ ] Keep credential values out of text and JSON output.
- [ ] Add a test asserting that audit and clean agree on this Write fixture.

Feature IDs: `SECRETS-SCAN`
