# Review packet — SXR-HAZ-01: close the primer downgrade hazard (D-10)

A hazard fix, not a slice. Delivered 2026-09-12.

## 1. What it closes, with a before/after invocation

D-10. `check_primer` compared only the version stamp, never the body, and this
tree's `PRIMER_BODY` stamped 0.14.0 while carrying prompts guidance older than
the published 0.13.0 primer. So `init --check` recommended a write that deleted
published instructions, and `init --write` performed it silently.

Against a scratch `AGENTS.md` holding the real published v0.13.0 primer
(`evidence-A/primer-guard.log`, produced by `capture_primer_guard.py`):

Before, from a tree extracted at `HEAD 48b11c6c`:

```
$ sxr init --check before-AGENTS.md
exit=1  primer v0.13.0 installed in …, binary is v0.12.2; run sxr init --write
$ sxr init --write before-AGENTS.md
exit=0  replaced primer v0.12.2 in …
        --latest still documented: False
```

After, from this tree:

```
$ sxr init --check after-AGENTS.md
exit=1  primer v0.13.0 in … is not this binary's v0.14.0, and replacing it would
        lose guidance: this binary's primer does not mention --latest. Leave it
        alone, or overwrite it deliberately with sxr init --write --force
$ sxr init --write after-AGENTS.md
exit=2  error: …: refusing to replace the primer, this binary's primer does not
        mention --latest
        # override with --force
        file changed: False
```

No disposition row changes: `init` rows in the CSV are `retain`, and this fixes a
defect in behavior they already describe rather than changing the surface, apart
from the new `--force` flag.

## 2. The bounded diff

`task-A.patch`, 3085 lines, +2788 / −134 across 11 files, of which the source
changes are `src/sxr/onboard.py`, the new `src/sxr/primer_text.py` (138 lines),
the new `tests/test_primer_guard.py` (216 lines), `README.md` and `CLAUDE.md`.
The remainder is `evidence-A/` and `capture_primer_guard.py`. Taken against
`baseline-A/worktree-snapshot.tar.gz`, whose restore was rehearsed before any
edit: 1026 files extracted, 1026 hashes verified, 0 failures.

sha256 `7bd59f6497b07689…`; regenerating the diff reproduces that hash.

Three paths present in `baseline-A/` are excluded from the patch because the
coordinator changed them at 07:01, mid-task, while restoring the first
reconciliation assessment over the second agent's copy:
`upstream-reconciliation.md`, `upstream-reconciliation-second-opinion.md` and
`RECOVERY-NOTE.md`. Before citing the restored assessment again I spot-checked
eleven of its own measured claims and found them intact.

## 3. Source identity, and what was run

The mechanism is two independent refusals, because a version stamp on its own
cannot be trusted — the hazard existed precisely because this tree's stamp was
higher while its content was older.

- **A later stamp.** `release()` parses dotted numbers; a strictly greater
  installed version refuses the write.
- **A lost surface.** `surfaces()` extracts the long flags and this tool's own
  subcommand names from a primer body. If the installed body documents anything
  this binary's body does not mention, the write is refused. Prose is
  deliberately not compared: rewording is normal at a release, whereas dropping
  `--latest` means the guidance no longer covers something the reader can type.
  `VERBS` is asserted equal to the app's real command set by a test, so the list
  cannot silently go stale.

`--force` overrides both, replacing only what is between the markers. Creating
and appending are not gated, since neither can lose an installed primer.
`check_primer` now reports the same condition without recommending a write, and
additionally compares the body, so a primer reissued under an unchanged version
is no longer called up to date. That second part is what caught this repository's
own `CLAUDE.md` during the change.

`PRIMER_BODY` was rebuilt on the published v0.13.0 body with three deliberate
departures: slice 5's `cmds --all-sessions` correction, the exit-code wording
that SXR-AUD-017 made true here, and — for D-08 — a prompts line that describes
reading as the default instead of the catalog. 62 body lines against upstream's
62, so the token budget is unchanged. `EPILOG` moved with it into
`primer_text.py`, which is what keeps `onboard.py` under the 300-line limit while
the guard is added; both names remain importable from `sxr.onboard`.

Verified, in this order, after the change:

| Check | Result |
|---|---|
| `uv run pytest` | **923 passed** (903 before, plus 20 new) |
| `uv run ruff check .` | clean |
| `uv run ruff format --check .` | 179 files formatted |
| `uv run konpy validate` / `check` | valid; 106 files, 0 violations |
| `konpy: ignore` added | none |
| `verify_cli.py --output evidence-A/historical-contracts.json` | 66 passed, 1 failed |
| `verify_prompts.py --output evidence-A/migrated-contracts.json` | 5 passed, 0 failed |
| per-check comparison against `evidence-05/` | **no check changed status** |
| `capture_primer_guard.py --output evidence-A/primer-guard.log` | before/after as quoted above |
| module lengths | `onboard.py` 285, `primer_text.py` 138, `test_primer_guard.py` 216 |

Those two line counts are as of this patch. Task B then added `--latest` to the
primer and repointed one fixture, taking `primer_text.py` to 139 and
`test_primer_guard.py` to 218; see that packet's §4.

Baseline separation: the single contract failure, `PROMPTS-filter`, has failed
since slice 1 by design, and `verify_cli.py` reported the same 66/1 before this
change. Not run: the packaged-bundle build, and any command outside `init`.

## 4. Compatibility, limits, decisions

- **New flag**, `init --write --force`. Without it, a lossy replacement now exits
  2 where it used to exit 0. This is a deliberate break for anyone scripting
  `init --write` across repositories with a forked build; the message names what
  would be lost and how to proceed.
- **`init --check` gained a state.** It still exits 0 or 1, but 1 now also covers
  "stamped this version over a different body", and its message no longer always
  ends in `run sxr init --write`.
- **The guard tracks real capability, not lineage.** Once this tree documents
  `--latest` again — which Task B does — installing over a published v0.13.0
  primer is no longer a loss and is allowed. That is the intended behavior, and
  it is why the guard tests use a synthetic fixture flag rather than `--latest`
  after the reconciliation.
- **Not closed:** nothing yet *tells* an installed primer it is stale. `--check`
  still has to be pointed at the file. Recorded as the remaining half of open
  decision 5.
- No decision needed to proceed.

## 5. Ledger, and what came next

`ledger.md` records SXR-HAZ-01 as delivered, marks the "do not run `init --write`
from this tree" warning closed with a pointer to `evidence-A/primer-guard.log`,
adds D-08, D-09 and D-10 to the resolved table, and notes that open decision 5 is
now only half open. Task B followed immediately, as instructed.
