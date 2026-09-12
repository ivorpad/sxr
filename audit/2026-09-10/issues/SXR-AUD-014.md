# SXR-AUD-014: Limited secret worklists understate the number of findings

P2 · Open · Audited working tree based on `48b11c6`

A user can stop rotating credentials after the one displayed row because the summary hides the remaining finding.

**Expected:** A worklist limited with -n reports the full distinct count and number omitted.

**Observed:** Two different synthetic password values are detected. With -n 1, the footer says '1 distinct secrets' and provides no omitted-count notice.

**Requirement basis:** README and CLI help

Reproduce from the repository root. The harness uses temporary synthetic files and records each CLI exit code, stdout and stderr. A failing contract makes the harness exit 1.

```bash
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check LIMIT-secrets-notice --output /private/tmp/sxr-audit-repro.json
```

| Check | Recorded result |
|---|---|
| `LIMIT-secrets-notice` | AssertionError: two detected values are reported as '1 distinct secrets' with no omitted-count notice |

Recorded CLI calls (fixture paths are placeholders):

| Command | Exit |
|---|---|
| `sxr secrets -n 1 --file '<fixture-root>/extras/two-secrets.jsonl'` | 0 |

Full output is retained under the check IDs in [contracts.json](../evidence/contracts.json).

Source locations:

- [src/sxr/views_secrets.py:30](../../../src/sxr/views_secrets.py#L30) `secrets_view`

Acceptance criteria:

- [ ] Compute totals before slicing.
- [ ] Report shown, total and omitted counts.
- [ ] Keep returned fingerprints stable across limited and unlimited views.

Feature IDs: `SECRETS-LIMIT`
