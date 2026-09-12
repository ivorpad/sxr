# Evidence for SXR-CLI-01

Every file here is the captured output of one command, with its exit code
appended as the last line where the log format allows it.

| File | Command | Exit |
|---|---|---|
| `baseline-pytest.log` / `.xml` | `uv run pytest -q` before any edit | 1 (642 tests, 8 failed) |
| `baseline-lint.log` | `uv run ruff check /tmp/sxr-baseline-0911` | 0 |
| `baseline-format.log` | `uv run ruff format --check /tmp/sxr-baseline-0911` | 0 |
| `baseline-konpy-check.log` | `konpy check` in the extracted baseline snapshot | 0 (96 files) |
| `after-pytest.log` / `.xml` | `uv run pytest -q` after the slice | 0 (676 tests) |
| `matrix-pytest.log` | affected command matrix, 11 modules | 0 (208 tests) |
| `lint.log` | `uv run ruff check .` | 0 |
| `format.log` | `uv run ruff format --check .` | 0 |
| `konpy-validate.log` / `konpy-check.log` | `uv run konpy validate` / `check` | 0 / 0 (98 files) |
| `historical-contracts.log` / `.json` | `uv run python verify_cli.py` from `audit/2026-09-10` | 1 — 66/67, `PROMPTS-filter` fails by design |
| `migrated-contracts.log` / `.json` | `uv run python verify_prompts.py` | 0 (5/5) |
| `prompts-help-after.txt` | `sxr prompts --help` after the slice | 0 |
| `demo-*.txt` | the before/after demonstration below | 0 |

## The demonstration fixture

The `demo-*.txt` captures use a synthetic Codex rollout with no real content:

```python
import json, pathlib

p = pathlib.Path("/tmp/sxr-demo/rollout-demo.jsonl")


def msg(text, kinds=None):
    pay = {"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]}
    if kinds is not None:
        pay["internal_chat_message_metadata_passthrough"] = {"content_item_kinds": kinds}
    return {"type": "response_item", "timestamp": "2026-09-01T12:00:00Z", "payload": pay}


recs = [
    {
        "type": "session_meta",
        "timestamp": "2026-09-01T12:00:00Z",
        "payload": {"id": "demo-0001", "cwd": "/tmp/sxr-demo"},
    },
    msg("# AGENTS.md instructions\nnever do X", ["agents_md.instructions"]),
    msg("please review the prompts command and report what it prints\n" * 900, ["user.text"]),
    {
        "type": "response_item",
        "timestamp": "2026-09-01T12:00:00Z",
        "payload": {"type": "function_call_output", "call_id": "c1", "output": "tool stdout"},
    },
    msg("now fix it", ["user.text"]),
]
p.write_text("\n".join(map(json.dumps, recs)))
```

"Before" was produced by running the extracted baseline snapshot's source:

```bash
PYTHONPATH=/tmp/sxr-baseline-0911/src uv run python -c \
  "import sys; sys.argv=['sxr','prompts','--file','/tmp/sxr-demo/rollout-demo.jsonl']; \
   from sxr.cli import app; app()"
```

`demo-before.stderr.txt` and `demo-after.stderr.txt` record which `sxr/__init__.py`
each run actually imported, so the comparison is not taking the same code twice.
