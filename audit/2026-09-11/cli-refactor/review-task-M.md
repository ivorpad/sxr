# Review packet — the merge, the findings audit, two upstream defects

2026-09-12. Three tasks in one packet, because none of them changed behavior:
`SXR-MERGE-01` (D-11), `SXR-AUDIT-02`, and the verification of two defects in the
published v0.13.0.

## 1. What was asked, and the concrete before/after

**Task 1, the merge.** No CSV row. The before/after is history, not behavior:

```
before   HEAD 48b11c6c  (the audited base), 36 tracked files modified,
                        30 untracked entries, nothing committed
after    HEAD d2021d9   merge, parents f806ede (this work) and 8f93114 (v0.13.0)
         git diff HEAD^1 HEAD  ->  empty
         git log --oneline | rg '3280f00|9f5fe09|8f93114'  ->  3
```

**Task 2, the findings audit.** Six findings from
`upstream-reconciliation-second-opinion.md`, checked against the merged tree.
Only finding 6 required a change to the product; the rest are records.

**Task 3, the upstream defects.** Both confirmed, against `8f93114` only:

```
before (published 8f93114)   sxr --codex prompts --path /w --budget 50
                             -> byte-identical to the bare form; budget ignored
after  (this tree)           -> "# trimmed to 200-char lines (447 chars > 50
                                requested budget); whole text: --all, --budget 0"

before (published 8f93114)   sxr --codex prompts --path /w -n 1
                             -> 1 session row, "# +1 more"
after  (this tree)           -> 1 prompt record, "# 1 of 2 human prompts shown"
```

## 2. The bounded diff and where it is saved

The merge changed no file, so it has no diff: `git diff HEAD^1 HEAD` is empty and
`post-merge-integrity.log` re-hashes all 1229 pre-merge files as OK. The work
commit `f806ede` is exactly the reviewed content of slices 1 to 5 plus
`SXR-HAZ-01`, already delivered as `slice-01..05.patch`, `task-A.patch` and
`task-B.patch` in this directory; it introduces nothing new.

The findings audit's own edits are **uncommitted**, seven files, listed in
`evidence-M/README.md`. Left uncommitted deliberately: the merge was the task with
a mandate to move HEAD, and wording changes should be read before they enter
history. `git diff` shows them in full; `evidence-M/final-integrity.log` names
them by hash.

Pre-merge snapshot: `baseline-M/` — `files.txt` (1229 paths, including the
gitignored `CLAUDE.md`), `sha256.txt`, `worktree-snapshot.tar.gz` (10.9 MB),
`head.txt`, `git-status.txt`, `stashes.txt`, `reflog.txt`, `refs.txt`. The restore
was rehearsed before git was touched: extracted to a temp directory and verified
1229 OK, 0 failed.

## 3. Source identity, changed files, and verification

**How the merge was done, in order.**

1. Snapshot and hash-verified restore rehearsal, as above.
2. A clone outside the repository, `git clone --no-hardlinks --local --no-checkout`
   into `/tmp/merge-rehearsal`, with `8f93114` fetched from the source repo's own
   `origin/main` ref so no network was used. The working tree was overlaid from
   the snapshot tarball, so the rehearsal started from a byte-identical copy —
   verified 1229 OK, and the file sets compared equal.
3. In the rehearsal: staged the product work, committed, merged, resolved,
   committed the merge, and ran the suite. **951 passed there** before anything
   was done in the real repository. The rehearsal's own worktree was verified
   1229 OK against the snapshot afterwards.
4. Only then, the same sequence in the repository.

**What was staged, and what was not.** 65 files were staged into `f806ede`: the
36 tracked modifications (all product files — no `audit/` path among them) and 29
untracked source and test modules. Left untracked on purpose:

- `audit/` — 1307 files and 37 MB of process evidence, including eight snapshot
  tarballs totalling 19.1 MB. It is the record of how the work was reviewed, not
  the product, and committing it would put those tarballs and thousands of
  regenerable captures into release history. Nothing is lost: it stays on disk,
  and `final-integrity.log` accounts for every file in it by hash.
- `CLAUDE.md` and `docs/` — gitignored by this repository (`.gitignore:20` and
  `:27`). Not committed, and not force-added; that is the repository's own
  standing choice, not this task's.

**The conflicts, and how each was resolved.** Git stopped with eight conflicted
paths, one clean add, and one silent auto-merge:

| Path | Git's state | Resolution |
|---|---|---|
| `README.md`, `packaging/verify.py`, `src/sxr/cli.py`, `src/sxr/onboard.py` | `UU` | ours; each was hand-integrated during Task B |
| `pyproject.toml`, `src/sxr/__init__.py`, `uv.lock` | `UU` | ours; the version stays 0.14.0 |
| `src/sxr/views_read.py` | `UU` | ours; see finding 4 below |
| `src/sxr/prompt_selection.py`, `tests/test_prompt_sessions.py` | `AA` | ours; both files exist on both sides |
| `tests/test_file_selection.py` | `M`, **auto-merged with no conflict** | reverted to ours; see finding 3 |
| `src/sxr/prompt_catalog.py` | `A`, clean add | `git rm -f`; rejected under D-08 |

The auto-merge of `tests/test_file_selection.py` is the one that would have done
real damage silently, which is why the resolution was `git checkout HEAD -- .`
across every path rather than per-file editing: it makes "this tree's content is
the resolution" a property of the whole tree instead of a checklist.

**Verification, all re-run after every change in this packet.**

| Check | Command | Result | Receipt |
|---|---|---|---|
| Full suite | `pytest` | **951 passed, 0 failed** | `evidence-M/pytest.log`, `pytest.xml` |
| Suite in the rehearsal | `pytest tests/` in `/tmp/merge-rehearsal` | 951 passed | quoted in this packet; the clone is removed |
| Lint | `ruff check .` | exit 0 | `evidence-M/ruff-check.log` |
| Format | `ruff format --check .` | 192 files, exit 0 | `evidence-M/ruff-format.log` |
| Conventions | `konpy check` | 109 files, 0 violations | `evidence-M/konpy.log` |
| Historical contracts | `verify_cli.py --output …` | 66 passed, 1 failed (`PROMPTS-filter`) | `evidence-M/historical-contracts.{log,json}` |
| Migrated prompt contracts | `verify_prompts.py --output …` | 5 passed, 0 failed | `evidence-M/migrated-contracts.{log,json}` |
| Slice recaptures | `capture_{ranges,show,errors,cmds}.py` | all 158 files byte-identical to `evidence-B/recaptures/` | `evidence-M/recaptures/`, `*-capture.log` |
| Pre-merge integrity | `shasum -a 256 -c baseline-M/sha256.txt` | 1229 OK immediately after the merge; 1222 OK + 7 intended after the audit | `evidence-M/post-merge-integrity.log`, `final-integrity.log` |

**Baseline versus new failures.** No status changed anywhere. `PROMPTS-filter` is
the same single intentional failure it has been since slice 1. Nothing else fails.

**Not run, and why.** Bundle build and relocation verification, and any release
check: nothing is published and the tree is dirty by design, so `just
release-check` would refuse. `sxr find --index` against real history: unnecessary
and it writes caches. The installed `/opt/homebrew/bin/sxr` was invoked exactly
once, `--version`, to verify the claim that the tap serves 0.13.0 — it does, via
`../Cellar/sxr/0.13.0/bin/sxr`.

## 4. The six findings, adjudicated

**Finding 1 — CSV staleness is broader than the reconciliation slice said.
Confirmed in direction, corrected in three rows, rejected in three others.**

The second opinion is right that my "the other 21 are still accurate" was too
generous. Measured against `8f93114`:

- `PAR-prompts-typer-budget` and `PAR-prompts-typer-line_cap` **are** wrong for
  the published release, which I had not flagged. Bare `--budget` is ignored
  entirely, and bare `--line-limit` caps a preview column instead of prompt
  lines. Both notes corrected.
- `EXTRA-006` **is** partially wrong for the published release, whose bare
  `prompts --json` emits synthesized objects. Note corrected.
- The ten prompts scope-flag rows keep their contract, but their `example_before`
  prints a listing there. That distinction is real and my note omitted it; all
  ten now carry it.
- **Rejected, with measurement:** `PAR-prompts-typer-help`, `PAR-root-typer-help`
  and `CMD-root-typer` are not stale. The two `--help` rows assert exit 0,
  `--help` under Typer and `-h` under argparse; all three still hold on
  `8f93114`. `CMD-root-typer` asserts bare-listing behavior and that root help is
  long; both still hold. Upstream did rewrite root and `prompts` help text, but
  no cell of any row quotes that text, so nothing they say became false.
- **The bound is exactly right, and now measured rather than reasoned:** of 18
  `--help` surfaces, exactly 2 differ between the refs — `sxr` and `sxr prompts`
  — and the other 16 are byte-identical. `navigation.py` is 9 insertions and 0
  deletions, so "purely additive" is confirmed.
- **One count correction.** There are **25** rows whose `command` column is
  `prompts`. The second opinion's 27, and my own earlier note's 27, both come
  from adding `EXTRA-004` and `EXTRA-006`, which list `prompts` among several
  commands. Its 8 + 1 + 10 + 2 + 6 partition reconciles exactly once that is
  said out loud, so this is a labelling correction, not a disagreement.

**Finding 2 — a pre-existing CSV error, not staleness. Confirmed, and it is
worse than described.** `PAR-prompts-typer-limit` claims `-n` limits distinct
physical source records in JSON. Measured with `prompts @N --json -n 1` against a
session holding three prompt records: `48b11c6c` returns **3**, `8f93114` returns
**3**, this tree returns **1**. So the cell was already false at the base the
audit pinned, and `SXR-CLI-01` fixed a defect that neither the review nor any
published release records. It now has its own disposition note saying so.

**Finding 3 — upstream weakened a contract test. Confirmed absent here, and the
merge tried to bring it in.** Upstream's `tests/test_file_selection.py` appends
`command = [*command, ref.id]` when the command is `prompts`, so its
`--file`/`--path` byte-identity check no longer covers the bare form. This tree's
version has no such branch — `["prompts", "--json"]` is compared with no id
appended — and `rg 'ref\.id'` finds it only in `show` cases. Worth flagging: git
auto-merged that file with **no conflict** during the merge, which would have
adopted the weakening silently. The blanket `git checkout HEAD -- .` reverted it,
and the contract still holds (the case passes in the 951).

**Finding 4 — `views_read.py`'s conflict was positional. Confirmed, and nothing
was resolved on a wrong premise.** Upstream has three hunks in that file: an
import of `prompt_navigation, prompt_records`; the deletion of `_prompt_record`;
and a rewrite of `prompts()`'s body. In this tree slice 1 moved both
`_prompt_record` and `prompts` out to `views_prompts.py` and `prompt_selection.py`,
and slice 4 put `error_records` and `error_line` in the vacated region — so git
diffed upstream's deletions against slice 4's error code. All three hunks are
already satisfied or inapplicable: neither symbol exists in this file, and the
import would be unused here and rejected by ruff. Verified by listing the
function definitions at all three refs.

**Finding 5 — upstream is missing the whole remediation. Confirmed, and measured
more usefully than by line count.** The preserved 67-check contract suite was run
against all three trees, one fresh corpus per check:

| Tree | Passed | Failed |
|---|---|---|
| `48b11c6c` | 36 | 31 |
| `8f93114` | 36 | 31 |
| this tree | 66 | 1 |

The base and the published release fail the **identical** 31 checks, so the three
releases fixed none of the 17 audit findings. Exactly one check runs the other
way. On the diff numbers: I measure 65 files, +5033/−890 between `origin/main` and
this tree, against the second opinion's "59 files, roughly +4371/−523" — the same
direction and order, and the difference is Tasks A and B, which landed after that
measurement was taken. Spot checks of its specific claims all hold: `-n -1` and
`show --budget -5` exit 0 on both older refs and 2 here; `errors --compact` is an
unknown option on both and exists here. One qualification: `prompts --budget -5`
exits 0 on this tree too, deliberately, under D-02 — for that claim `show` is the
right surface, not `prompts`.

**Finding 6 — the `PROMPTS-filter` wording. Confirmed, and it drove the only
product change in this packet.** `PROMPTS-filter` passes on `48b11c6c` **and** on
`8f93114`, and fails only here. It uses `--file`, so upstream's "`--all` needs a
selection" guard never fires and the old `--all` meaning still holds there.
The divergence is therefore from a shipped release. Four places now say so:

- `prompts --help` gained a `Migration:` paragraph naming the released 0.13.0
  that Homebrew installs.
- `README.md`'s migration note says the reversal is of a released version, "and
  not merely an internal draft", and warns anyone scripting against 0.13.0's
  bare output or its session-row `-n`.
- The primer gained one clause: "Released 0.13.0 listed sessions from a bare
  prompts instead; that default is reversed here." This repository's own
  `CLAUDE.md` block was reissued from that body and `init --check` reports it up
  to date. No new flag or subcommand token enters the primer, so the
  `SXR-HAZ-01` surface guard is unaffected.
- `verify_prompts.py`'s docstring records that the case passes on both older
  refs and that the same measurement shows the published release failing 31 cases
  this tree passes — so the cost of the divergence is stated with its context.

## 5. Two defects in the published v0.13.0

Verified against `8f93114` in a `git archive` scratch tree, read-only, never
against this repository. Recorded, not fixed, as the reviewer chose.

**UP-DEF-01, `--budget` silently ignored.** Without a session id, `--file` or
`--latest`, `cli.prompts` calls
`prompt_catalog(refs, provider.parse, json_out, limit, line_cap)` and never
passes `budget`. Bare `prompts`, `--budget 0` and `--budget 50` produce
byte-identical output. Confirmed behaviorally and in source. It cannot reach this
tree: the catalog path is not adopted, and `prompt_command.py` puts `budget` into
`PromptOpts` on both paths.

**UP-DEF-02, `-n` changes unit.** With two human sessions in scope, `-n 1` prints
one session row and `# +1 more`; `-n 2` prints both. A negative `-n` prints no
rows and exits 0. This answers, by shipping, the `PAR-tools-typer-limit` question
this ledger says no task may assume — whether a limit may change unit — in the
affirmative. It cannot reach this tree: `-n` counts prompt records on every path
here, and the question stays open in the ledger.

A third divergence, recorded for completeness rather than as a defect: on
`8f93114` a bare `prompts --line-limit N` caps the listing's first-prompt preview
column unconditionally, with no budget involved. Measured at 10, 40 and 200.

## 6. Compatibility, limitations, decisions

- **Nothing was pushed.** `origin/main` is still `8f93114`. The branch has no
  upstream configured, so no push could happen by accident.
- **The merge is local and the tree still has uncommitted work**, both the
  `audit/` directory and this packet's seven wording files.
- **A judgment call worth confirming:** leaving `audit/` untracked. If the
  reviewer wants the written record in history, the documents could be committed
  without the tarballs and captures; say so and it is a small follow-up.
- **No decision is needed to continue.** D-11 is answered and done.

## 7. Ledger state and the next slice

`SXR-MERGE-01` and `SXR-AUDIT-02` are recorded as delivered. D-11 is in the
resolved table. Open decision 7 keeps only its release half; its history half is
closed. Open decisions 1, 2, 3, 4 and 5 are unchanged, and decision 2's
`PAR-tools-typer-limit` question is now known to have been answered in the
affirmative by a published release — which is an argument for answering it
deliberately here rather than by drift.

`SXR-CLI-05`'s acceptance is still marked deferred in the ledger from before the
reconciliation. It has been delivered, re-verified twice, and the reason for the
deferral is gone; the reviewer may want to close that.

The next proposed slice is **SXR-CLI-06**, `EXTRA-006`: deduplicate raw `--json`
records for `grep` and `cmds`, correct the `--json` help, and add `--events-json`
for selected normalized events. Not started.
