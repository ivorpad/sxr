"""sxr: x-ray Codex and Claude Code sessions from the terminal."""

__version__ = "0.1.0"


def main() -> None:
    """CLI entry point."""
    from sxr.cli import app

    app()
