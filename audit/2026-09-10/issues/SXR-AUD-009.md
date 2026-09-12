# SXR-AUD-009: Skill input counts multiply when calls share a record

P2 · Open · Audited working tree based on `48b11c6`

Per-skill usage reports overcount batched tool calls.

**Expected:** Two Skill blocks calling notify and review produce one input count for each.

**Observed:** calls reports Skill=2, but skill_inputs reports notify=2 and review=2. Each Skill event rescans all tool_use blocks in the original physical record.

**Requirement basis:** README and CLI help

Reproduce from the repository root. The harness uses temporary synthetic files and records each CLI exit code, stdout and stderr. A failing contract makes the harness exit 1.

```bash
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check TOOLS-skill-count --output /private/tmp/sxr-audit-repro.json
```

| Check | Recorded result |
|---|---|
| `TOOLS-skill-count` | AssertionError: each Skill input counted more than once: {'notify': 2, 'review': 2} |

Recorded CLI calls (fixture paths are placeholders):

| Command | Exit |
|---|---|
| `sxr tools --json --file '<fixture-root>/extras/skill-calls.jsonl'` | 0 |

Full output is retained under the check IDs in [contracts.json](../evidence/contracts.json).

Source locations:

- [src/sxr/views_info.py:93](../../../src/sxr/views_info.py#L93) `tools_view`

Acceptance criteria:

- [ ] Associate each event with its own input block or count each physical block once.
- [ ] Test two Skill calls plus an unrelated tool in the same record.

Feature IDs: `TOOLS-SKILL-INPUTS`
