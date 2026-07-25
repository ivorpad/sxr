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

# Pipeline: bump version in pyproject + __init__, uv lock, just check,
# build, commit, push main + tag (each verified with ls-remote, never
# trusting "ok" output), GitHub release with dist assets, brew tap bump
# from the tag tarball sha, brew upgrade, then smoke BOTH providers with
# the installed binary. Backend stays flit_core: brew's --no-binary
# cannot build uv_build.
#
# Ship VERSION to GitHub + brew; NOTES is one line (commit msg tail + release notes).
release VERSION NOTES: (release-check VERSION)
    #!/usr/bin/env bash
    set -euo pipefail
    V={{VERSION}}
    NOTES={{quote(NOTES)}}
    TAP="$(brew --repository)/Library/Taps/ivorpad/homebrew-tap"

    echo "== bump to $V"
    sed -i '' "s/^version = \".*\"/version = \"$V\"/" pyproject.toml
    sed -i '' "s/^__version__ = \".*\"/__version__ = \"$V\"/" src/sxr/__init__.py
    grep -q "^version = \"$V\"" pyproject.toml
    grep -q "^__version__ = \"$V\"" src/sxr/__init__.py
    uv lock

    echo "== check + build"
    just check
    rm -f dist/*
    uv build
    uv run --no-project --with "dist/sxr-$V-py3-none-any.whl" sxr --version | grep -F "$V"

    echo "== commit + push main (ls-remote verified)"
    git add pyproject.toml src/sxr/__init__.py uv.lock
    git commit -m "$V: $NOTES"
    git push origin main
    [ "$(git ls-remote origin main | cut -f1)" = "$(git rev-parse HEAD)" ]

    echo "== tag + push (ls-remote verified)"
    git tag "v$V"
    git push origin "refs/tags/v$V"
    [ "$(git ls-remote origin "refs/tags/v$V" | cut -f1)" = "$(git rev-parse "v$V^{commit}")" ]

    echo "== github release with dist assets"
    gh release create "v$V" --title "sxr $V" --notes "$NOTES" \
        "dist/sxr-$V-py3-none-any.whl" "dist/sxr-$V.tar.gz"
    [ "$(gh release view "v$V" --json assets --jq '.assets | length')" = "2" ]

    echo "== brew tap bump (ls-remote verified)"
    sha=$(curl -sfL "https://github.com/ivorpad/sxr/archive/refs/tags/v$V.tar.gz" | shasum -a 256 | cut -d' ' -f1)
    [ "${#sha}" -eq 64 ]
    sed -i '' -E "s|refs/tags/v[0-9.]+\.tar\.gz|refs/tags/v$V.tar.gz|" "$TAP/Formula/sxr.rb"
    sed -i '' -E "1,/sha256/ s|sha256 \"[0-9a-f]{64}\"|sha256 \"$sha\"|" "$TAP/Formula/sxr.rb"
    grep -q "v$V.tar.gz" "$TAP/Formula/sxr.rb"
    grep -q "$sha" "$TAP/Formula/sxr.rb"
    git -C "$TAP" commit -am "sxr $V"
    git -C "$TAP" push origin main
    [ "$(git -C "$TAP" ls-remote origin main | cut -f1)" = "$(git -C "$TAP" rev-parse HEAD)" ]

    echo "== brew upgrade + smoke both providers"
    brew upgrade sxr
    sxr --version | grep -F "$V"
    sxr cmds @1 -n 1 >/dev/null && echo "claude ok"
    sxr --codex cmds @1 -n 1 >/dev/null && echo "codex ok"
    echo "== released $V"

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
