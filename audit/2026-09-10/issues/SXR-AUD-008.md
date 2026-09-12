# SXR-AUD-008: --full still trims long transcript text

P2 · Open · Audited working tree based on `48b11c6`

An agent following the documented recovery flag still loses content.

**Expected:** --full prints whole text, as both the help epilog and agent primer state.

**Observed:** show --full trims a synthetic user message larger than the default 40,000-character scan budget. --around correctly preserves the full text.

**Requirement basis:** README and CLI help

Reproduce from the repository root. The harness uses temporary synthetic files and records each CLI exit code, stdout and stderr. A failing contract makes the harness exit 1.

```bash
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --check SHOW-full --output /private/tmp/sxr-audit-repro.json
```

| Check | Recorded result |
|---|---|
| `SHOW-full` | AssertionError: --full trimmed the 64017-character text |

Recorded CLI calls (fixture paths are placeholders):

| Command | Exit |
|---|---|
| `sxr show --full --file '<fixture-root>/extras/long.jsonl'` | 0 |

Full output is retained under the check IDs in [contracts.json](../evidence/contracts.json).

Source locations:

- [src/sxr/views_read.py:44](../../../src/sxr/views_read.py#L44) `_base_selection`
- [src/sxr/views_read.py:141](../../../src/sxr/views_read.py#L141) `show`
- [src/sxr/onboard.py:12](../../../src/sxr/onboard.py#L12) `EPILOG`

Acceptance criteria:

- [ ] Treat --full as disabling text trimming, or consistently change the published contract.
- [ ] Add a long-record CLI check distinct from ordinary full-kind selection.

Feature IDs: `SHOW-FULL`
