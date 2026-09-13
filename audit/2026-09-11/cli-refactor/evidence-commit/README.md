# evidence-commit — gates re-run after the audit-trail commits

2026-09-12, after `b70f3ac` (finding 6's wording) and `f42b1ad` (the audit
documents and the new `.gitignore` rules).

| Check | Result |
|---|---|
| `pytest` | 951 passed, 0 failed |
| `ruff check .` | exit 0 |
| `ruff format --check .` | 193 files, exit 0 |
| `konpy check` | 109 files, 0 violations |
| `verify_cli.py --output …` | 66 passed, 1 failed (`PROMPTS-filter`, by design) |
| `verify_prompts.py --output …` | 5 passed, 0 failed |

No status changed. Both commits are documentation only; `b70f3ac` touches three
source and prose files whose only change is wording, and `f42b1ad` adds no file
that ships.

This directory is itself excluded by the new rules, except for this `README.md`.
