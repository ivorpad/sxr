"""sxr: x-ray Codex and Claude Code sessions from the terminal."""

__version__ = "0.8.0"


def main() -> None:
    """CLI entry point."""
    import sys

    if sys.argv[1:2] == ["find"]:
        from sxr.find_cli import main as find

        raise SystemExit(find(sys.argv[2:]))
    from sxr.cli import app

    app()
