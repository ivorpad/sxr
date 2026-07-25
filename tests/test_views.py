"""View behavior: prompts selection per provider, adaptive trimming."""

from pathlib import Path

from sxr.model import Event, SessionRef
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
