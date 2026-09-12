# SXR-AUD-007: tools, stats, path and clean accept but ignore -n

P2 · Open · Audited working tree based on `48b11c6`

The shared option appears valid while providing no control over these outputs.

**Expected:** Commands that advertise a printed-row limit honor it, or reject an unsupported option.

**Observed:** With -n 1, tools prints two tool rows, stats prints 17 field rows, and path prints both parent and child paths. A clean preview also prints both selected file rows with -n 1.

**Requirement basis:** README and CLI help

Reproduce from the repository root. The harness uses temporary synthetic files and records each CLI exit code, stdout and stderr. A failing contract makes the harness exit 1.

```bash
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check LIMIT-tools --output /private/tmp/sxr-audit-repro.json
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check LIMIT-stats --output /private/tmp/sxr-audit-repro.json
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check LIMIT-path --output /private/tmp/sxr-audit-repro.json
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check LIMIT-clean --output /private/tmp/sxr-audit-repro.json
```

| Check | Recorded result |
|---|---|
| `LIMIT-tools` | AssertionError: -n 1 printed 2 tool rows |
| `LIMIT-stats` | AssertionError: -n 1 printed 17 stat rows |
| `LIMIT-path` | AssertionError: -n 1 printed both parent and child paths |
| `LIMIT-clean` | AssertionError: clean -n 1 printed 2 file rows |

Recorded CLI calls (fixture paths are placeholders):

| Command | Exit |
|---|---|
| `sxr tools -n 1 --file '<fixture-root>/claude/projects/-sxr-audit-project/aaa-main.jsonl'` | 0 |
| `sxr stats -n 1 --file '<fixture-root>/claude/projects/-sxr-audit-project/aaa-main.jsonl'` | 0 |
| `sxr path aaa-main -n 1 --path /sxr-audit-project` | 0 |
| `sxr secrets clean -n 1 --path /sxr-audit-project` | 0 |

Full output is retained under the check IDs in [contracts.json](../evidence/contracts.json).

Source locations:

- [src/sxr/cli.py:139](../../../src/sxr/cli.py#L139) `tools`
- [src/sxr/cli.py:156](../../../src/sxr/cli.py#L156) `stats`
- [src/sxr/cli.py:174](../../../src/sxr/cli.py#L174) `path_cmd`
- [src/sxr/secrets_commands.py:53](../../../src/sxr/secrets_commands.py#L53) `clean_cmd`

Acceptance criteria:

- [ ] Implement consistent row limits with omission notices or remove unsupported command options.
- [ ] Preserve explicit-file scope and unlimited zero semantics.

Feature IDs: `OUTPUT-LIMIT-AGGREGATES`
