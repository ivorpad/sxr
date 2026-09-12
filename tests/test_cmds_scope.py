"""SXR-CLI-05: a `cmds` filter narrows rows, never the set of sessions searched.

Until 0.14.0 a nonempty `--grep` with no selector silently widened the scope from
the newest session to every session in the project, so the same flag meant two
different scopes depending on whether a selector was present. `--all-sessions`
now names that scope explicitly.
"""

import json

import pytest
from typer.testing import CliRunner

from sxr.cli import app
from sxr.onboard import EPILOG, PRIMER_BODY

runner = CliRunner()


def _write(path, records):
    """One JSONL transcript, one physical line per record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    return path


def _claude_session(root, ident, stamp, marker):
    """Two shell calls and one non-shell call, each with a paired result."""

    def message(seq, role, content):
        return dict(
            type="assistant" if role == "assistant" else "user",
            timestamp=f"2026-09-0{seq}T12:0{seq}:0{seq}Z",
            cwd="/w",
            message=dict(role=role, content=content),
        )

    def call(seq, call_id, tool, arguments):
        return message(
            seq, "assistant", [dict(type="tool_use", id=call_id, name=tool, input=arguments)]
        )

    def result(seq, call_id, body):
        return message(seq, "user", [dict(type="tool_result", tool_use_id=call_id, content=body)])

    return _write(
        root / "projects" / "-w" / f"{ident}.jsonl",
        [
            dict(type="user", timestamp=stamp, cwd="/w", message=dict(role="user", content="hi")),
            call(2, "call-a", "Bash", dict(command=f"git push origin {marker}")),
            result(3, "call-a", "pushed"),
            call(4, "call-b", "Read", dict(file_path=f"/w/{marker}.py")),
            result(5, "call-b", "contents"),
        ],
    )


def _codex_session(root, ident, day, marker):
    """The same coverage on Codex record shapes.

    Shell commands arrive as `event_msg`/`item_completed` CommandExecution items,
    which is where Codex records the normalized command text, and one MCP-style
    `function_call` stands in for a non-shell tool.
    """

    def executed(seq, call_id, command, output):
        return dict(
            timestamp=f"2026-09-0{seq}T12:0{seq}:0{seq}Z",
            type="event_msg",
            payload=dict(
                type="item_completed",
                item=dict(
                    type="CommandExecution",
                    id=call_id,
                    call_id=call_id,
                    command=command,
                    aggregated_output=output,
                    exit_code=0,
                ),
            ),
        )

    return _write(
        root
        / "sessions"
        / "2026"
        / "09"
        / f"0{day}"
        / f"rollout-2026-09-0{day}T12-00-00-{ident}.jsonl",
        [
            dict(
                timestamp="2026-09-01T12:00:00Z",
                type="session_meta",
                payload=dict(id=ident, cwd="/w", timestamp="2026-09-01T12:00:00Z"),
            ),
            dict(
                timestamp="2026-09-01T12:01:01Z",
                type="response_item",
                payload=dict(
                    type="message", role="user", content=[dict(type="input_text", text="hi")]
                ),
            ),
            executed(2, "call-a", ["git", "push", "origin", marker], "pushed"),
            dict(
                timestamp="2026-09-04T12:04:04Z",
                type="response_item",
                payload=dict(
                    type="function_call",
                    name="read_file",
                    call_id="call-b",
                    arguments=json.dumps(dict(path=f"/w/{marker}.py")),
                ),
            ),
            dict(
                timestamp="2026-09-05T12:05:05Z",
                type="response_item",
                payload=dict(
                    type="function_call_output",
                    call_id="call-b",
                    output=json.dumps(dict(output="contents", metadata=dict(exit_code=0))),
                ),
            ),
        ],
    )


@pytest.fixture(params=["claude", "codex"])
def corpus(request, tmp_path, monkeypatch):
    """Two sessions in one scope: newest says 'beta', oldest says 'alpha'."""
    root = tmp_path / request.param
    if request.param == "claude":
        _claude_session(
            root, "aaaaaaa1-0000-4000-8000-00000000000a", "2026-09-01T12:00:00Z", "alpha"
        )
        _claude_session(
            root, "bbbbbbb2-0000-4000-8000-00000000000b", "2026-09-02T12:00:00Z", "beta"
        )
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(root))
        return []
    _codex_session(root, "01999991-aaaa-7000-8000-00000000000a", 1, "alpha")
    _codex_session(root, "01999992-bbbb-7000-8000-00000000000b", 2, "beta")
    monkeypatch.setenv("CODEX_HOME", str(root))
    return ["--codex"]


def _run(corpus, *args):
    """Invoke cmds in the fixture scope."""
    return runner.invoke(app, [*corpus, "cmds", *args, "--path", "/w"])


def _markers(stdout):
    """Which sessions the printed rows came from, by their distinctive text."""
    return {m for m in ("alpha", "beta") if m in stdout}


def test_a_filter_no_longer_widens_the_scope(corpus):
    """The defect: --grep with no selector used to reach every session."""
    result = _run(corpus, "--grep", "git push")
    assert result.exit_code == 0, result.output
    assert _markers(result.stdout) == {"beta"}


def test_all_sessions_restores_the_old_reach_explicitly(corpus):
    """The migration path named in the row's compatibility clause."""
    result = _run(corpus, "--all-sessions", "--grep", "git push")
    assert result.exit_code == 0, result.output
    assert _markers(result.stdout) == {"alpha", "beta"}


def test_all_sessions_works_without_a_filter(corpus):
    """It is a scope flag, not a filter modifier."""
    result = _run(corpus, "--all-sessions")
    assert result.exit_code == 0, result.output
    assert _markers(result.stdout) == {"alpha", "beta"}


def test_no_selector_and_no_filter_is_unchanged(corpus):
    """The stable default was already the newest session; it still is."""
    result = _run(corpus)
    assert result.exit_code == 0, result.output
    assert _markers(result.stdout) == {"beta"}


def test_an_explicit_selector_still_wins_over_a_filter(corpus):
    """Unchanged: naming a session searches that session."""
    assert _markers(_run(corpus, "@2", "--grep", "git push").stdout) == {"alpha"}
    assert _markers(_run(corpus, "@1", "--grep", "git push").stdout) == {"beta"}


def test_a_range_still_selects_every_reference(corpus):
    """Unchanged: @A:@B is its own explicit scope."""
    result = _run(corpus, "@1:@2", "--grep", "git push")
    assert result.exit_code == 0, result.output
    assert _markers(result.stdout) == {"alpha", "beta"}


def test_all_sessions_with_a_selector_is_a_usage_error(corpus):
    """Two contradictory scopes are rejected rather than one silently winning."""
    result = _run(corpus, "@1", "--all-sessions")
    assert result.exit_code == 2, result.output
    assert "--all-sessions" in result.output
    assert "Traceback" not in result.output


def test_an_empty_filter_string_is_still_no_filter(corpus):
    """Unchanged edge: --grep '' does not filter, and does not widen either."""
    result = _run(corpus, "--grep", "")
    assert result.exit_code == 0, result.output
    assert _markers(result.stdout) == {"beta"}


def test_a_match_only_in_an_older_session_teaches_the_flag(corpus):
    """The whole point of the migration: the empty result says where the rest are."""
    result = _run(corpus, "--grep", "alpha")
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "--all-sessions searches the other 1 in scope" in result.stderr


def test_a_narrowed_search_says_how_many_sessions_it_read(corpus):
    """A found result still discloses that the scope was larger."""
    result = _run(corpus, "--grep", "git push")
    assert "# 1 of 2 sessions searched; all of them: --all-sessions" in result.stdout


def test_all_sessions_does_not_claim_a_narrowed_scope(corpus):
    """The note is about what was skipped, so searching everything prints none."""
    result = _run(corpus, "--all-sessions", "--grep", "git push")
    assert "sessions searched" not in result.stdout


def test_a_chosen_scope_is_never_second_guessed(corpus):
    """The note explains a defaulted scope; a named one needs no explaining.

    This is what keeps every already-explicit invocation byte-identical to
    0.12.2, which the evidence-05 capture index checks case by case.
    """
    for args in (["@2", "--grep", "git push"], ["@1:@2", "--grep", "git push"]):
        assert "sessions searched" not in _run(corpus, *args).stdout


def test_an_unfiltered_default_is_not_annotated_either(corpus):
    """`sxr cmds` is the oldest default in the tool; it gains no new output."""
    assert "sessions searched" not in _run(corpus).stdout


def test_no_match_anywhere_still_exits_one(corpus):
    """Unchanged: an empty result is exit 1 with a clean stdout."""
    result = _run(corpus, "--all-sessions", "--grep", "nothing-matches-this")
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "no commands matching 'nothing-matches-this'" in result.stderr


def test_json_emits_complete_records_one_per_physical_line(corpus):
    """SXR-AUD-005/015: raw records, unchanged by the new flag."""
    result = _run(corpus, "--all-sessions", "--json")
    assert result.exit_code == 0, result.output
    lines = result.stdout.splitlines()
    assert len(lines) == 4  # two tool calls per session
    for line in lines:
        assert isinstance(json.loads(line), dict)


def test_the_row_limit_still_spans_the_selected_sessions(corpus):
    """SXR-AUD-006: -n is one allowance for the invocation, not per session."""
    result = _run(corpus, "--all-sessions", "--grep", "git push", "-n", "1")
    assert result.exit_code == 0, result.output
    rows = [r for r in result.stdout.splitlines() if not r.startswith("#")]
    assert len(rows) == 1
    assert "showing first 1" in result.stdout


def test_a_negative_limit_is_still_a_usage_error(corpus):
    """SXR-AUD-012, unchanged."""
    result = _run(corpus, "--all-sessions", "-n", "-1")
    assert result.exit_code == 2
    assert "limit" in result.output


def test_non_shell_tool_calls_are_still_covered(corpus):
    """The row's compatibility clause: preserve all-tool coverage."""
    result = _run(corpus, "--all-sessions")
    assert "git push" in result.stdout
    assert ("Read" in result.stdout) or ("read_file" in result.stdout)


def test_help_documents_the_new_scope_flag(corpus):
    """Discoverable without reading the changelog."""
    result = runner.invoke(app, [*corpus, "cmds", "--help"])
    assert result.exit_code == 0
    assert "--all-sessions" in result.stdout


def test_the_primer_recipe_teaches_all_sessions():
    """The primer ships inside other repositories, so its recipe must stay true."""
    recipe = [line for line in PRIMER_BODY.splitlines() if line.startswith("recorded commands")]
    assert len(recipe) == 1
    assert "--all-sessions" in recipe[0]


def test_the_epilog_example_teaches_all_sessions():
    """`sxr --help` is the other place the old scope was advertised."""
    lines = [line for line in EPILOG.splitlines() if "cmds" in line and "--grep" in line]
    assert lines and all("--all-sessions" in line for line in lines)
