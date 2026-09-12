"""init --write refuses to replace an installed primer with a lesser one.

The primer ships inside other repositories, so a rewrite from a forked checkout
can delete guidance a newer sxr installed. These tests pin the refusal, the
--force override, and the fact that --check never recommends a losing write.
"""

from pathlib import Path

import pytest
import typer.main
from typer.testing import CliRunner

import sxr
from sxr.cli import app
from sxr.onboard import (
    VERBS,
    DowngradeError,
    block_body,
    install_primer,
    primer,
    release,
    surfaces,
    write_hazard,
)
from sxr.primer_text import PRIMER_BODY

runner = CliRunner()

CLOSE = "<!-- /sxr:primer -->"

# The shape of the real hazard: a published primer that documents a flag this
# binary's body never mentions, so replacing the block deletes its only guidance.
# `--conversations` is synthetic -- the hazard that motivated the guard was the
# real `--latest`, and this tree documents that again since the reconciliation,
# so a fixture flag is needed to keep exercising the refusal.
NEWER_BODY = """## sxr: search past agent sessions

human requests        sxr prompts @N
- Bare prompts lists human sessions; prompts --conversations lists them too.
"""


def block(version: str, body: str) -> str:
    """An installed primer block with an arbitrary stamp and body."""
    return f"<!-- sxr:primer v{version} -->\n{body}{CLOSE}\n"


def installed(tmp_path: Path, version: str, body: str) -> Path:
    """A scratch context file with prose on both sides of a primer block."""
    target = tmp_path / "AGENTS.md"
    target.write_text(f"# House rules\n\nno tabs.\n\n{block(version, body)}\nlocal prose below.\n")
    return target


def test_verbs_are_exactly_this_app_s_commands() -> None:
    # A stale list would silently stop detecting a dropped command.
    assert set(VERBS) == set(typer.main.get_command(app).commands)


def test_surfaces_collects_flags_and_commands_but_not_prose() -> None:
    found = surfaces("Run sxr cmds --all-sessions to search history, never sxr nonsense.\n")
    assert found == {"--all-sessions", "sxr cmds"}


def test_release_parses_dotted_numbers_only() -> None:
    assert release("0.14.0") == (0, 14, 0)
    assert release("1.2") == (1, 2)
    assert release(None) is None
    assert release("") is None
    assert release("0.14.0rc1") is None
    assert release("main") is None


def test_a_dropped_flag_is_a_hazard_whatever_the_stamps_say() -> None:
    # The stamps are ordered the safe way round and it is still a hazard.
    # Only the flag is named: this body does document `sxr prompts`, just not it.
    assert write_hazard(NEWER_BODY, "0.13.0", "0.14.0") == (
        "this binary's primer does not mention --conversations"
    )


def test_a_newer_stamp_is_a_hazard_even_with_this_exact_body() -> None:
    hazard = write_hazard(PRIMER_BODY, "9.9.9", sxr.__version__)
    assert hazard == f"the installed primer is v9.9.9, newer than this binary's v{sxr.__version__}"


def test_rewording_is_not_a_hazard() -> None:
    reworded = PRIMER_BODY.replace("Before re-deriving", "Before you re-derive")
    assert reworded != PRIMER_BODY
    assert write_hazard(reworded, "0.13.0", "0.14.0") is None


def test_write_refuses_the_published_shape_and_leaves_the_file_byte_identical(
    tmp_path: Path,
) -> None:
    target = installed(tmp_path, "0.13.0", NEWER_BODY)
    before = target.read_bytes()
    result = runner.invoke(app, ["init", "--write", str(target)])
    assert result.exit_code == 2
    assert target.read_bytes() == before
    assert "refusing to replace the primer" in result.stderr
    assert "--conversations" in result.stderr
    assert "--force" in result.stderr


def test_check_names_the_hazard_and_does_not_recommend_a_write(tmp_path: Path) -> None:
    target = installed(tmp_path, "0.13.0", NEWER_BODY)
    result = runner.invoke(app, ["init", "--check", str(target)])
    assert result.exit_code == 1
    assert "would lose guidance" in result.stderr
    assert "Leave it alone" in result.stderr
    # The old advice is what made the hazard reachable, so it must be absent.
    assert "run sxr init --write" not in result.stderr


def test_check_still_recommends_a_write_when_nothing_would_be_lost(tmp_path: Path) -> None:
    target = installed(tmp_path, "0.0.1", "## sxr\n\nnothing documented here.\n")
    result = runner.invoke(app, ["init", "--check", str(target)])
    assert result.exit_code == 1
    assert "run sxr init --write" in result.stderr


def test_force_overwrites_and_still_keeps_the_neighbouring_prose(tmp_path: Path) -> None:
    target = installed(tmp_path, "0.13.0", NEWER_BODY)
    result = runner.invoke(app, ["init", "--write", "--force", str(target)])
    assert result.exit_code == 0
    text = target.read_text()
    assert "replaced" in result.stdout
    assert text.startswith("# House rules\n\nno tabs.\n\n")
    assert text.endswith("\nlocal prose below.\n")
    assert "--conversations" not in text


def test_force_needs_write(tmp_path: Path) -> None:
    target = installed(tmp_path, "0.13.0", NEWER_BODY)
    before = target.read_bytes()
    result = runner.invoke(app, ["init", "--check", "--force", str(target)])
    assert result.exit_code == 2
    assert "--force only applies to --write" in result.stderr
    assert target.read_bytes() == before


def test_a_legitimate_refresh_replaces_and_preserves_prose(tmp_path: Path) -> None:
    # An older primer whose surfaces this body all still documents.
    older = PRIMER_BODY.replace("sxr cmds --all-sessions --grep", "sxr cmds --grep")
    target = installed(tmp_path, "0.12.2", older)
    assert runner.invoke(app, ["init", "--write", str(target)]).exit_code == 0
    text = target.read_text()
    assert f"<!-- sxr:primer v{sxr.__version__} -->" in text
    assert text.startswith("# House rules\n\nno tabs.\n\n")
    assert text.endswith("\nlocal prose below.\n")
    assert "--all-sessions" in text


def test_a_refresh_is_still_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text("prose\n")
    assert install_primer(target, sxr.__version__) == "appended"
    once = target.read_bytes()
    assert install_primer(target, sxr.__version__) == "unchanged"
    assert target.read_bytes() == once


@pytest.mark.parametrize("existing", ["", "prose only\n"])
def test_creating_and_appending_are_never_gated(tmp_path: Path, existing: str) -> None:
    # Neither can lose an installed primer, so neither consults the hazard check.
    target = tmp_path / "nested" / "AGENTS.md"
    target.parent.mkdir(parents=True)
    if existing:
        target.write_text(existing)
        assert install_primer(target, "0.0.1") == "appended"
    else:
        assert install_primer(target, "0.0.1") == "created"
    assert primer("0.0.1") in target.read_text()


def test_install_primer_raises_rather_than_writing_a_lesser_primer(tmp_path: Path) -> None:
    target = installed(tmp_path, "0.13.0", NEWER_BODY)
    before = target.read_bytes()
    with pytest.raises(DowngradeError):
        install_primer(target, sxr.__version__)
    assert target.read_bytes() == before
    assert install_primer(target, sxr.__version__, force=True) == "replaced"


def test_check_reports_a_body_reissued_under_the_same_stamp(tmp_path: Path) -> None:
    # The defect this fixes: check compared only the stamp, so a reissued body
    # under an unchanged version was reported up to date.
    reworded = PRIMER_BODY.replace("Before re-deriving", "Before you re-derive")
    target = installed(tmp_path, sxr.__version__, reworded)
    result = runner.invoke(app, ["init", "--check", str(target)])
    assert result.exit_code == 1
    assert "stamped this version but its body differs" in result.stderr


def test_check_is_still_quiet_and_zero_when_truly_current(tmp_path: Path) -> None:
    target = installed(tmp_path, sxr.__version__, PRIMER_BODY)
    result = runner.invoke(app, ["init", "--check", str(target)])
    assert result.exit_code == 0
    assert "up to date" in result.stderr


def test_block_body_recovers_the_installed_text_exactly(tmp_path: Path) -> None:
    from sxr.onboard import find_block

    target = installed(tmp_path, "0.13.0", NEWER_BODY)
    text = target.read_text()
    span = find_block(text)
    assert span is not None
    assert block_body(text, span) == NEWER_BODY


def test_this_tree_s_primer_documents_every_surface_the_published_one_did() -> None:
    # The reconciliation adopted --latest, so the published primer is no longer
    # a superset and installing over it is no longer a loss.
    published = {"--all-projects", "--json", "--paths", "--latest", "--grep", "sxr prompts"}
    assert sorted(published - surfaces(PRIMER_BODY)) == []
