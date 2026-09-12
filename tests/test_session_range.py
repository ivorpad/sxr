"""An @A:@B range renders every selected session, not only the first one.

Each session in a range is named by one `# session @N  <id>  <path>` banner --
on stdout for text, on stderr for --json, where stdout is a raw record contract.
A selection of one session must stay byte-identical to what it printed before.
"""

import json

import pytest
from typer.testing import CliRunner

from sxr.cli import app

runner = CliRunner()
BANNER = "# session "
LONG = "long human request " * 3000 + "unique ending"
OLDER = ("older ask", "ToolAlpha")
NEWER = ("newer ask", "ToolBeta")


def _claude(root, name, started, prompt, tool):
    """One Claude transcript: a human prompt, a tool call, and its result."""
    stamp = f"{started}T10:00:00.000Z"
    records = [
        {
            "type": "user",
            "cwd": "/w",
            "timestamp": stamp,
            "message": {"role": "user", "content": prompt},
        },
        {
            "type": "user",
            "cwd": "/w",
            "timestamp": stamp,
            "isMeta": True,
            "message": {"role": "user", "content": "injected context"},
        },
        {
            "type": "assistant",
            "timestamp": stamp,
            "message": {
                "content": [
                    {"type": "tool_use", "id": "t1", "name": tool, "input": {"command": "just"}}
                ]
            },
        },
    ]
    path = root / f"{name}.jsonl"
    path.write_text("\n".join(map(json.dumps, records)))
    return path


def _codex(root, session_id, started, prompt, tool):
    """One Codex rollout with a labelled human prompt and a labelled context item."""
    day = root / "sessions" / "2026" / "09" / started[-2:]
    day.mkdir(parents=True, exist_ok=True)
    stamp = f"{started}T10:00:00.000Z"

    def item(text, kinds):
        return {
            "timestamp": stamp,
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{"type": "text", "text": text}],
                "internal_chat_message_metadata_passthrough": {"content_item_kinds": kinds},
            },
        }

    records = [
        {
            "timestamp": stamp,
            "type": "session_meta",
            "payload": {"session_id": session_id, "cwd": "/w", "originator": "codex_exec"},
        },
        item(prompt, ["user.text"]),
        item("injected context", ["agents_md.instructions"]),
        {
            "timestamp": stamp,
            "type": "response_item",
            "payload": {"type": "function_call", "name": tool, "arguments": "{}", "call_id": "c1"},
        },
    ]
    path = day / f"rollout-2026-09-{started[-2:]}T10-00-00-{session_id[:8]}.jsonl"
    path.write_text("\n".join(map(json.dumps, records)))
    return path


@pytest.fixture(params=["claude", "codex"])
def scope(request, tmp_path, monkeypatch):
    """Two sessions of one provider in one cwd, newest first, plus its CLI flag."""
    monkeypatch.setenv("SXR_CACHE_DIR", str(tmp_path / "cache"))
    if request.param == "claude":
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / ".claude"))
        root = tmp_path / ".claude" / "projects" / "-w"
        root.mkdir(parents=True)
        older = _claude(root, "aaaa1111-2222-3333-4444-555566667777", "2026-09-01", *OLDER)
        newer = _claude(root, "bbbb2222-3333-4444-5555-666677778888", "2026-09-02", *NEWER)
        return ["--claude"], newer, older
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    root = tmp_path / ".codex"
    older = _codex(root, "019f9510-5499-72a0-80b1-782880a12e01", "2026-09-01", *OLDER)
    newer = _codex(root, "019f9520-5499-72a0-80b1-782880a12e02", "2026-09-02", *NEWER)
    return ["--codex"], newer, older


def _run(scope, command, *args):
    provider, _, _ = scope
    return runner.invoke(app, [command, *provider, "--path", "/w", *args])


def _rows(command, stdout):
    """The data rows of a view: event lines for show/prompts, tool rows for tools."""
    lines = stdout.splitlines()
    if command == "tools":
        return [line for line in lines if line and not line.startswith("#")]
    return [line for line in lines if line.startswith("#0")]


@pytest.mark.parametrize("command", ["show", "prompts", "tools"])
def test_range_renders_every_selected_session(scope, command):
    _, newer, older = scope
    result = _run(scope, command, "@1:@2")
    assert result.exit_code == 0, result.output
    banners = [line for line in result.stdout.splitlines() if line.startswith(BANNER)]
    assert len(banners) == 2
    assert str(newer) in banners[0] and str(older) in banners[1]
    assert "@1" in banners[0] and "@2" in banners[1]


@pytest.mark.parametrize("command", ["show", "prompts", "tools"])
def test_range_carries_content_from_both_sessions(scope, command):
    result = _run(scope, command, "@1:@2")
    assert result.exit_code == 0, result.output
    wanted = ("ToolAlpha", "ToolBeta") if command == "tools" else ("newer ask", "older ask")
    for text in wanted:
        assert text in result.stdout


@pytest.mark.parametrize("command", ["show", "prompts", "tools"])
@pytest.mark.parametrize("selector", ["@1", "@1:@1"])
def test_single_session_output_is_unchanged(scope, command, selector):
    """One selected session takes the pre-range path: no banner, same rows."""
    plain = _run(scope, command)
    result = _run(scope, command, selector)
    assert result.exit_code == 0, result.output
    assert result.stdout == plain.stdout
    assert BANNER not in result.stdout and BANNER not in result.stderr


@pytest.mark.parametrize("command", ["show", "prompts", "tools"])
def test_inverted_range_matches_its_normal_form(scope, command):
    forward = _run(scope, command, "@1:@2")
    inverted = _run(scope, command, "@2:@1")
    assert inverted.exit_code == 0, inverted.output
    assert inverted.stdout == forward.stdout


@pytest.mark.parametrize("command", ["show", "prompts", "tools"])
def test_range_beyond_the_scope_is_a_usage_error(scope, command):
    result = _run(scope, command, "@1:@9")
    assert result.exit_code == 2, result.output
    assert "out of range" in result.output and "Traceback" not in result.output


@pytest.mark.parametrize("command", ["show", "prompts", "tools"])
def test_row_limit_is_one_allowance_across_the_range(scope, command):
    """-n caps rows for the whole invocation, as it already does for errors."""
    result = _run(scope, command, "@1:@2", "-n", "1")
    assert result.exit_code == 0, result.output
    assert len(_rows(command, result.stdout)) == 1
    assert "more" in result.stdout
    unlimited = _rows(command, _run(scope, command, "@1:@2", "-n", "0").stdout)
    each = [len(_rows(command, _run(scope, command, handle).stdout)) for handle in ("@1", "@2")]
    assert len(unlimited) == sum(each) > 1


@pytest.mark.parametrize("command", ["show", "prompts", "tools"])
def test_json_keeps_stdout_parseable_and_identifies_on_stderr(scope, command):
    _, newer, older = scope
    result = _run(scope, command, "@1:@2", "--json")
    assert result.exit_code == 0, result.output
    for line in result.stdout.splitlines():
        assert isinstance(json.loads(line), dict)
    banners = [line for line in result.stderr.splitlines() if line.startswith(BANNER)]
    assert len(banners) == 2
    assert str(newer) in banners[0] and str(older) in banners[1]


@pytest.mark.parametrize("command", ["show", "prompts"])
def test_json_emits_every_session_record_exactly_once(scope, command):
    """Dedup stays per transcript, so a range neither drops nor repeats a record."""
    result = _run(scope, command, "@1:@2", "--json", "-n", "0")
    assert result.exit_code == 0, result.output
    each = [
        len(_run(scope, command, handle, "--json", "-n", "0").stdout.splitlines())
        for handle in ("@1", "@2")
    ]
    assert len(result.stdout.splitlines()) == sum(each) > 1


def test_json_row_limit_spans_the_range(scope):
    result = _run(scope, "prompts", "@1:@2", "--json", "-n", "1")
    assert result.exit_code == 0, result.output
    assert len(result.stdout.splitlines()) == 1
    assert "shown 1 of 2" in result.stderr


def test_all_lifts_the_shared_limit_across_the_range(scope):
    limited = _run(scope, "prompts", "@1:@2", "-n", "1")
    lifted = _run(scope, "prompts", "@1:@2", "-n", "1", "--all")
    assert lifted.exit_code == 0, lifted.output
    assert len(_rows("prompts", lifted.stdout)) == 2 and "more" not in lifted.stdout
    assert len(_rows("prompts", limited.stdout)) == 1


def test_include_context_widens_every_session_in_the_range(scope):
    result = _run(scope, "prompts", "@1:@2", "--include-context")
    assert result.exit_code == 0, result.output
    assert result.stdout.count("injected context") == 2
    assert result.stdout.count("2 of 2 user records shown") == 2


def test_budget_requests_compact_text_per_session(scope):
    """A range still trims only when asked, and says so for each session."""
    _, newer, _ = scope
    newer.write_text(newer.read_text().replace("newer ask", LONG, 1))
    plain = _run(scope, "prompts", "@1:@2")
    assert "unique ending" in plain.stdout and "chars]" not in plain.stdout
    result = _run(scope, "prompts", "@1:@2", "--budget", "1", "--line-limit", "20")
    assert result.exit_code == 0, result.output
    assert "chars]" in result.stdout and "unique ending" not in result.stdout
    assert "older ask" in result.stdout


def test_empty_selection_exits_one_only_when_no_session_produced_output(scope):
    result = _run(scope, "show", "@1:@2", "--type", "missing")
    assert result.exit_code == 1, result.output
    partial = _run(scope, "show", "@1:@2", "--type", "text")
    assert partial.exit_code == 0, partial.output


def test_tools_json_keeps_one_complete_aggregate_per_session(scope):
    """SXR-AUD-007 holds across a range: -n never prunes keys from an aggregate."""
    result = _run(scope, "tools", "@1:@2", "--json", "-n", "1")
    assert result.exit_code == 0, result.output
    objects = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(objects) == 2
    assert [set(o) for o in objects] == [{"type", "calls", "errors", "skill_inputs"}] * 2
    assert {tool for o in objects for tool in o["calls"]} == {"ToolAlpha", "ToolBeta"}


def test_cached_and_uncached_range_reads_agree(scope, monkeypatch):
    """show reads each transcript through its own cache entry, so a range is stable."""
    cold = _run(scope, "show", "@1:@2")
    warm = _run(scope, "show", "@1:@2")
    monkeypatch.setenv("SXR_NO_CACHE", "1")
    direct = _run(scope, "show", "@1:@2")
    assert cold.exit_code == 0 and warm.stdout == cold.stdout == direct.stdout


def test_a_session_without_prompts_does_not_sink_the_range(scope):
    """One empty session reports itself on stderr; the range still exits 0."""
    _, _, older = scope
    older.write_text(
        "\n".join(line for line in older.read_text().splitlines() if "older ask" not in line)
    )
    result = _run(scope, "prompts", "@1:@2")
    assert result.exit_code == 0, result.output
    assert "newer ask" in result.stdout
    assert "no user text records" in result.stderr


def test_providers_cannot_be_mixed_in_one_range():
    """A scope is one provider, so no range can span Claude and Codex."""
    result = runner.invoke(app, ["prompts", "--claude", "--codex", "@1:@2"])
    assert result.exit_code == 2, result.output
    assert "mutually exclusive" in result.output
