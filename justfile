default: check

check: lint konpy test

# Preflight for a release: every gate here is read-only, safe to run anytime.
release-check VERSION:
    #!/usr/bin/env bash
    set -euo pipefail
    V={{VERSION}}
    [[ "$V" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "version must be X.Y.Z, got '$V'"; exit 2; }
    [ "$(git rev-parse --abbrev-ref HEAD)" = "main" ] || { echo "not on main"; exit 2; }
    [ -z "$(git status --porcelain)" ] || { echo "working tree dirty"; exit 2; }
    ! git rev-parse -q --verify "refs/tags/v$V" >/dev/null || { echo "tag v$V exists locally"; exit 2; }
    [ -z "$(git ls-remote --tags origin "refs/tags/v$V")" ] || { echo "tag v$V exists on origin"; exit 2; }
    gh auth status >/dev/null 2>&1 || { echo "gh not authenticated"; exit 2; }
    TAP="$(brew --repository)/Library/Taps/ivorpad/homebrew-tap"
    [ -f "$TAP/Formula/sxr.rb" ] || { echo "tap formula missing at $TAP"; exit 2; }
    [ -z "$(git -C "$TAP" status --porcelain)" ] || { echo "tap checkout dirty"; exit 2; }
    uv run sxr -n 1 >/dev/null || { echo "claude provider smoke failed"; exit 2; }
    uv run sxr --codex -n 1 >/dev/null || { echo "codex provider smoke failed"; exit 2; }
    echo "release-check $V: all gates green"

# Commit the version bump in pyproject.toml, __init__.py and the sxr uv.lock entry,
# push main, then run `gh workflow run binaries.yml --ref main` and wait for success.
# Publication requires matching, verified bundles for all four platforms.
release VERSION NOTES: (release-check VERSION)
    uv run python packaging/publish.py {{VERSION}} {{quote(NOTES)}}

lint:
    uv run ruff format --check .
    uv run ruff check .

fmt:
    uv run ruff format .
    uv run ruff check --fix .

konpy:
    uv run konpy validate
    uv run konpy check

test:
    uv run pytest
