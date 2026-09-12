# sxr CLI refactor — execution directory

Execution of the 2026-09-11 handoff (`../refactor-agent-handoff.md`, preserved
unchanged). The 2026-09-10 audit and command-review directories are historical
evidence and are untouched; everything produced by this work lives here.

Read in this order. You should not need the 399 KB handoff again.

| File | What it is |
|---|---|
| [baseline.md](baseline.md) | the tree and check state measured before any edit, and how to reproduce a bounded diff |
| [contracts.md](contracts.md) | what no task may break without saying so |
| [tasks.md](tasks.md) | 24 tasks: IDs, CSV rows, before/after, files, deps, acceptance, review checkpoint, class, and the proposed sequence |
| [disposition.md](disposition.md) / [disposition.json](disposition.json) | every one of the 408 CSV rows mapped to a task or an explicit disposition |
| [ledger.md](ledger.md) | task states, disposition tallies, resolved and open decisions |
| [review-slice-01.md](review-slice-01.md) | review packet for SXR-CLI-01 (accepted 2026-09-11) |
| [review-slice-02.md](review-slice-02.md) | review packet for SXR-CLI-02 (delivered 2026-09-11) |

Each slice records its own starting tree, so a slice's diff isolates only that
slice's contribution — the previous slices are part of its starting state.

| Slice | Baseline snapshot | Bounded diff | Hashes after | Evidence |
|---|---|---|---|---|
| SXR-CLI-01 | `baseline/` | `slice-01.patch` | `slice-01-after-sha256.txt` | `evidence/` |
| SXR-CLI-02 | `baseline-02/` | `slice-02.patch` | `slice-02-after-sha256.txt` | `evidence-02/` |

Each snapshot directory holds the working tree (tracked **and** untracked),
per-file hashes, `git status`, and the tracked-vs-HEAD patch. `git diff HEAD` is
not equivalent to any of these: HEAD predates the uncommitted remediation work.

Tools:

- `verify_prompts.py` — re-verifies the historical `PROMPTS-filter` contract's
  intent under the migrated flag names, reusing the 2026-09-10 audit corpus.
- `fixture_ranges.py` / `capture_ranges.py` — build the synthetic two-session
  Claude and Codex corpora and capture 28 range invocations to one file each,
  so before/after is a byte comparison. `uv run python capture_ranges.py <dir>`.

## Reproducing a bounded diff

Substitute `baseline` / `slice-01` or `baseline-02` / `slice-02`:

```bash
cd /path/to/sxr
D=audit/2026-09-11/cli-refactor
mkdir -p /tmp/sxr-baseline && tar -xzf $D/baseline-02/worktree-snapshot.tar.gz -C /tmp/sxr-baseline
(cd /tmp/sxr-baseline && find . -type f | sort | xargs shasum -a 256) | diff - $D/baseline-02/sha256.txt

mkdir -p /tmp/sxr-now
{ git ls-files src tests docs packaging README.md CLAUDE.md konpy.json pyproject.toml justfile
  git ls-files -o --exclude-standard src tests docs packaging; } | sort -u > /tmp/now-files.txt
rsync -a --files-from=/tmp/now-files.txt ./ /tmp/sxr-now/
diff -ruN -x .ruff_cache -x __pycache__ /tmp/sxr-baseline /tmp/sxr-now   # == slice-02.patch
```

`-x .ruff_cache` matters: running `ruff` against an extracted snapshot writes a
cache directory into it, which would otherwise show up as spurious diff entries.
`baseline/sha256.txt` records `./`-prefixed paths and `baseline-02/sha256.txt`
does not, so compare hash columns rather than whole lines when in doubt.

## Reproducing the checks

```bash
uv run pytest -q                                          # 745 passed
uv run ruff check . && uv run ruff format --check .
uv run konpy validate && uv run konpy check
(cd audit/2026-09-10 && uv run python verify_cli.py --output /tmp/contracts.json)   # 66/67; see review packet
(cd audit/2026-09-11/cli-refactor && uv run python verify_prompts.py)              # 5/5
(cd audit/2026-09-11/cli-refactor && uv run python capture_ranges.py /tmp/ranges)   # == evidence-02/after/
```

Nothing here publishes, installs, releases, or rewrites a real transcript, and
no commit was made. `/opt/homebrew/bin/sxr` was neither used nor changed.
