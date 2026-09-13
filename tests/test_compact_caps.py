"""One compact cap per view, and an environment value that says when it is unusable.

Three claims, each pinned on both providers where both can reach the code:

* Every trimmed row of one view answers to one cap. Before this, a `grep -C`
  invocation printed its match row at a built-in 200 and its context rows at
  `SXR_LINE_LIMIT`, so one view had two caps.
* A tool-result body is not exempt. It used to keep a fixed 200-and-120 middle
  trim whatever cap was asked for, which is the clause SXR-CLI-03 and SXR-CLI-04
  each touched and left open.
* An unusable `SXR_BUDGET`/`SXR_LINE_LIMIT` is reported once, on stderr, and only
  when the command would have used it. Silence was the defect: a typo capped or
  uncapped every command in a shell and said nothing.

The asymmetry D-02 and D-05 settled is pinned here too, so this slice cannot be
read as having quietly harmonized it: `show` refuses a negative cap, `prompts`
still treats one as "never truncate".
"""

import json

import pytest
from typer.testing import CliRunner

from sxr.cli import app
from sxr.util import ONE_LINE_LIMIT, middle_trim

runner = CliRunner()

NEEDLE = "shibboleth"
LONG = f"{NEEDLE} " + " ".join(f"w{n:04d}aaaaaaaaaaaaaa" for n in range(80))
RESULT = f"HEADSTART {LONG} TAILFINISH"


def _claude(root):
    project = root / "projects" / "-w"
    project.mkdir(parents=True)

    def turn(role, content, minute):
        return dict(
            type="assistant" if role == "assistant" else "user",
            timestamp=f"2026-09-10T07:{minute:02d}:00Z",
            cwd="/w",
            message=dict(role=role, content=content),
        )

    records = [
        turn("user", f"open caps {LONG}", 0),
        turn("assistant", [dict(type="text", text=LONG)], 1),
        turn(
            "assistant", [dict(type="tool_use", id="t1", name="Bash", input={"command": LONG})], 2
        ),
        turn("user", [dict(type="tool_result", tool_use_id="t1", content=RESULT)], 3),
        turn(
            "assistant", [dict(type="tool_use", id="t2", name="Bash", input={"command": LONG})], 4
        ),
        turn(
            "user", [dict(type="tool_result", tool_use_id="t2", content=RESULT, is_error=True)], 5
        ),
    ]
    path = project / "abcd0021-0000-4000-8000-000000000021.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return "CLAUDE_CONFIG_DIR", []


def _codex(root):
    directory = root / "sessions" / "2026" / "09" / "10"
    directory.mkdir(parents=True)
    ident = "01999922-cccc-7000-8000-000000000021"
    records = [
        dict(
            timestamp="2026-09-10T07:00:00Z",
            type="session_meta",
            payload=dict(id=ident, cwd="/w", timestamp="2026-09-10T07:00:00Z"),
        ),
        dict(
            timestamp="2026-09-10T07:00:00Z",
            type="event_msg",
            payload=dict(type="user_message", message=f"open caps {LONG}"),
        ),
        dict(
            timestamp="2026-09-10T07:01:00Z",
            type="response_item",
            payload=dict(
                type="message", role="assistant", content=[dict(type="output_text", text=LONG)]
            ),
        ),
        dict(
            timestamp="2026-09-10T07:02:00Z",
            type="event_msg",
            payload=dict(
                type="item_completed",
                item=dict(
                    type="CommandExecution",
                    id="c1",
                    call_id="c1",
                    command=["bash", "-lc", LONG],
                    aggregated_output=RESULT,
                    exit_code=1,
                ),
            ),
        ),
    ]
    path = directory / f"rollout-2026-09-10T07-00-00-{ident}.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return "CODEX_HOME", ["--codex"]


@pytest.fixture(params=["claude", "codex"])
def corpus(request, tmp_path, monkeypatch):
    """A long-text session on one provider, with the flag that selects it."""
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


def widest(text):
    """The longest printed row, which is what a cap change moves first."""
    return max((len(line) for line in text.splitlines() if line), default=0)


def test_grep_match_rows_follow_the_line_limit(corpus, monkeypatch):
    """A match row is not exempt from the cap the rest of the view obeys."""
    monkeypatch.setenv("SXR_LINE_LIMIT", "60")
    narrow = run(corpus, "grep", NEEDLE)
    monkeypatch.setenv("SXR_LINE_LIMIT", "400")
    wide = run(corpus, "grep", NEEDLE)
    assert narrow.exit_code == 0 and wide.exit_code == 0
    assert widest(narrow.stdout) < widest(wide.stdout)


def test_grep_rows_and_context_windows_share_one_cap(corpus, monkeypatch):
    """The defect was two caps in one invocation: the row's and the window's."""
    monkeypatch.setenv("SXR_LINE_LIMIT", "60")
    rows = run(corpus, "grep", NEEDLE)
    windows = run(corpus, "grep", NEEDLE, "-C", "1")
    assert rows.exit_code == 0 and windows.exit_code == 0
    quoted = [line for line in rows.stdout.splitlines() if NEEDLE in line]
    assert quoted, "expected at least one match row"
    # 60 plus the row's own tab-separated prefix and the recovery marker.
    assert all(len(line) < 200 for line in quoted)


def test_line_limit_zero_never_trims_a_match_row(corpus, monkeypatch):
    """0 means no trimming here as it does at every other cap."""
    monkeypatch.setenv("SXR_LINE_LIMIT", "0")
    result = run(corpus, "grep", NEEDLE)
    assert result.exit_code == 0
    assert "chars]" not in result.stdout
    assert widest(result.stdout) > ONE_LINE_LIMIT * 2


def test_compact_error_text_follows_the_line_limit(corpus, monkeypatch):
    """`errors --compact` used to keep fixed widths whatever was asked for."""
    monkeypatch.setenv("SXR_LINE_LIMIT", "60")
    narrow = run(corpus, "errors", "--compact")
    monkeypatch.setenv("SXR_LINE_LIMIT", "400")
    wide = run(corpus, "errors", "--compact")
    assert narrow.exit_code == 0 and wide.exit_code == 0
    assert "chars, middle]" in narrow.stdout
    assert widest(narrow.stdout) < widest(wide.stdout)


def test_plain_errors_still_print_whole_text(corpus, monkeypatch):
    """SXR-CLI-04's default stays: only --compact trims, cap or no cap."""
    monkeypatch.setenv("SXR_LINE_LIMIT", "60")
    result = run(corpus, "errors")
    assert result.exit_code == 0
    assert "TAILFINISH" in result.stdout
    assert "chars, middle]" not in result.stdout


def test_middle_trim_keeps_its_documented_default_split():
    """At the 200 default the head and tail are the 200 and 120 they always were."""
    text = "H" * 1000
    assert middle_trim(text) == middle_trim(text, ONE_LINE_LIMIT)
    trimmed = middle_trim(text)
    head, _, tail = trimmed.partition(" ...[+")
    assert len(head) == 200
    assert len(tail.split("chars, middle]... ")[1]) == 120


def test_middle_trim_scales_with_the_cap_and_zero_disables_it():
    """One number governs it, and 0 means no trimming."""
    text = "H" * 1000
    assert len(middle_trim(text, 60)) < len(middle_trim(text, 400))
    assert middle_trim(text, 0) == text
    assert middle_trim("short", 60) == "short"


def test_unusable_budget_is_reported_once_on_stderr(corpus, monkeypatch):
    """The notice exists, names the value, and does not repeat within one run."""
    monkeypatch.setenv("SXR_BUDGET", "abc")
    result = run(corpus, "show")
    assert result.exit_code == 0
    notices = [line for line in result.stderr.splitlines() if line.startswith("# SXR_BUDGET=")]
    assert len(notices) == 1
    assert "'abc'" in notices[0]
    assert "40000" in notices[0]


def test_a_negative_environment_value_is_reported_not_obeyed(corpus, monkeypatch):
    """It used to reach the footer, which announced a cap of -5 characters."""
    monkeypatch.setenv("SXR_LINE_LIMIT", "-5")
    result = run(corpus, "show", "--budget", "500")
    assert result.exit_code == 0
    assert "# SXR_LINE_LIMIT='-5'" in result.stderr
    assert "-5-char lines" not in result.stdout
    assert f"trimmed to {ONE_LINE_LIMIT}-char lines" in result.stdout


def test_a_usable_environment_value_says_nothing(corpus, monkeypatch):
    """A notice on every invocation of a correctly configured shell would be noise."""
    monkeypatch.setenv("SXR_BUDGET", "500")
    monkeypatch.setenv("SXR_LINE_LIMIT", "0")
    result = run(corpus, "show")
    assert result.exit_code == 0
    assert "SXR_BUDGET" not in result.stderr
    assert "SXR_LINE_LIMIT" not in result.stderr


def test_the_notice_never_reaches_json_stdout(corpus, monkeypatch):
    """--json stdout stays a record contract even from a misconfigured shell."""
    monkeypatch.setenv("SXR_BUDGET", "abc")
    monkeypatch.setenv("SXR_LINE_LIMIT", "abc")
    for args in (["show", "--json"], ["grep", NEEDLE, "--json"], ["cmds", "--json"]):
        result = run(corpus, *args)
        assert result.exit_code in (0, 1), args
        for line in result.stdout.splitlines():
            if line:
                json.loads(line)


def test_an_unused_variable_is_not_reported(corpus, monkeypatch):
    """Only a value the command would have applied is worth a diagnostic."""
    monkeypatch.setenv("SXR_BUDGET", "abc")
    result = run(corpus, "list")
    assert result.exit_code == 0
    assert "SXR_BUDGET" not in result.stderr


def test_grep_refuses_a_negative_budget(corpus):
    """It joins `show --budget`, which D-05 settled; 0 remains the way to say all."""
    refused = run(corpus, "grep", NEEDLE, "--budget", "-1")
    assert refused.exit_code == 2
    assert "--budget" in refused.stderr
    unlimited = run(corpus, "grep", NEEDLE, "--budget", "0")
    assert unlimited.exit_code == 0


def test_show_keeps_refusing_and_prompts_keeps_never_truncating(corpus):
    """D-05 and D-02's asymmetry is deliberate and survives this slice."""
    for flag in ("--budget", "--line-limit"):
        assert run(corpus, "show", flag, "-1").exit_code == 2
        never = run(corpus, "prompts", flag, "-1")
        assert never.exit_code == 0
        assert "chars]" not in never.stdout


def test_a_flag_still_beats_the_environment(corpus, monkeypatch):
    """Precedence is flag, then environment, then default -- and stays that way."""
    monkeypatch.setenv("SXR_BUDGET", "1")
    monkeypatch.setenv("SXR_LINE_LIMIT", "10")
    result = run(corpus, "show", "--budget", "0", "--line-limit", "0")
    assert result.exit_code == 0
    assert "chars]" not in result.stdout
    # The last word of a text body, so a cap of 1 or 10 could not have survived.
    assert LONG.split()[-1] in result.stdout


def test_complete_views_still_ignore_the_budget(corpus, monkeypatch):
    """--full, zooms and --json bypass trimming however small the budget is."""
    monkeypatch.setenv("SXR_BUDGET", "1")
    for args in (["show", "--full"], ["show", "--range", "1:6"], ["show", "--around", "2"]):
        result = run(corpus, *args)
        assert result.exit_code == 0, args
        assert "chars]" not in result.stdout, args
