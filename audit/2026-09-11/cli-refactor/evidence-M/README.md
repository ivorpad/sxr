# evidence-M — the merge, the findings audit, and two upstream defects

Receipts for `SXR-MERGE-01` and `SXR-AUDIT-02`, 2026-09-12. The merge is
`d2021d9`; the pre-merge snapshot it was verified against is `../baseline-M/`.

| File | What it holds |
|---|---|
| `head.txt`, `history.txt`, `git-status.txt`, `stashes.txt`, `merge-parents.txt` | the git state after the merge |
| `post-merge-integrity.log` | all 1229 pre-merge files re-hashed immediately after the merge commit: 1229 OK, 0 failed, 0 missing |
| `final-integrity.log` | the same check after the findings audit: 1222 OK, 7 deliberately changed, 0 missing |
| `upstream-defects.json` | 12 invocations × 3 trees (`48b11c6c`, `8f93114`, this tree), from `../probe_upstream_defects.py` |
| `limit-unit.json` | 7 invocations × 3 trees plus all 18 `--help` surfaces compared between the refs, from `../probe_limit_unit.py` |
| `upstream-contracts.json` | the preserved 67-check contract suite run against all three trees, from `../probe_upstream_contracts.py` |
| `pytest.log`, `pytest.xml` | 951 passed, 0 failed |
| `ruff-check.log`, `ruff-format.log` | clean; 192 files formatted |
| `konpy.log` | 109 files, 0 violations, no suppressions |
| `historical-contracts.{log,json}` | 66 passed, 1 failed (`PROMPTS-filter`, by design) |
| `migrated-contracts.{log,json}` | 5 passed, 0 failed |
| `recaptures/{ranges,show,errors,cmds}/`, `*-capture.log` | slices 2 to 5 re-captured; all 158 files byte-identical to `evidence-B/recaptures/` |

## The merge changed no file

`git diff HEAD^1 HEAD` is empty: the merge commit's tree is identical to the work
commit's. Every conflict was resolved to this tree's content with
`git checkout HEAD -- .`, and the one file the merge would otherwise have added,
`src/sxr/prompt_catalog.py`, was removed deliberately under D-08. It still exists
in `HEAD^2` and can be read there.

`rerere.enabled` is `true` in `~/.gitconfig`, so the real merge was run with
`-c rerere.enabled=false`: nothing was auto-resolved from a cache, and no
resolution was written into this repository's `rr-cache`. The rehearsal clone in
`/tmp/merge-rehearsal` did record resolutions, in its own `.git`, and has been
removed.

## The seven files that differ from the pre-merge snapshot

None of them is a merge effect; all seven are the findings audit's own edits,
made after the merge commit and left uncommitted for review:

| File | Why |
|---|---|
| `src/sxr/prompt_command.py` | `prompts --help` now names the reversed published default (finding 6) |
| `README.md` | the migration note now says the reversal is of a released version Homebrew installs, not an internal draft (finding 6) |
| `src/sxr/primer_text.py` | the primer says the same in one clause (finding 6) |
| `CLAUDE.md` | this repo's own primer block reissued from that body, `init --check` reports up to date |
| `../verify_prompts.py` | the contract's recorded justification now states that `PROMPTS-filter` passes on the published release too |
| `../disposition.json` | 17 rows gained a findings-audit note; `upstream_defects` added |
| `../ledger.md` | D-11, the merge, the contract comparison, and the two upstream defects |

## Reproducing the upstream measurements

All three probes extract a ref with `git archive` into a temp directory and run
the repository venv's interpreter with `PYTHONPATH` pointed at it. No checkout,
no worktree, no index operation, and the installed `/opt/homebrew/bin/sxr` is
never invoked except to read its version.

```bash
cd /path/to/sxr/audit/2026-09-11/cli-refactor
uv run python probe_upstream_defects.py --output evidence-M/upstream-defects.json
uv run python probe_limit_unit.py --output evidence-M/limit-unit.json
uv run python probe_upstream_contracts.py --output evidence-M/upstream-contracts.json
```

`ruff format --check` counts Python inside markdown code blocks, so the file
count rises as documents are added: 186 in `evidence-B`, 192 here once this directory's two documents exist.
