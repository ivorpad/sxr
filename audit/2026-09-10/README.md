# sxr CLI feature audit

Audited the current 0.12.2 working tree at `48b11c6cf08200de363e108924e42fdbc52d83e8` on 2026-09-10, including its pre-existing edits. Mapped **143 expected behaviors**: 122 passed their linked checks, 18 have a confirmed discrepancy, and 3 remain unverified. There are **17 issue reports**. Application source, tests and existing edits were preserved.

- [Feature map, JSON](features.json): expectations, statuses, issue IDs, exact test cases, parser metadata and environment.
- [Feature map, CSV](features.csv): filter by area, status or issue ID.
- [Issue data, JSON](issues.json): reproducible findings and acceptance criteria.
- [CLI surface](cli-surface.json): 288 parameter entries across 21 parser surfaces, including both fast parsers and the hidden audit alias. Every entry links to a feature.

The existing suite has **542 passing cases**. Its first sandboxed run passed 538 and failed four worker tests because the sandbox denied Unix socket binding. All seven worker tests passed when run with temporary socket access. Those four environmental failures are not CLI defects.

The additional subprocess audit ran **67 contracts**: 37 passed and 30 failed. Those failures are grouped into 16 runtime reports; one further report documents the empty-list exit-code exception. Tests cover synthetic Claude/Codex files, cache changes, skill maps, primer files and credential-shaped fixture values. No real transcripts were cleaned.

A new macOS arm64 bundle was built from this working tree and passed the repository's relocation verification with an empty PATH. The native tests also covered worker reuse, fallback, concurrent startup, idle expiry and caller settings. Formatting, lint and repository conventions passed. See [external checks](evidence/external-checks.json), [suite results](evidence/pytest.xml), [worker rerun](evidence/worker.xml), [subprocess evidence](evidence/contracts.json) and [bundle verification](evidence/bundle.log).

Passing a row means its linked checks passed, not proof for every possible input. The Linux/x86_64 and older-OS compatibility matrix, Homebrew installation/upgrade, and historical performance benchmarks were not verified. These are explicitly marked in the map. Inferred consistency expectations, such as negative limits and --tail 0, are identified in their reports.

| Issue | Priority | Finding |
|---|---|---|
| [SXR-AUD-001](issues/SXR-AUD-001.md) | P1 | Secret audit misses credentials in Write tool contents |
| [SXR-AUD-002](issues/SXR-AUD-002.md) | P2 | Time filters compare timestamp strings instead of instants |
| [SXR-AUD-003](issues/SXR-AUD-003.md) | P2 | Counted Claude API errors disappear from the errors view |
| [SXR-AUD-004](issues/SXR-AUD-004.md) | P2 | Normalized find matches can produce excerpts with no matching text |
| [SXR-AUD-005](issues/SXR-AUD-005.md) | P2 | show, prompts and errors ignore row limits in JSON mode |
| [SXR-AUD-006](issues/SXR-AUD-006.md) | P2 | errors applies text limits per session and hides omissions |
| [SXR-AUD-007](issues/SXR-AUD-007.md) | P2 | tools, stats, path and clean accept but ignore -n |
| [SXR-AUD-008](issues/SXR-AUD-008.md) | P2 | --full still trims long transcript text |
| [SXR-AUD-009](issues/SXR-AUD-009.md) | P2 | Skill input counts multiply when calls share a record |
| [SXR-AUD-010](issues/SXR-AUD-010.md) | P2 | Empty show selections exit successfully only in text mode |
| [SXR-AUD-011](issues/SXR-AUD-011.md) | P3 | --tail 0 returns the entire selected transcript |
| [SXR-AUD-012](issues/SXR-AUD-012.md) | P3 | Negative row limits are accepted inconsistently |
| [SXR-AUD-013](issues/SXR-AUD-013.md) | P2 | path and secrets clean accept --json but emit plain text |
| [SXR-AUD-014](issues/SXR-AUD-014.md) | P2 | Limited secret worklists understate the number of findings |
| [SXR-AUD-015](issues/SXR-AUD-015.md) | P2 | A non-object JSONL record crashes transcript reads |
| [SXR-AUD-016](issues/SXR-AUD-016.md) | P3 | Primer filesystem failures escape as Python tracebacks |
| [SXR-AUD-017](issues/SXR-AUD-017.md) | P3 | The documented empty-result exit code omits the list exception |

Start with SXR-AUD-001: the audit can miss a credential that the clean preview detects. Time filtering and missing error records also affect which historical evidence an agent can retrieve.

Re-run the extra contracts from the repository root:

```bash
rtk proxy .venv/bin/python audit/2026-09-10/verify_cli.py --output /private/tmp/sxr-audit-contracts.json
```

Use `--check CHECK-ID` to reproduce one check or ID prefix. The harness returns 1 while any selected contract fails; it does not apply fixes. Each issue supplies a narrower command.

[feature-specifications.psv](feature-specifications.psv) is the editable expectation catalogue. [issue-specifications.json](issue-specifications.json) holds report text. `build_report.py` rebuilds JSON, CSV and Markdown from saved evidence, validates all references, checks that every failed contract has a report, and refuses to reuse evidence after audited source changes. Fresh checks and a fresh baseline are required after fixing the CLI.

Priorities: P1 means a false-clean credential audit; P2 covers incorrect results, missing evidence and broken output contracts; P3 covers validation boundaries, diagnostics or documentation.
