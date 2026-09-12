# SXR-AUD-013: path and secrets clean accept --json but emit plain text

P2 · Open · Audited working tree based on `48b11c6`

Automation piping a clean preview to a JSON reader fails despite using an accepted flag.

**Expected:** An accepted --json option emits structured output, or the command rejects the unsupported option.

**Observed:** The clean command advertises --json, accepts it and exits 0, but stdout contains a TSV header, data row and dry-run prose. path --json likewise accepts the option and returns a plain pathname.

**Requirement basis:** README and CLI help

Reproduce from the repository root. The harness uses temporary synthetic files and records each CLI exit code, stdout and stderr. A failing contract makes the harness exit 1.

```bash
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check FORMAT-clean-json --output /private/tmp/sxr-audit-repro.json
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check FORMAT-path-json --output /private/tmp/sxr-audit-repro.json
```

| Check | Recorded result |
|---|---|
| `FORMAT-clean-json` | AssertionError: secrets clean --json accepts the flag but emits TSV and prose |
| `FORMAT-path-json` | AssertionError: path --json accepts the flag but emits a plain pathname |

Recorded CLI calls (fixture paths are placeholders):

| Command | Exit |
|---|---|
| `sxr secrets clean --json --file '<fixture-root>/extras/clean-json.jsonl'` | 0 |
| `sxr path --json --file '<fixture-root>/claude/projects/-sxr-audit-project/aaa-main.jsonl'` | 0 |

Full output is retained under the check IDs in [contracts.json](../evidence/contracts.json).

Source locations:

- [src/sxr/secrets_commands.py:53](../../../src/sxr/secrets_commands.py#L53) `clean_cmd`
- [src/sxr/secrets/clean.py:116](../../../src/sxr/secrets/clean.py#L116) `clean_view`
- [src/sxr/cli.py:174](../../../src/sxr/cli.py#L174) `path_cmd`

Acceptance criteria:

- [ ] Implement JSON output for preview/apply results or reject the flag clearly.
- [ ] Keep diagnostics separate and credential values masked.

Feature IDs: `FORMAT-CLEAN-JSON`, `FORMAT-PATH-JSON`
