# SXR-AUD-017: The documented empty-result exit code omits the list exception

P3 · Open · Audited working tree based on `48b11c6`

Consumers following the global exit-code description cannot infer whether an empty listing is a miss or a successful command.

**Expected:** The exit-code reference clearly describes list returning 0 for an empty scope, if that deliberate exception remains.

**Observed:** README and top-level help say exit 1 means an empty result. list_scope explicitly returns 0 for an empty scope, and test_empty_json_list_keeps_stdout_machine_readable asserts that behavior.

**Requirement basis:** Documentation consistency, confirmed by the existing empty-list CLI test

Reproduce from the repository root. The harness uses temporary synthetic files and records each CLI exit code, stdout and stderr. A failing contract makes the harness exit 1.

```bash
rtk proxy .venv/bin/python -m pytest tests/test_discovery.py::test_empty_json_list_keeps_stdout_machine_readable
```

This existing test passes and confirms the implemented exception. The discrepancy is in the global exit-code documentation.

Source locations:

- [src/sxr/views_info.py:37](../../../src/sxr/views_info.py#L37) `list_scope`
- [src/sxr/onboard.py:12](../../../src/sxr/onboard.py#L12) `EPILOG`

Acceptance criteria:

- [ ] Document the empty-list exception in the README and help, or adopt a consistent behavior after reviewing compatibility.
- [ ] Keep the primer exit-code guidance consistent with the chosen rule.

Feature IDs: `DOC-EXIT-CODES`
