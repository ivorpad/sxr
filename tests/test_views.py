"""View behavior: prompts selection per provider, adaptive trimming."""

from pathlib import Path

import pytest

from sxr.model import Event, SessionRef
from sxr.views_info import cmds_view
from sxr.views_read import ShowOpts, prompts, show


def _ref(provider: str = "claude") -> SessionRef:
    return SessionRef(provider, "aaaa1111-2222", Path("x.jsonl"))


def test_prompts_codex_prefers_user_message(capsys) -> None:
    events = [
        Event(1, "", "user", "text", "<injected environment blob>"),
        Event(2, "", "user", "user_message", "the actual human prompt"),
        Event(3, "", "user", "result", "tool output"),
    ]
    assert prompts(_ref("codex"), events, False, False, None) == 0
    out = capsys.readouterr().out
    assert "actual human prompt" in out
    assert "injected environment blob" not in out
    assert "--all includes them" in out


def test_prompts_claude_uses_text(capsys) -> None:
    events = [Event(1, "", "user", "text", "hola"), Event(2, "", "user", "result", "x")]
    assert prompts(_ref(), events, False, False, None) == 0
    assert "hola" in capsys.readouterr().out


def test_show_whole_text_under_budget(capsys) -> None:
    events = [Event(1, "", "asst", "text", "line one\nline two")]
    assert show(_ref(), events, ShowOpts()) == 0
    out = capsys.readouterr().out
    assert "line one\nline two" in out
    assert "[+" not in out


def test_show_trims_over_budget_and_says_so(capsys) -> None:
    events = [Event(1, "", "asst", "text", "x" * 500)]
    assert show(_ref(), events, ShowOpts(budget=100, line_limit=50)) == 0
    out = capsys.readouterr().out
    assert "[+450 chars]" in out
    assert "--budget 0" in out


def test_show_hidden_note_names_flags(capsys) -> None:
    events = [
        Event(1, "", "asst", "text", "visible"),
        Event(2, "", "asst", "thinking", "hidden thought"),
        Event(3, "", "user", "result", "hidden result"),
    ]
    assert show(_ref(), events, ShowOpts()) == 0
    out = capsys.readouterr().out
    assert "1 thinking (--thinking)" in out
    assert "1 tool results (--tools)" in out


def test_show_tail_keeps_last_selected_events(capsys) -> None:
    events = [Event(i, "", "asst", "text", f"msg {i}") for i in range(1, 6)]
    assert show(_ref(), events, ShowOpts(tail=2)) == 0
    out = capsys.readouterr().out
    assert "msg 4" in out and "msg 5" in out
    assert "msg 3" not in out


def test_show_tail_is_zoom_never_trims(capsys) -> None:
    events = [
        Event(1, "", "asst", "text", "padding " * 100),
        Event(2, "", "asst", "text", "final report " * 30),
    ]
    assert show(_ref(), events, ShowOpts(tail=1, budget=100)) == 0
    out = capsys.readouterr().out
    assert out.count("final report") == 30
    assert "[+" not in out


def _tool(seq: int, text: str, tag: str = "ok") -> Event:
    return Event(seq, "", "asst", "tool", text, tool="Bash", tag=tag)


def test_cmds_grep_matches_untruncated_command_text(capsys) -> None:
    events = [_tool(1, "git push origin main && echo done"), _tool(2, "ls -la")]
    assert cmds_view([_ref()], lambda _: events, False, None, "git push") == 0
    out = capsys.readouterr().out
    assert "git push" in out
    assert "ls -la" not in out


def test_cmds_grep_smart_case(capsys) -> None:
    events = [_tool(1, "GIT PUSH origin main")]
    assert cmds_view([_ref()], lambda _: events, False, None, "git push") == 0
    assert cmds_view([_ref()], lambda _: events, False, None, "Git Push") == 1


def test_cmds_grep_no_match_exits_1(capsys) -> None:
    events = [_tool(1, "ls -la")]
    assert cmds_view([_ref()], lambda _: events, False, None, "git push") == 1
    assert "no commands matching" in capsys.readouterr().err


def test_cmds_limit_caps_the_whole_scope_not_each_session(capsys) -> None:
    refs = [SessionRef("claude", f"sess{n}111-2222", Path(f"{n}.jsonl")) for n in range(3)]
    events = [_tool(1, "git status"), _tool(2, "git log")]
    assert cmds_view(refs, lambda _: events, False, 2, "git") == 0
    out = capsys.readouterr().out
    assert len([line for line in out.splitlines() if not line.startswith("#")]) == 2
    assert "# 6 commands, showing first 2 (raise -n, or -n 0 for all)" in out


def test_cmds_limit_zero_prints_everything(capsys) -> None:
    events = [_tool(n, f"git log {n}") for n in range(5)]
    assert cmds_view([_ref()], lambda _: events, False, 0, "git") == 0
    out = capsys.readouterr().out
    assert out.count("git log") == 5
    assert "showing first" not in out


def test_cmds_bad_grep_regex_exits_2_naming_its_own_flag(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        cmds_view([_ref()], lambda _: [_tool(1, "ls")], False, None, "foo(")
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "bad regex 'foo('" in err
    assert "--grep 'foo\\('" in err


def test_limit_zero_means_every_row(capsys) -> None:
    events = [Event(i, "", "asst", "text", f"msg {i}") for i in range(1, 6)]
    assert show(_ref(), events, ShowOpts(limit=0)) == 0
    out = capsys.readouterr().out
    assert out.count("msg ") == 5
    assert "more events" not in out


def test_show_range_accepts_the_grep_dash_habit(capsys) -> None:
    events = [Event(i, "", "asst", "text", f"msg {i}") for i in range(1, 6)]
    assert show(_ref(), events, ShowOpts(range_="2-4")) == 0
    out = capsys.readouterr().out
    assert "msg 2" in out and "msg 4" in out
    assert "msg 1" not in out and "msg 5" not in out


def test_show_bad_range_teaches_the_colon_form(capsys) -> None:
    events = [Event(1, "", "asst", "text", "msg 1")]
    with pytest.raises(SystemExit) as exc:
        show(_ref(), events, ShowOpts(range_="junk"))
    assert exc.value.code == 2
    assert "format is A:B, e.g. --range 10:50" in capsys.readouterr().err
