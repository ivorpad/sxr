# Audit remediation

Resolved 17 findings. The fresh suite has 632 passing tests; all 67 CLI contracts pass.

[Issue dispositions and regression tests](resolutions.json) · [Current feature map](features.json) · [Feature table](features.csv) · [Verification runs](verification.json)

The original audit remains unchanged. Each verification run records its source hashes, exit code and output hashes. This report rejects changed source or evidence.

| Issue | Disposition | Change |
|---|---|---|
| SXR-AUD-001 | fixed | Audit the decoded stored values with the cleaner's structured detector, once per physical record. Tool display summaries no longer determine coverage. |
| SXR-AUD-002 | fixed | Compare UTC datetime values, including offset and fractional boundaries. A missing or invalid session start cannot establish membership in a bounded window. |
| SXR-AUD-003 | fixed | Preserve isApiErrorMessage on error-bearing events without assigning a tool call a false outcome. Multiple text blocks emit their original JSON record once. Invalidate older read-position snapshots. |
| SXR-AUD-004 | fixed | Use the same SQLite unicode61 tokenizer for finding the excerpt location as for retrieval. Cut the original string at source offsets. |
| SXR-AUD-005 | fixed | Limit complete distinct physical JSON records in show, prompts and errors. Omission counts go to stderr. |
| SXR-AUD-006 | fixed | Share the errors row allowance across selected sessions and report the full omitted count in both formats. |
| SXR-AUD-007 | fixed | Apply -n to tool rows, stat rows, paths and cleaning report rows. JSON aggregate objects retain all fields. A cleaning report limit never changes which selected files are scanned or rewritten. |
| SXR-AUD-008 | fixed | Full views bypass the character budget while retaining row limits and complete selected text. |
| SXR-AUD-009 | fixed | Attach each Claude tool input to its own event and count only that Skill call, excluding unrelated tools. |
| SXR-AUD-010 | fixed | Empty show selections return 1 in both text and JSON, with and without the read cache. |
| SXR-AUD-011 | fixed | Choose zero selected events for --tail 0, with empty-result exit 1. Negative tails are usage errors. This is distinct from the documented unlimited -n 0. |
| SXR-AUD-012 | fixed | Reject negative row limits before discovery in the shared Typer option. Existing fast find and skills validation agrees. Root, group and command flag positions retain the same rule. |
| SXR-AUD-013 | fixed | Path JSON emits path objects. Clean JSON emits masked file-result objects with applied state, counts and kinds. Diagnostics and totals remain on stderr. |
| SXR-AUD-014 | fixed | Compute all distinct-secret and severity totals before slicing. Limited and unlimited output retain the same fingerprints. |
| SXR-AUD-015 | fixed | Skip non-object JSONL records like malformed syntax, in both providers and index parsing. Later valid records retain physical line numbers. Files are not rewritten. |
| SXR-AUD-016 | fixed | Catch filesystem and text-decoding failures at the init command boundary, name the destination and return 2. Preserve existing files on denied access. |
| SXR-AUD-017 | fixed | Keep the deliberate successful empty listing for compatibility. State the exception in README, top-level help and generated primer. |

The macOS arm64 bundle passed relocation verification with an empty PATH. Linux/x86_64, older OS compatibility, Homebrew installation and historical benchmarks remain unverified. See the feature map for the exact exclusions.

Behavior choices: negative row limits and tails return 2; -n 0 is unlimited; --tail 0 selects no events and returns 1. Empty listing retains exit 0. Cleaning row limits affect reporting, while every selected file is processed.
