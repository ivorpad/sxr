# SXR-AUD-004: Normalized find matches can produce excerpts with no matching text

P2 · Open · Audited working tree based on `48b11c6`

Agents receive a correctly matched session with evidence that does not demonstrate why it matched.

**Expected:** The excerpt for a normalized match shows the original source occurrence, including diacritic-insensitive matches.

**Observed:** Query cafe matches a long event ending in café, but the returned excerpt contains only its leading padding. The match lies beyond the excerpt because position lookup uses unnormalized substring search.

**Requirement basis:** README and CLI help

Reproduce from the repository root. The harness uses temporary synthetic files and records each CLI exit code, stdout and stderr. A failing contract makes the harness exit 1.

```bash
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check FIND-unicode-evidence --output /private/tmp/sxr-audit-repro.json
```

| Check | Recorded result |
|---|---|
| `FIND-unicode-evidence` | AssertionError: returned excerpt contains no occurrence of the matched café |

Recorded CLI calls (fixture paths are placeholders):

| Command | Exit |
|---|---|
| `sxr find cafe --json --file '<fixture-root>/extras/accent.jsonl'` | 0 |

Full output is retained under the check IDs in [contracts.json](../evidence/contracts.json).

Source locations:

- [src/sxr/find_query.py:25](../../../src/sxr/find_query.py#L25) `_excerpt`

Acceptance criteria:

- [ ] Locate excerpt spans using tokenization compatible with ranked matching.
- [ ] Retain a mapping to original source character positions.
- [ ] Test long events with diacritics and normalization differences.

Feature IDs: `FIND-EVIDENCE`
