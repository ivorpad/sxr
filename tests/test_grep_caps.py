"""grep's three caps are independent, and `--all` means what it means on prompts.

`-n` capped results *and* silently lifted the character budget, while per-match
flattening applied no matter what, so there was no spelling for "every match, whole".
Now: `-n` caps results, `--budget` stops output by characters, `--line-limit`
flattens each row, `--full` lifts the two character caps, and `--all` lifts all
three. `--all` is exactly `--full -n 0`, asserted byte-for-byte below rather than
described, so the two spellings cannot drift apart.

`--all` used to mean "keep zero-match rows in `-c`" and nothing else. That job is
now `--include-zero`, which mirrors how `prompts` moved its selection-widening to
`--include-context` when D-01 made `--all` mean completeness. Both commands now use
`--all` for the same thing and an `--include-*` flag for the other thing.
"""

import json

import pytest
from typer.testing import CliRunner

from sxr.cli import app

runner = CliRunner()

NEEDLE = "resonance"
ABSENT = "quernstone"
LONG = " ".join(f"w{i:04d}aaaaaaaaaaaaaa" for i in range(40))


def _text(n):
    return f"{NEEDLE} hit {n} {LONG} ENDOFHIT{n}"


def _claude(root):
    project = root / "projects" / "-w"
    project.mkdir(parents=True)
    for index, ident in enumerate(("aaaa0107", "bbbb0107", "cccc0107")):
        records = [
            dict(
                type="user",
                timestamp=f"2026-09-1{index}T07:00:00Z",
                cwd="/w",
                message=dict(role="user", content=f"open caps {index}"),
            )
        ]
        for n in range(6):
            body = _text(n) if index < 2 else f"unrelated {n}"
            records.append(
                dict(
                    type="assistant",
                    timestamp=f"2026-09-1{index}T07:0{n + 1}:00Z",
                    cwd="/w",
                    message=dict(role="assistant", content=[dict(type="text", text=body)]),
                )
            )
        path = project / f"{ident}-0000-4000-8000-00000000000{index}.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return "CLAUDE_CONFIG_DIR", []


def _codex(root):
    for index, tag in enumerate("abc"):
        directory = root / "sessions" / "2026" / "09" / f"1{index}"
        directory.mkdir(parents=True)
        ident = f"0199910{index}-{tag * 4}-7000-8000-00000000000{index}"
        records = [
            dict(
                timestamp=f"2026-09-1{index}T07:00:00Z",
                type="session_meta",
                payload=dict(id=ident, cwd="/w", timestamp=f"2026-09-1{index}T07:00:00Z"),
            ),
            dict(
                timestamp=f"2026-09-1{index}T07:00:00Z",
                type="event_msg",
                payload=dict(type="user_message", message=f"open caps {index}"),
            ),
        ]
        for n in range(6):
            body = _text(n) if index < 2 else f"unrelated {n}"
            records.append(
                dict(
                    timestamp=f"2026-09-1{index}T07:0{n + 1}:00Z",
                    type="response_item",
                    payload=dict(
                        type="message",
                        role="assistant",
                        content=[dict(type="output_text", text=body)],
                    ),
                )
            )
        path = directory / f"rollout-2026-09-1{index}T07-00-00-{ident}.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return "CODEX_HOME", ["--codex"]


@pytest.fixture(params=["claude", "codex"])
def corpus(request, tmp_path, monkeypatch):
    """Three sessions on one provider: two matching, one not."""
    root = tmp_path / request.param
    root.mkdir()
    variable, flags = {"claude": _claude, "codex": _codex}[request.param](root)
    monkeypatch.setenv(variable, str(root))
    monkeypatch.delenv("SXR_BUDGET", raising=False)
    monkeypatch.delenv("SXR_LINE_LIMIT", raising=False)
    return flags


def run(corpus, *args):
    """Invoke sxr scoped to the fixture's project."""
    return runner.invoke(app, [*corpus, *args, "--path", "/w"])


def data_rows(text):
    """Printed rows that are output rather than footers."""
    return [line for line in text.splitlines() if line and not line.startswith("#")]


def test_limit_caps_results_and_leaves_the_budget_alone(corpus):
    """-n 0 used to discard an explicit --budget. It was named for rows.

    This is the migration's centre: `grep -n 0 --budget 400` printed everything
    before and stops at the budget now.
    """
    capped = run(corpus, "grep", NEEDLE, "--budget", "400")
    lifted = run(corpus, "grep", NEEDLE, "--budget", "400", "-n", "0")
    assert capped.exit_code == 0 and lifted.exit_code == 0
    assert len(data_rows(lifted.stdout)) == len(data_rows(capped.stdout))
    assert "-n 0 lifts the result cap only now" in lifted.stderr


def test_limit_zero_still_lifts_the_result_cap(corpus):
    """The half of -n 0 that was never in question keeps working."""
    few = run(corpus, "grep", NEEDLE, "-n", "2")
    every = run(corpus, "grep", NEEDLE, "-n", "0")
    assert len(data_rows(few.stdout)) == 2
    assert len(data_rows(every.stdout)) == 12


def test_full_prints_complete_text_under_the_row_cap(corpus):
    """--full answers the character caps; -n keeps deciding how many results."""
    result = run(corpus, "grep", NEEDLE, "--full", "-n", "5")
    assert result.exit_code == 0
    rows = data_rows(result.stdout)
    assert len(rows) == 5
    assert all("ENDOFHIT" in row for row in rows)
    assert "chars]" not in result.stdout


def test_full_bypasses_the_character_budget(corpus):
    """As `show --full` does (SXR-AUD-008): complete means complete."""
    result = run(corpus, "grep", NEEDLE, "--full", "--budget", "400")
    assert result.exit_code == 0
    assert len(data_rows(result.stdout)) == 12
    assert all("ENDOFHIT" in row for row in data_rows(result.stdout))


def test_all_is_exactly_full_with_no_row_cap(corpus):
    """One spelling, asserted byte-for-byte so the two cannot drift apart."""
    every = run(corpus, "grep", NEEDLE, "--all")
    spelled_out = run(corpus, "grep", NEEDLE, "--full", "-n", "0")
    assert every.exit_code == 0 and spelled_out.exit_code == 0
    assert every.stdout == spelled_out.stdout


def test_all_overrides_an_explicit_row_cap_like_prompts(corpus):
    """D-01 gave `prompts --all` this precedence; grep's --all must not differ."""
    result = run(corpus, "grep", NEEDLE, "--all", "-n", "2")
    assert result.exit_code == 0
    assert len(data_rows(result.stdout)) == 12


def test_all_overrides_an_explicit_budget_like_prompts(corpus):
    """The other half of D-01's precedence: --all beats an explicit character cap."""
    result = run(corpus, "grep", NEEDLE, "--all", "--budget", "400")
    assert result.exit_code == 0
    assert len(data_rows(result.stdout)) == 12
    assert "chars]" not in result.stdout


def test_include_zero_keeps_zero_match_sessions(corpus):
    """The job --all used to do, under the name that says what it does."""
    pruned = run(corpus, "grep", NEEDLE, "-c")
    kept = run(corpus, "grep", NEEDLE, "-c", "--include-zero")
    assert len(data_rows(pruned.stdout)) == 2
    assert len(data_rows(kept.stdout)) == 3
    assert "\t0\t" in kept.stdout


def test_all_no_longer_keeps_zero_rows(corpus):
    """The breaking half of the rename, asserted so it cannot regress quietly."""
    result = run(corpus, "grep", NEEDLE, "-c", "--all")
    assert result.exit_code == 0
    assert len(data_rows(result.stdout)) == 2


def test_an_all_zero_table_prints_and_still_exits_one(corpus):
    """Reporting zero rows as data does not make a zero-match scope a hit."""
    result = run(corpus, "grep", ABSENT, "-c", "--include-zero")
    assert result.exit_code == 1
    rows = data_rows(result.stdout)
    assert len(rows) == 3
    assert all("\t0\t" in row for row in rows)
    assert "0 of 3 sessions match" in result.stdout


def test_a_zero_match_scope_without_include_zero_is_unchanged(corpus):
    """The existing empty path keeps its diagnostics and its exit 1."""
    result = run(corpus, "grep", ABSENT, "-c")
    assert result.exit_code == 1
    assert not data_rows(result.stdout)
    assert f"no matches for '{ABSENT}'" in result.stderr


def test_omitted_results_are_reported_under_json_too(corpus):
    """Before this, `grep -n 2 --json` printed 2 of 12 and said nothing anywhere."""
    result = run(corpus, "grep", NEEDLE, "-n", "2", "--json")
    assert result.exit_code == 0
    lines = [line for line in result.stdout.splitlines() if line]
    assert len(lines) == 2
    for line in lines:
        json.loads(line)  # stdout stays a record contract (D-09).
    assert "showing first 2" in result.stderr


def test_the_count_footer_names_the_flag_that_exists(corpus):
    """A footer advertising the old flag would be a migration trap."""
    result = run(corpus, "grep", NEEDLE, "-c")
    assert "keep zero-match rows: --include-zero" in result.stdout
    assert "rows: --all" not in result.stdout


def test_flags_that_describe_another_shape_are_refused(corpus):
    """-c prints no text to complete, and --include-zero has no table without -c."""
    no_text = run(corpus, "grep", NEEDLE, "-c", "--full")
    assert no_text.exit_code == 2
    assert "--full" in no_text.stderr and "--all" in no_text.stderr
    no_table = run(corpus, "grep", NEEDLE, "--include-zero")
    assert no_table.exit_code == 2
    assert "--include-zero" in no_table.stderr


def test_counts_are_independent_of_display_caps(corpus):
    """A cap on what is printed must never change what was counted."""
    plain = run(corpus, "grep", NEEDLE, "-c")
    capped = run(corpus, "grep", NEEDLE, "-c", "-n", "1")
    assert "2 of 3 sessions match" in plain.stdout
    assert "2 of 3 sessions match" in capped.stdout
    # A capped view reports the true total, not the number it managed to print.
    for flags in (["-n", "2"], ["--budget", "400"]):
        result = run(corpus, "grep", NEEDLE, *flags)
        assert "12 matches, showing first" in result.stdout
    assert len(data_rows(run(corpus, "grep", NEEDLE).stdout)) == 12


def test_raw_json_records_survive_every_new_flag(corpus):
    """D-09 and D-12: raw records stay raw, and --ids stays a projection."""
    whole = run(corpus, "grep", NEEDLE, "--all", "--json")
    assert whole.exit_code == 0
    records = [json.loads(line) for line in whole.stdout.splitlines() if line]
    assert len(records) == 12
    assert all("type" in record or "payload" in record for record in records)
    ids = run(corpus, "grep", NEEDLE, "--ids", "--json")
    projections = [json.loads(line) for line in ids.stdout.splitlines() if line]
    assert [p["type"] for p in projections] == ["grep_session"] * 2
    assert all("matches" not in p for p in projections)
