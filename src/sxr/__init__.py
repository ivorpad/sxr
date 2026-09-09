"""sxr: x-ray Codex and Claude Code sessions from the terminal."""

__version__ = "0.12.2"


def main() -> None:
    """CLI entry point."""
    import sys

    if sys.argv[1:2] == ["skills"]:
        from sxr.skills_cli import main as skills

        raise SystemExit(skills(sys.argv[2:]))
    if sys.argv[1:2] == ["serve"]:
        from sxr.find_worker import main as worker

        raise SystemExit(worker(sys.argv[2:]))
    if sys.argv[1:2] == ["find"]:
        from sxr.find_cli import main as find

        raise SystemExit(find(sys.argv[2:]))
    from sxr.cli import app

    app()
