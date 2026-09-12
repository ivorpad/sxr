# evidence-B: the reconciliation with the published prompts releases

Adopts upstream's session filtering, `--latest` and navigation notices under
D-08 (reading stays the default) and D-09 (`--json` stays raw records). Nothing
was committed; `HEAD` is still `48b11c6c` and there are no stashes.

| File | What it records |
|---|---|
| `pytest.log` | 951 passed (923 before, plus 28 in `tests/test_prompt_sessions.py`) |
| `ruff-check.log`, `ruff-format.log` | clean; 183 files formatted |

`ruff format --check` counts Python inside markdown code blocks, so the file
count rises whenever a document is added. It reads 183 in the log above and 186
after the two review packets were written; both runs are clean.
| `konpy.log` | configuration valid; 109 files, 0 violations, no suppressions |
| `historical-contracts.json`, `.log` | `audit/2026-09-10/verify_cli.py --output …`: 66 passed, 1 failed (`PROMPTS-filter`, by design since slice 1). Per-check-id comparison against `evidence-A/`: **no check changed status** |
| `migrated-contracts.json`, `.log` | `../verify_prompts.py --output …`: 5 passed, 0 failed |
| `recaptures/{ranges,show,errors,cmds}/` | slices 2 to 5 re-captured with the same scripts, plus each run's log |

## Where the rebase happened

The reconciled tree was built in `/tmp/recon`, outside the repository, from
`baseline-B/worktree-snapshot.tar.gz`. Upstream's `navigation.py` change was
applied there with `patch`; the prompts work was integrated by hand; the full
suite was run there and passed 951 before anything was copied back. Ten files
were then copied into the working tree. The scratch tree has been removed.
`HEAD` never moved and no git index operation was performed.

## Slice recaptures

Slices 3, 4 and 5 re-capture **byte-identical** to `evidence-03/after`,
`evidence-04/after` and `evidence-05/after` — 48, 38 and 44 files each.

Slice 2's 28 range captures differ from `evidence-02/after` in 6 files, and the
differences are **not from this work**: re-capturing from the pre-reconciliation
snapshot in `/tmp/B-before` produces the same 6 differences, and that recapture
is byte-identical to this one. They are slice 3's two changes reaching output
that slice 2 had already recorded: the hidden-rows hint now says
`--tool-results` where it said `--tools`, and an empty selection now explains
which `--type` matched nothing and points at `sxr stats`.

## What the user's tree looks like afterwards

Every one of the 1045 files in `baseline-B/sha256.txt` was re-hashed: 0 missing,
7 changed, and all 7 are files this work intended to change. The other 1038,
including every prior slice's patch, baseline and evidence directory, are
byte-identical. Three files are new (`src/sxr/prompt_command.py`,
`src/sxr/prompt_selection.py`, `tests/test_prompt_sessions.py`).

`recaptures/` is deliberately excluded from `task-B.patch`: 158 files of verbatim
re-run output would swamp the diff, and they are compared programmatically above
rather than read.
