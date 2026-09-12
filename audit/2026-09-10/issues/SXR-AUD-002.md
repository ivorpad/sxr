# SXR-AUD-002: Time filters compare timestamp strings instead of instants

P2 · Open · Audited working tree based on `48b11c6`

Searches can omit the requested historical sessions or include sessions outside a time boundary.

**Expected:** Session membership follows the UTC half-open interval [since, before), independent of timestamp precision and offset spelling.

**Observed:** A session at 12:00:00.123Z is excluded by --before 12:00:00.123001Z. A session at 13:00:00+02:00 is excluded by --before 12:00:00Z even though it started at 11:00 UTC.

**Requirement basis:** README and CLI help

Reproduce from the repository root. The harness uses temporary synthetic files and records each CLI exit code, stdout and stderr. A failing contract makes the harness exit 1.

```bash
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check TIME-fraction --output /private/tmp/sxr-audit-repro.json
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check TIME-offset --output /private/tmp/sxr-audit-repro.json
```

| Check | Recorded result |
|---|---|
| `TIME-fraction` | AssertionError: a session one microsecond before the bound was excluded |
| `TIME-offset` | AssertionError: 11:00 UTC was excluded by --before 12:00 UTC |

Recorded CLI calls (fixture paths are placeholders):

| Command | Exit |
|---|---|
| `sxr list --before 2026-08-01T12:00:00.123001Z --json --file '<fixture-root>/extras/fraction.jsonl'` | 0 |
| `sxr list --before 2026-08-01T12:00:00Z --json --file '<fixture-root>/extras/offset.jsonl'` | 0 |

Full output is retained under the check IDs in [contracts.json](../evidence/contracts.json).

Source locations:

- [src/sxr/handles.py:97](../../../src/sxr/handles.py#L97) `_stamp`
- [src/sxr/handles.py:122](../../../src/sxr/handles.py#L122) `window`

Acceptance criteria:

- [ ] Normalize both stored timestamps and bounds before comparing.
- [ ] Check inclusive since and exclusive before for equivalent offsets and mixed fractional precision.
- [ ] Preserve @N and today semantics.

Feature IDs: `TIME-WINDOW`
