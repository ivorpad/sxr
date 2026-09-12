# SXR-AUD-016: Primer filesystem failures escape as Python tracebacks

P3 · Open · Audited working tree based on `48b11c6`

Setup automation receives the empty/stale status for a real write error, with an unnecessarily long exception dump.

**Expected:** An invalid or unwritable destination returns a useful filesystem diagnostic with exit 2.

**Observed:** init --write not-a-directory/AGENTS.md, where not-a-directory is an existing regular file, exits 1 with a FileExistsError traceback.

**Requirement basis:** README and CLI help

Reproduce from the repository root. The harness uses temporary synthetic files and records each CLI exit code, stdout and stderr. A failing contract makes the harness exit 1.

```bash
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check INIT-file-error --output /private/tmp/sxr-audit-repro.json
```

| Check | Recorded result |
|---|---|
| `INIT-file-error` | AssertionError: invalid destination produces exit 1 and a Python traceback |

Recorded CLI calls (fixture paths are placeholders):

| Command | Exit |
|---|---|
| `sxr init --write '<fixture-root>/not-a-directory/AGENTS.md'` | 1 |

Full output is retained under the check IDs in [contracts.json](../evidence/contracts.json).

Source locations:

- [src/sxr/onboard.py:155](../../../src/sxr/onboard.py#L155) `install_primer`
- [src/sxr/onboard.py:260](../../../src/sxr/onboard.py#L260) `_apply`

Acceptance criteria:

- [ ] Catch relevant filesystem errors at the command boundary.
- [ ] Report the destination and error on stderr.
- [ ] Keep the original file intact.

Feature IDs: `INIT-IO-ERROR`
