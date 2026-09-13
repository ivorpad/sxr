"""SXR-CLI-06: every grep and cmds JSON mode emits JSON, one record per line.

Three defects met here. `grep -l --json` printed bare session ids, which are not
JSON at all, because -l was decided before --json. Raw `--json` printed one
object per matching *event*, so a Claude line carrying two matching content
blocks -- one physical record -- was printed twice, and `-n` counted the copies.
And `-c` silently swallowed -l, -C and --budget, accepting flags that described
an output it never produced.

The Claude and Codex halves of the corpus are deliberately not equivalent: Claude
yields one event per content block and Codex one per physical record, so only the
Claude half can duplicate. Both are exercised, because the fix must not make the
Codex half worse and the asymmetry is worth pinning.
"""

import json

import pytest
from typer.testing import CliRunner

from sxr.cli import app

runner = CliRunner()
NEEDLE = "retry"


def _write(path, records):
    """One JSONL transcript, one physical line per record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    return path


def _claude_session(root, ident, marker):
    """Five physical records, two of which carry two blocks each."""

    def message(seq, role, content):
        return dict(
            type="assistant" if role == "assistant" else "user",
            timestamp=f"2026-09-{seq:02d}T12:{seq:02d}:00Z",
            cwd="/w",
            message=dict(role=role, content=content),
        )

    return _write(
        root / "projects" / "-w" / f"{ident}.jsonl",
        [
            dict(
                type="user",
                timestamp="2026-09-01T12:00:00Z",
                cwd="/w",
                message=dict(role="user", content=f"start {NEEDLE} {marker}"),
            ),
            # One line, two matching text blocks.
            message(
                2,
                "assistant",
                [
                    dict(type="text", text=f"{NEEDLE} first {marker}"),
                    dict(type="text", text=f"{NEEDLE} second {marker}"),
                ],
            ),
            # One line, two tool calls.
            message(
                3,
                "assistant",
                [
                    dict(
                        type="tool_use",
                        id="call-a",
                        name="Bash",
                        input=dict(command=f"git {NEEDLE} {marker}"),
                    ),
                    dict(
                        type="tool_use",
                        id="call-b",
                        name="Read",
                        input=dict(file_path=f"/w/{NEEDLE}.py"),
                    ),
                ],
            ),
            # A second tool-bearing line, one call, so a limit of 2 can pick two.
            message(
                4,
                "assistant",
                [
                    dict(
                        type="tool_use",
                        id="call-c",
                        name="Bash",
                        input=dict(command=f"git {NEEDLE} --again {marker}"),
                    )
                ],
            ),
            message(5, "assistant", [dict(type="text", text=f"done {marker}")]),
        ],
    )


def _codex_session(root, ident, day, marker):
    """The same coverage on Codex shapes, which hold one event per record."""

    def item(seq, payload):
        return dict(
            timestamp=f"2026-09-{seq:02d}T12:{seq:02d}:00Z", type="response_item", payload=payload
        )

    def said(seq, role, body):
        kind = "input_text" if role == "user" else "output_text"
        return item(seq, dict(type="message", role=role, content=[dict(type=kind, text=body)]))

    def executed(seq, call_id, command):
        return dict(
            timestamp=f"2026-09-{seq:02d}T12:{seq:02d}:00Z",
            type="event_msg",
            payload=dict(
                type="item_completed",
                item=dict(
                    type="CommandExecution",
                    id=call_id,
                    call_id=call_id,
                    command=command,
                    aggregated_output="ok",
                    exit_code=0,
                ),
            ),
        )

    return _write(
        root
        / "sessions"
        / "2026"
        / "09"
        / f"{day:02d}"
        / f"rollout-2026-09-{day:02d}T12-00-00-{ident}.jsonl",
        [
            dict(
                timestamp="2026-09-01T12:00:00Z",
                type="session_meta",
                payload=dict(id=ident, cwd="/w", timestamp="2026-09-01T12:00:00Z"),
            ),
            said(1, "user", f"start {NEEDLE} {marker}"),
            said(2, "assistant", f"{NEEDLE} first {marker}"),
            executed(3, "call-a", ["git", NEEDLE, marker]),
            executed(4, "call-c", ["git", NEEDLE, "--again", marker]),
            said(5, "assistant", f"done {marker}"),
        ],
    )


@pytest.fixture(params=["claude", "codex"])
def corpus(request, tmp_path, monkeypatch):
    """Two sessions in one scope, oldest 'alpha' and newest 'beta'."""
    root = tmp_path / request.param
    if request.param == "claude":
        for ident, marker in [
            ("aaaaaaa1-0000-4000-8000-00000000000a", "alpha"),
            ("bbbbbbb2-0000-4000-8000-00000000000b", "beta"),
        ]:
            _claude_session(root, ident, marker)
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(root))
        return []
    for day, (ident, marker) in enumerate(
        [
            ("01999991-aaaa-7000-8000-00000000000a", "alpha"),
            ("01999992-bbbb-7000-8000-00000000000b", "beta"),
        ],
        start=1,
    ):
        _codex_session(root, ident, day, marker)
    monkeypatch.setenv("CODEX_HOME", str(root))
    return ["--codex"]


def _run(corpus, *args):
    """Invoke the CLI against the fixture scope and return its result."""
    return runner.invoke(app, [*corpus, *args, "--path", "/w"])


def _objects(result):
    """Every stdout line parsed as JSON; a non-JSON line fails the test here."""
    lines = [line for line in result.stdout.splitlines() if line]
    parsed = []
    for line in lines:
        try:
            parsed.append(json.loads(line))
        except ValueError as exc:  # pragma: no cover - only on a regression
            pytest.fail(f"stdout line is not JSON ({exc.args[0]}): {line!r}")
    return parsed


def test_ids_json_names_each_matching_session(corpus) -> None:
    result = _run(corpus, "grep", NEEDLE, "-l", "--json")
    assert result.exit_code == 0
    objects = _objects(result)
    assert len(objects) == 2
    for record in objects:
        assert record["type"] == "grep_session"
        assert len(record["session"]) > 8, "the full id, not a short prefix"
        assert record["provider"] in ("claude", "codex")
        assert record["path"].endswith(".jsonl")
    assert len({record["session"] for record in objects}) == 2


def test_ids_alias_matches_the_original_spelling(corpus) -> None:
    for spelling in ("--ids", "--files-with-matches"):
        result = _run(corpus, "grep", NEEDLE, spelling, "--json")
        assert result.exit_code == 0
        assert _objects(result) == _objects(_run(corpus, "grep", NEEDLE, "-l", "--json"))


def test_ids_without_json_still_prints_bare_short_ids(corpus) -> None:
    result = _run(corpus, "grep", NEEDLE, "-l")
    assert result.exit_code == 0
    printed = [line for line in result.stdout.splitlines() if line]
    identities = _objects(_run(corpus, "grep", NEEDLE, "-l", "--json"))
    assert len(printed) == 2
    for line, record in zip(printed, identities, strict=True):
        assert "{" not in line, "without --json the ids stay bare"
        assert record["session"].startswith(line)


def test_raw_json_prints_every_physical_record_once(corpus) -> None:
    result = _run(corpus, "grep", NEEDLE, "--json")
    assert result.exit_code == 0
    lines = [line for line in result.stdout.splitlines() if line]
    assert lines, "the pattern matches this corpus"
    assert len(lines) == len(set(lines)), "a physical record was printed twice"
    assert _objects(result)


def test_two_matching_blocks_on_one_claude_line_are_one_record(tmp_path, monkeypatch) -> None:
    root = tmp_path / "claude"
    _claude_session(root, "aaaaaaa1-0000-4000-8000-00000000000a", "alpha")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(root))
    result = runner.invoke(app, ["grep", NEEDLE, "--json", "--path", "/w"])
    assert result.exit_code == 0
    records = _objects(result)
    # Records 1 through 4 match; record 2 carries two matching blocks and
    # record 3 two matching tool calls, so the old code printed six lines.
    assert len(records) == 4
    stamps = [record["timestamp"] for record in records]
    assert len(stamps) == len(set(stamps))


def test_json_limit_counts_records(corpus) -> None:
    every = _objects(_run(corpus, "grep", NEEDLE, "--json", "-n", "0"))
    assert len(every) > 2
    for count in (1, 2):
        capped = _objects(_run(corpus, "grep", NEEDLE, "--json", "-n", str(count)))
        assert capped == every[:count]


def test_count_json_is_unchanged_by_this_slice(corpus) -> None:
    result = _run(corpus, "grep", NEEDLE, "-c", "--json")
    assert result.exit_code == 0
    objects = _objects(result)
    assert [record["type"] for record in objects] == ["grep_count", "grep_count"]
    assert all(record["matches"] > 0 for record in objects)


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["-c", "-l"], "-c ranks matching sessions and -l lists them"),
        (["-c", "--ids"], "-c ranks matching sessions and -l lists them"),
        (["-c", "-C", "2"], "-c prints one row per session"),
        (["--sort", "started"], "--sort orders the -c table"),
        (["-C", "-1"], "-C takes 0 or more events"),
        (["--sort", "density"], "--sort takes matches or started"),
    ],
)
def test_incompatible_modes_exit_two(corpus, args, message) -> None:
    result = _run(corpus, "grep", NEEDLE, *args)
    assert result.exit_code == 2, result.stdout
    assert message in result.stderr
    assert result.stdout == ""


def test_a_bad_sort_value_is_reported_before_the_mode(corpus) -> None:
    result = _run(corpus, "grep", NEEDLE, "-c", "--sort", "density")
    assert result.exit_code == 2
    assert "--sort takes matches or started" in result.stderr


def test_naming_the_default_sort_under_count_changes_nothing(corpus) -> None:
    explicit = _run(corpus, "grep", NEEDLE, "-c", "--sort", "matches")
    bare = _run(corpus, "grep", NEEDLE, "-c")
    assert (explicit.exit_code, bare.exit_code) == (0, 0)
    assert explicit.stdout == bare.stdout


def test_budget_under_count_says_it_caps_text_the_table_omits(corpus) -> None:
    plain = _run(corpus, "grep", NEEDLE, "-c")
    noted = _run(corpus, "grep", NEEDLE, "-c", "--budget", "10")
    assert noted.exit_code == 0
    assert "--budget caps match text" in noted.stderr
    assert noted.stdout == plain.stdout, "the table itself is unaffected"


def test_context_zero_is_accepted_and_prints_rows(corpus) -> None:
    result = _run(corpus, "grep", NEEDLE, "-C", "0")
    assert result.exit_code == 0
    assert NEEDLE in result.stdout


def test_no_match_exits_one_in_every_json_mode(corpus) -> None:
    for args in (["--json"], ["-l", "--json"], ["-c", "--json"], []):
        result = _run(corpus, "grep", "zzz-no-match", *args)
        assert result.exit_code == 1, args
        assert result.stdout == "", args


def test_cmds_json_prints_every_physical_record_once(corpus) -> None:
    result = _run(corpus, "cmds", "--json")
    assert result.exit_code == 0
    lines = [line for line in result.stdout.splitlines() if line]
    assert lines
    assert len(lines) == len(set(lines))
    assert _objects(result)


def test_cmds_json_limit_selects_distinct_records(corpus) -> None:
    every = _objects(_run(corpus, "cmds", "--json", "-n", "0"))
    assert len(every) >= 2
    two = _objects(_run(corpus, "cmds", "--json", "-n", "2"))
    assert two == every[:2]
    assert two[0] != two[1], "a limit must not spend both rows on one record"


def test_cmds_json_dedups_per_session_not_across_the_scope(corpus) -> None:
    scoped = _objects(_run(corpus, "cmds", "@1", "--json"))
    whole = _objects(_run(corpus, "cmds", "--all-sessions", "--json"))
    assert len(whole) == 2 * len(scoped), "both sessions keep their own records"


def test_cmds_text_output_is_unaffected(corpus) -> None:
    result = _run(corpus, "cmds")
    assert result.exit_code == 0
    assert result.stdout.count(f"git {NEEDLE}") >= 2


def test_file_selection_scopes_every_json_mode(corpus, tmp_path) -> None:
    listing = runner.invoke(app, [*corpus, "list", "--json", "--path", "/w"])
    newest = json.loads(listing.stdout.splitlines()[0])
    for args in (["--json"], ["-l", "--json"], ["-c", "--json"]):
        result = runner.invoke(app, [*corpus, "grep", NEEDLE, *args, "--file", newest["path"]])
        assert result.exit_code == 0, args
        objects = _objects(result)
        assert objects, args
        for record in objects:
            if record.get("type") in ("grep_session", "grep_count"):
                assert record["session"] == newest["id"]
