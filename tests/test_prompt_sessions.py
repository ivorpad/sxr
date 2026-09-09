"""Default prompt discovery must reach human sessions past newer background work."""

import json
import shlex

import pytest
from typer.testing import CliRunner

from sxr.cli import app
from sxr.providers import claude_code, codex

runner = CliRunner()


def _text(text, kind="user.text"):
    return {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
            "internal_chat_message_metadata_passthrough": {"content_item_kinds": [kind]},
        },
    }


@pytest.fixture
def scope(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    home = tmp_path / "codex"
    monkeypatch.setenv("CODEX_HOME", str(home))
    folder = home / "sessions"
    folder.mkdir(parents=True)

    def write(name, day, source, records, cwd=project):
        path = folder / f"rollout-{name}.jsonl"
        meta = {
            "type": "session_meta",
            "timestamp": f"2026-09-{day:02d}T12:00:00Z",
            "payload": {"id": name, "cwd": str(cwd), "source": source},
        }
        path.write_text("\n".join(json.dumps(record) for record in [meta, *records]))
        return path

    instructions = _text("injected setup", "agents_md.instructions")
    human = _text("the latest human request")
    write("older", 1, "cli", [_text("older request")])
    selected = write("human", 2, "cli", [instructions, human])
    empty = write("empty", 3, "cli", [instructions])
    review = write("review", 4, "guardian_review", [_text("automated review request")])
    inherited = write(
        "inherited",
        5,
        {"subagent": {"thread_spawn": {"parent_thread_id": "human", "depth": 1}}},
        [_text("inherited human request")],
    )
    child = write("child", 6, "subagent", [instructions])
    write("unrelated", 7, "cli", [_text("another project")], tmp_path / "other")
    return dict(
        selected=selected,
        empty=empty,
        child=child,
        inherited=inherited,
        review=review,
        human=human,
        instructions=instructions,
        project=project,
    )


@pytest.mark.parametrize(
    "flags",
    [
        ["prompts", "--codex"],
        ["--codex", "prompts"],
        ["prompts", "--codex", "--json"],
        ["prompts", "--codex", "--all"],
    ],
)
def test_default_reaches_latest_human_session(scope, flags):
    result = runner.invoke(app, flags)
    assert result.exit_code == 0, result.output
    assert "the latest human request" in result.stdout
    for text in (
        "older request",
        "automated review request",
        "inherited human request",
        "another project",
    ):
        assert text not in result.stdout
    assert "human" in result.stderr and "skipped 4" in result.stderr
    if "--json" in flags:
        assert json.loads(result.stdout) == scope["human"]
    else:
        assert ("injected setup" in result.stdout) == ("--all" in flags)


@pytest.mark.parametrize("window,handle", [([], "@5"), (["--before", "2026-09-06"], "@4")])
def test_prompt_output_supplies_a_working_session_list(
    scope, monkeypatch, tmp_path, window, handle
):
    result = runner.invoke(app, ["--codex", *window, "prompts"])
    assert result.exit_code == 0, result.output
    assert f"# prompts: {handle} human" in result.stderr
    listing = next(
        line.removeprefix("# sessions: ")
        for line in result.stderr.splitlines()
        if line.startswith("# sessions: ")
    )
    command = shlex.split(listing)
    assert command[0] == "env"
    sxr_index = command.index("sxr")
    # Follow the printed command after changing directory and Codex profile.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "wrong-profile"))
    with monkeypatch.context() as copied_environment:
        for assignment in command[1:sxr_index]:
            key, value = assignment.split("=", 1)
            copied_environment.setenv(key, value)
        args = command[sxr_index + 1 :]
        listed = runner.invoke(app, args)
        assert listed.exit_code == 0, listed.output
        assert f"{handle}\thuman\t" in listed.stdout
        selected = runner.invoke(app, [*args[:-1], "prompts", handle, "--json"])
        assert selected.exit_code == 0, selected.output
        assert json.loads(selected.stdout) == scope["human"]


def test_explicit_file_does_not_invent_a_global_handle(scope):
    result = runner.invoke(app, ["prompts", "--file", str(scope["selected"])])
    assert result.exit_code == 0, result.output
    assert "# prompts: human (--file)" in result.stderr
    assert "# sessions:" not in result.stderr
    assert "@1" not in result.stderr


def test_default_parses_only_candidates_until_a_human_session(scope, monkeypatch):
    paths = []
    parse = codex.parse

    def tracked(path):
        paths.append(path)
        return parse(path)

    monkeypatch.setattr(codex, "parse", tracked)
    result = runner.invoke(app, ["prompts", "--codex"])
    assert result.exit_code == 0, result.output
    assert paths == [scope["empty"], scope["selected"]]


@pytest.mark.parametrize("selector", ["child", "@1", "empty", "@4"])
def test_explicit_empty_session_never_falls_back(scope, selector):
    result = runner.invoke(app, ["prompts", "--codex", selector, "--json"])
    assert result.exit_code == 1
    assert result.stdout == ""
    all_records = runner.invoke(app, ["prompts", "--codex", selector, "--all", "--json"])
    assert all_records.exit_code == 0, all_records.output
    assert json.loads(all_records.stdout) == scope["instructions"]


@pytest.mark.parametrize("name", ["child", "empty"])
def test_explicit_file_never_falls_back(scope, name):
    result = runner.invoke(app, ["prompts", "--file", str(scope[name]), "--json"])
    assert result.exit_code == 1
    assert result.stdout == ""


@pytest.mark.parametrize(
    "name,expected",
    [("review", "automated review request"), ("inherited", "inherited human request")],
)
def test_background_sessions_remain_explicitly_readable(scope, name, expected):
    result = runner.invoke(app, ["prompts", "--codex", name])
    assert result.exit_code == 0, result.output
    assert expected in result.stdout
    assert "skipped" not in result.stderr


def test_no_human_session_reports_scope_not_an_arbitrary_child(scope):
    scope["selected"].unlink()
    (scope["selected"].parent / "rollout-older.jsonl").unlink()
    result = runner.invoke(app, ["prompts", "--codex", "--json"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "no human prompts in 4 sessions in scope" in result.stderr


def test_default_respects_the_selected_date_window(scope):
    result = runner.invoke(app, ["--codex", "--before", "2026-09-02", "prompts"])
    assert result.exit_code == 0, result.output
    assert "older request" in result.stdout
    assert "the latest human request" not in result.stdout


def test_claude_default_skips_empty_roots_and_nested_agents(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
    project = home / "projects" / claude_code.flatten_cwd(str(tmp_path))
    project.mkdir(parents=True)
    human = {
        "type": "user",
        "cwd": str(tmp_path),
        "timestamp": "2026-09-01T12:00:00Z",
        "message": {"role": "user", "content": "human Claude request"},
    }
    (project / "human.jsonl").write_text(json.dumps(human))
    empty = {
        **human,
        "timestamp": "2026-09-02T12:00:00Z",
        "isMeta": True,
        "message": {"role": "user", "content": "injected rules"},
    }
    (project / "empty.jsonl").write_text(json.dumps(empty))
    children = project / "human" / "subagents"
    children.mkdir(parents=True)
    child = {
        **human,
        "timestamp": "2026-09-03T12:00:00Z",
        "message": {"role": "user", "content": "inherited child prompt"},
    }
    (children / "agent-child.jsonl").write_text(json.dumps(child))
    result = runner.invoke(app, ["prompts", "--include-agents", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == human
    assert "skipped 2" in result.stderr
