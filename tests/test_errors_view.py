"""SXR-CLI-04: `errors` rows name their source, and their text is complete.

Both providers get two sessions recording an error at the *same* physical
sequence, which is the case CMD-errors-typer's acceptance names, plus a long
multi-line error whose ending only survives when text is not trimmed.
"""

import json

import pytest
from typer.testing import CliRunner

from sxr.cli import app

runner = CliRunner()

LONG_HEAD = "Traceback (most recent call last):"
LONG_TAIL = "exit status 65."
LONG = (
    LONG_HEAD + "\n"
    '  File "/w/app/main.py", line 118, in handler\n'
    "    payload = decode(body)\n"
    "ValueError: " + "unexpected token " * 60 + "\n"
    "The failure is at the END, which middle trimming keeps: " + LONG_TAIL
)


def _write(path, records):
    """One JSONL transcript, one physical line per record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    return path


def _stamp(seq):
    """A distinct timestamp per physical record, so clocks are readable in rows."""
    return f"2026-09-0{seq}T12:0{seq}:0{seq}Z"


def _claude_session(root, ident, stamp, marker):
    """One Claude transcript: a clean call, a failure at seq 6, its repeat, a long failure."""

    def message(seq, role, content):
        role_type = "assistant" if role == "assistant" else "user"
        return dict(
            type=role_type,
            timestamp=_stamp(seq),
            cwd="/w",
            message=dict(role=role, content=content),
        )

    def result(seq, call, content, failed):
        block = dict(type="tool_result", tool_use_id=call, content=content)
        return message(seq, "user", [dict(block, is_error=True) if failed else block])

    def call(seq, call_id, tool):
        return message(seq, "assistant", [dict(type="tool_use", id=call_id, name=tool, input={})])

    return _write(
        root / "projects" / "-w" / f"{ident}.jsonl",
        [
            dict(
                type="user", timestamp=stamp, cwd="/w", message=dict(role="user", content="start")
            ),
            message(2, "assistant", [dict(type="text", text=f"work {marker}")]),
            call(3, "call-a", "Bash"),
            result(4, "call-a", "ok", False),
            call(5, "call-b", "Read"),
            result(6, "call-b", f"ENOENT: /x {marker}", True),
            result(7, "call-b", "ENOENT: /x (repeat)", True),
            call(8, "call-c", "Bash"),
            result(9, "call-c", LONG, True),
        ],
    )


def _codex_session(root, ident, day, marker):
    """One Codex rollout mirroring the Claude coverage on Codex record shapes."""

    def item(seq, payload):
        return dict(timestamp=_stamp(seq), type="response_item", payload=payload)

    def call(seq, call_id):
        return item(
            seq,
            dict(
                type="function_call",
                name="shell",
                call_id=call_id,
                arguments=json.dumps(dict(command=["run"])),
            ),
        )

    def output(seq, call_id, text, code):
        return item(
            seq,
            dict(
                type="function_call_output",
                call_id=call_id,
                output=json.dumps(dict(output=text, metadata=dict(exit_code=code))),
            ),
        )

    def text(seq, role, body):
        kind = "output_text" if role == "assistant" else "input_text"
        return item(seq, dict(type="message", role=role, content=[dict(type=kind, text=body)]))

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
            text(1, "user", "start"),
            text(2, "assistant", f"work {marker}"),
            call(3, "call-a"),
            output(4, "call-a", "ok", 0),
            call(5, "call-b"),
            output(6, "call-b", f"ENOENT: /x {marker}", 1),
            output(7, "call-b", "ENOENT: /x (repeat)", 1),
            call(8, "call-c"),
            output(9, "call-c", LONG, 65),
        ],
    )


@pytest.fixture(params=["claude", "codex"])
def corpus(request, tmp_path, monkeypatch):
    """Two same-provider sessions in one scope, each with an error at one shared seq."""
    root = tmp_path / request.param
    if request.param == "claude":
        _claude_session(root, "aaaaaaa1-0000-4000-8000-00000000000a", "2026-09-01T12:00:00Z", "a")
        _claude_session(root, "bbbbbbb2-0000-4000-8000-00000000000b", "2026-09-02T12:00:00Z", "b")
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(root))
        return [], ("bbbbbbb2", "aaaaaaa1"), 6
    _codex_session(root, "01999991-aaaa-7000-8000-00000000000a", 1, "a")
    _codex_session(root, "01999992-bbbb-7000-8000-00000000000b", 2, "b")
    monkeypatch.setenv("CODEX_HOME", str(root))
    return ["--codex"], ("01999992-bbbb", "01999991-aaaa"), 7


def _run(corpus, *args):
    """Invoke errors in the fixture scope."""
    flag, _, _ = corpus
    return runner.invoke(app, [*flag, "errors", *args, "--path", "/w"])


def _rows(stdout):
    """Only the error rows, not the block bodies or the trailing summary."""
    return [line for line in stdout.splitlines() if line.startswith("#0")]


def test_every_row_names_its_source_session(corpus):
    """The acceptance case: one sequence, two sessions, still distinguishable."""
    _, (newest, oldest), seq = corpus
    result = _run(corpus, "@1:@2", "--compact")
    assert result.exit_code == 0, result.output
    at_seq = [row for row in _rows(result.stdout) if row.startswith(f"#{seq:04d}")]
    assert len(at_seq) == 2
    assert [row.split()[1] for row in at_seq] == [newest, oldest]


def test_the_source_column_is_a_selector_show_accepts(corpus):
    """A row can be zoomed with nothing but the tokens printed on it."""
    flag, _, seq = corpus
    row = _rows(_run(corpus, "@1:@2", "--compact").stdout)[0]
    number, source = row.split()[0], row.split()[1]
    zoomed = runner.invoke(
        app, [*flag, "show", source, "--around", str(int(number[1:])), "--path", "/w"]
    )
    assert zoomed.exit_code == 0, zoomed.output
    assert f"#{seq:04d}" in zoomed.stdout


def test_single_session_rows_carry_the_source_too(corpus):
    """Identity is unconditional, so a parser sees one column layout everywhere."""
    _, (newest, _), _ = corpus
    rows = _rows(_run(corpus, "@1", "--compact").stdout)
    assert rows and all(row.split()[1] == newest for row in rows)


def test_long_error_text_is_complete_by_default(corpus):
    """Head, middle and tail all survive, and the body keeps its own line breaks."""
    result = _run(corpus, "@1")
    assert result.exit_code == 0, result.output
    assert LONG_HEAD in result.stdout
    assert LONG_TAIL in result.stdout
    assert "unexpected token " * 60 in " ".join(result.stdout.split()) + " "
    assert "chars, middle]" not in result.stdout
    assert "    " + LONG_HEAD in result.stdout  # indented block, not one long row


def test_a_one_line_error_stays_on_its_row(corpus):
    """Complete text does not mean a block for errors that were already one line."""
    _, _, seq = corpus
    row = [r for r in _rows(_run(corpus, "@1").stdout) if r.startswith(f"#{seq:04d}")][0]
    assert row.endswith('"ENOENT: /x b"')


def test_compact_restores_one_trimmed_line_per_error(corpus):
    """--compact is the only thing that trims, and it trims the middle."""
    result = _run(corpus, "@1", "--compact")
    assert result.exit_code == 0, result.output
    assert len(_rows(result.stdout)) == 2
    assert "chars, middle]" in result.stdout
    assert LONG_TAIL in result.stdout  # the ending, where the summary lives, survives
    assert "\n    " not in result.stdout


def test_compact_does_not_reach_json(corpus):
    """--compact is a text flag; raw records stay complete."""
    plain = _run(corpus, "@1", "--json")
    compact = _run(corpus, "@1", "--compact", "--json")
    assert compact.stdout == plain.stdout
    # The record nests the error text as an escaped string, so check the ends survive.
    record = json.dumps(json.loads(compact.stdout.splitlines()[-1]))
    assert LONG_HEAD in record and LONG_TAIL in record
    assert "chars, middle]" not in record


def test_json_emits_complete_distinct_physical_records(corpus):
    """SXR-AUD-005 and SXR-AUD-015: one object per source line, nothing truncated."""
    result = _run(corpus, "@1", "--json")
    assert result.exit_code == 0, result.output
    lines = result.stdout.splitlines()
    assert len(lines) == 2
    for line in lines:
        assert isinstance(json.loads(line), dict)


def test_repeated_tool_results_are_deduplicated_per_transcript(corpus):
    """The second physical record for one call id never becomes a second row."""
    result = _run(corpus, "@1", "--compact")
    assert "(repeat)" not in result.stdout
    assert len(_rows(result.stdout)) == 2


def test_the_row_limit_is_one_allowance_across_sessions(corpus):
    """SXR-AUD-006: -n spans the range, and the omission count says so."""
    result = _run(corpus, "@1:@2", "-n", "1", "--compact")
    assert result.exit_code == 0, result.output
    assert len(_rows(result.stdout)) == 1
    assert "+3 more error records (shown 1 of 4" in result.stdout


def test_the_json_omission_notice_stays_off_stdout(corpus):
    """SXR-AUD-005: stdout under --json is parseable, notices go to stderr."""
    result = _run(corpus, "@1:@2", "--json", "-n", "1")
    assert len(result.stdout.splitlines()) == 1
    assert json.loads(result.stdout)
    assert "more error records" in result.stderr


@pytest.mark.parametrize("limit", ["0", None])
def test_no_limit_and_zero_both_mean_every_record(corpus, limit):
    """-n 0 is unlimited, as it is everywhere else."""
    args = ["@1:@2", "--compact"] + (["-n", limit] if limit else [])
    result = _run(corpus, *args)
    assert len(_rows(result.stdout)) == 4
    assert "more error records" not in result.output


def test_a_negative_limit_is_still_a_usage_error(corpus):
    """SXR-AUD-012, unchanged by the new flag."""
    result = _run(corpus, "@1", "-n", "-1")
    assert result.exit_code == 2
    assert "limit" in result.output
    assert "Traceback" not in result.output


def test_a_scope_with_no_sessions_is_still_a_usage_error(corpus):
    """Unchanged: nothing to select is exit 2, not an empty result."""
    flag, _, _ = corpus
    result = runner.invoke(app, [*flag, "errors", "--path", "/nowhere"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert "no sessions in scope" in result.stderr


def test_a_session_without_errors_exits_one_and_names_the_scope(tmp_path, monkeypatch):
    """Exit 1 is the empty result, and stdout stays clean for a caller's pipeline."""
    project = tmp_path / "clean" / "projects" / "-w"
    project.mkdir(parents=True)
    (project / "dddddddd-0000-4000-8000-00000000000d.jsonl").write_text(
        json.dumps(
            dict(
                type="user",
                timestamp="2026-09-01T12:00:00Z",
                cwd="/w",
                message=dict(role="user", content="no failures here"),
            )
        )
        + "\n"
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "clean"))
    result = runner.invoke(app, ["errors", "--path", "/w"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "no error records in dddddddd" in result.stderr


def test_the_zoom_hint_names_the_session_of_the_first_row(corpus):
    """A range used to print no hint at all, and read the wrong session's rows."""
    _, (newest, _), seq = corpus
    result = _run(corpus, "@1:@2", "--compact")
    hint = [line for line in result.stdout.splitlines() if line.startswith("# zoom:")]
    assert len(hint) == 1
    assert f"--around {seq}" in hint[0]
    assert newest.split("-")[0] in hint[0]


def test_the_summary_counts_every_selected_record_not_the_shown_rows(corpus):
    """The tally is the scope's total, so a limited view still reports the truth."""
    result = _run(corpus, "@1:@2", "-n", "1", "--compact")
    assert "# 4 error records" in result.stdout


def test_colliding_short_ids_widen_the_source_column(tmp_path, monkeypatch):
    """Two sessions sharing a short id prefix stay distinguishable per row."""
    root = tmp_path / "claude"
    _claude_session(root, "cccccccc-0000-4000-8000-00000000000a", "2026-09-01T12:00:00Z", "a")
    _claude_session(root, "cccccccc-0000-4000-8000-00000000000b", "2026-09-02T12:00:00Z", "b")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(root))
    result = runner.invoke(app, ["errors", "@1:@2", "--compact", "--path", "/w"])
    assert result.exit_code == 0, result.output
    sources = {row.split()[1] for row in _rows(result.stdout)}
    assert sources == {
        "cccccccc-0000-4000-8000-00000000000a",
        "cccccccc-0000-4000-8000-00000000000b",
    }


def test_help_documents_complete_text_and_the_compact_escape(corpus):
    """The flag and the new default are both discoverable from --help."""
    flag, _, _ = corpus
    result = runner.invoke(app, [*flag, "errors", "--help"])
    assert result.exit_code == 0
    assert "--compact" in result.stdout
    assert "complete" in result.stdout
