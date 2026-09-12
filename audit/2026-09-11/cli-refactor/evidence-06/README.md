# evidence-06: upstream reconciliation assessment

Evidence for [../upstream-reconciliation.md](../upstream-reconciliation.md).
This directory belongs to no slice. It records a read-only investigation of the
three published releases between local `HEAD` (`48b11c6c`) and `origin/HEAD`
(`8f93114f8a1712cc7f02f2cfb91cf10d3040bb04`).

Nothing here altered the repository. Upstream trees were materialized with
`git archive <ref> | tar -x` into temp directories outside the repository; no
worktree, checkout, merge, rebase, reset or index operation was performed, and
the version was not changed. Verified afterwards: `HEAD` unmoved, no stashes,
35 tracked files still modified, `src/sxr/__init__.py` still `0.14.0`,
`slice-05.patch` still `fa773dd9b5554024…`.

| File | What it records | Produced by |
|---|---|---|
| `prompt-predicates.log` | This tree's `human_prompt` against upstream's `_prompt_record` over 23 record shapes: **0 divergences** | `../probe_prompt_predicates.py --output evidence-06/prompt-predicates.log` |
| `prompts-three-way.log`, `.json` | 12 `prompts` invocations run against `HEAD`, this tree and `origin/HEAD` over one synthetic Codex corpus, with raw stdout and stderr | `../probe_prompts_three_way.py --output evidence-06/prompts-three-way.log` |
| `contracts-vs-upstream.log`, `.json` | The five migrated prompt contracts per tree: this tree 5/0, `HEAD` 1/4, upstream 1/4 | `../probe_contracts_vs_upstream.py --output evidence-06/contracts-vs-upstream.log` |
| `upstream-tests-vs-this-tree.log` | Upstream's `tests/test_prompt_sessions.py` (15 functions, 28 cases) against this tree: 23 failed, 5 passed | `uv run pytest /tmp/upstream-tests/test_prompt_sessions.py -q` |
| `prompts-option-surface.log` | `prompts --help` option lists: `HEAD` 16, this tree 17 (`--include-context`), upstream 17 (`--latest`) | `prompts --help` per tree |
| `primer-lineage.log` | This tree's `init --check` and `init --write` over a scratch `AGENTS.md` holding the published v0.13.0 primer | `sxr init` from this tree, fixture in `/tmp` |
| `primer-bodies.log` | Full `PRIMER_BODY` and `EPILOG` diffs, upstream v0.13.0 versus this tree v0.14.0 | `difflib` over both modules |
| `rebase-conflicts.log` | The cumulative `git diff HEAD` (35 files, 2481 lines) applied to an extracted upstream tree: 11 rejected hunks in 7 files | `patch -p1 --dry-run` in `/tmp` |
| `test-share.log` | 83 of 903 collected tests are prompts-related | `pytest --collect-only [-k prompt]` |

The three probe scripts require `--output`, following D-06, so no run can
overwrite a receipt by default.

## One measurement drift worth naming

`ruff format --check .` now reports **173 files**, not the 169 recorded in
`review-slice-05.md` and `evidence-05/README.md`. The four extra files are the
three probe scripts and this investigation's markdown; ruff formats Python inside
markdown code blocks, so the count rises whenever a document is added. Slice 5's
169 was correct when measured. Re-verified alongside it, unchanged: `ruff check`
clean, `konpy check` 104 files with 0 violations, and `pytest` 903 passed.
