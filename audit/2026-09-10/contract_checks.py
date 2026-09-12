"""Behavioral expectations from README, help text, and ordinary CLI contracts."""

import json
import shlex

from audit_support import (
    SYNTHETIC_PASSWORD,
    assistant,
    code,
    event_rows,
    json_lines,
    require,
    tool,
    user,
    write_records,
)

CHECKS = []


def case(identity, expected):
    """Register a reproducible expectation without changing application tests."""

    def register(function):
        CHECKS.append((identity, expected, function))
        return function

    return register


def help_check(corpus, command):
    result = corpus.run(*command, "--help")
    code(result)
    require("usage:" in result.stdout.lower(), "help must contain usage")


for command in (
    [],
    *(
        [name]
        for name in (
            "list",
            "show",
            "prompts",
            "cmds",
            "errors",
            "tools",
            "stats",
            "path",
            "grep",
            "find",
            "index",
            "skills",
            "secrets",
            "init",
            "serve",
        )
    ),
    ["secrets", "clean"],
):
    case("HELP-" + ("-".join(command) or "root"), "Every public command provides help.")(
        lambda corpus, command=command: help_check(corpus, command)
    )


@case("VERSION", "The source entry point reports the package version.")
def version(c):
    from sxr import __version__

    result = c.run("--version")
    code(result)
    require(result.stdout.strip() == f"sxr {__version__}", "version mismatch")


@case(
    "LIST-default", "Bare invocation equals list; Claude is default and sessions are newest first."
)
def list_default(c):
    bare = c.run("--path", "/sxr-audit-project", "--json")
    listed = c.scope("list", "--json")
    code(bare)
    code(listed)
    require(bare.stdout == listed.stdout, "bare and list disagree")
    require(
        [r["id"] for r in json_lines(bare)] == ["aaa-main", "bbb-second"],
        "ordering/provider mismatch",
    )


@case("LIST-provider", "Codex listing and root/command flag positions select the same source.")
def list_provider(c):
    first = c.scope("list", "--codex", "--json")
    second = c.run("--codex", "--json", "--path", "/sxr-audit-project", "list")
    code(first)
    require(first.stdout == second.stdout, "flag positions disagree")
    require([r["id"] for r in json_lines(first)] == ["codex-audit"], "wrong Codex identity")


@case("SELECT-range", "A session range includes both endpoints and accepts reversed bounds.")
def select_range(c):
    a = c.scope("grep", "needle", "@1:@2", "-c", "--json")
    b = c.scope("grep", "needle", "@2:@1", "-c", "--json")
    code(a)
    require(a.stdout == b.stdout and len(json_lines(a)) == 2, "range did not include both sessions")


@case(
    "SELECT-identities", "Handle, unique prefix, name, and omitted ID select the expected source."
)
def select_identities(c):
    results = [c.scope("path", *args) for args in ([], ["@1"], ["aaa"], ["audit-main"])]
    for result in results:
        code(result)
        require(result.stdout.strip() == str(c.main), "selector chose another session")


@case(
    "FIND-roundtrip",
    "Find combines providers, returns real evidence, and prints a working exact-file follow-up.",
)
def find_roundtrip(c):
    result = c.scope("find", "needle", "--json")
    code(result)
    data = json.loads(result.stdout)
    require(data["total"] == 3 and data["complete"], "expected all three synthetic sessions")
    for hit in data["results"]:
        require(any("needle" in e["text"].lower() for e in hit["evidence"]), "excerpt omitted clue")
        follow = shlex.split(hit["follow_up"])
        zoom = c.run(*follow[1:])
        code(zoom)
        require(hit["path"] in zoom.stdout, "follow-up lost exact source")


@case("FIND-paths", "Path mode returns every matching physical source in sorted order.")
def find_paths(c):
    result = c.scope("find", "needle", "--paths", "--json")
    code(result)
    data = json.loads(result.stdout)
    require(data["paths"] == sorted(map(str, [c.main, c.second, c.codex])), "wrong path set")


@case("FIND-freshness", "A warm search sees source edits and removes stale matches.")
def find_freshness(c):
    code(c.file("find", "alpha", "--json"))
    c.main.write_text(c.main.read_text().replace("alpha", "replacement"))
    code(c.file("find", "alpha", "--json"), 1)
    code(c.file("find", "replacement", "--json"))


@case("FIND-exclusion", "Find excludes the current Codex thread unless explicitly included.")
def find_exclusion(c):
    result = c.run(
        "find",
        "needle",
        "--path",
        "/sxr-audit-project",
        "--json",
        env={"CODEX_THREAD_ID": "codex-audit"},
    )
    code(result)
    require(json.loads(result.stdout)["total"] == 2, "current session included")
    result = c.run(
        "find",
        "needle",
        "--path",
        "/sxr-audit-project",
        "--json",
        "--include-current",
        env={"CODEX_THREAD_ID": "codex-audit"},
    )
    require(json.loads(result.stdout)["total"] == 3, "override did not restore current session")


@case(
    "FIND-unicode-evidence",
    "A normalized word match includes the matching source text in its excerpt.",
)
def find_unicode(c):
    path = c.extra("accent", [user("padding " * 150 + "café unique ending")])
    result = c.file("find", "cafe", "--json", path=path)
    code(result)
    data = json.loads(result.stdout)
    require(data["total"] == 1, "accent-normalized match missing")
    require(
        any("café" in e["text"] for e in data["results"][0]["evidence"]),
        "returned excerpt contains no occurrence of the matched café",
    )


@case(
    "GREP-modes",
    "Regex, fixed strings, smart case, -i, and leading-dash patterns have distinct semantics.",
)
def grep_modes(c):
    for pattern, options, expected in (
        ("needle", [], 3),
        ("NEEDLE", [], 1),
        ("NEEDLE", ["-i"], 3),
        ("a.b", ["-F"], 1),
        ("--dash", ["-e"], 1),
    ):
        args = ["-e", pattern] if "-e" in options else [pattern, *options]
        result = c.file("grep", *args, "--json")
        code(result)
        require(len(json_lines(result)) == expected, f"wrong matches for {pattern}")


@case("GREP-cache-parity", "Indexed and direct grep return identical decoded records.")
def grep_parity(c):
    cached = c.file("grep", "needle", "--json")
    direct = c.file("grep", "needle", "--json", env={"SXR_NO_CACHE": "1"})
    code(cached)
    require(cached.stdout == direct.stdout, "cache changed grep results")


@case(
    "READ-provider-outcomes",
    "Both providers display command failures and preserve original error records.",
)
def provider_outcomes(c):
    for path, count in ((c.main, 2), (c.codex, 1)):
        result = c.file("cmds", path=path)
        code(result)
        require("-> err" in result.stdout, "command outcome missing")
        result = c.file("errors", "--json", path=path)
        code(result)
        require(len(json_lines(result)) == count, "wrong original error-record count")


@case("PROMPTS-filter", "Prompts omit metadata and tool results; --all restores user-role records.")
def prompts_filter(c):
    result = c.file("prompts", "--json")
    code(result)
    require(
        len(json_lines(result)) == 3 and "injected fixture" not in result.stdout,
        "prompt selection wrong",
    )
    require(
        len(json_lines(c.file("prompts", "--all", "--json"))) == 6, "--all omitted user records"
    )


def limit_check(c, command):
    result = c.file(command, "--json", "-n", "1")
    code(result)
    require(len(json_lines(result)) == 1, f"-n 1 printed {len(json_lines(result))} records")


for name in ("show", "prompts", "errors", "cmds", "grep"):
    if name == "grep":
        continue
    case(
        f"LIMIT-json-{name}",
        "-n 1 caps the number of JSONL records without truncating record contents.",
    )(lambda c, name=name: limit_check(c, name))


@case("LIMIT-errors-scope", "An errors row limit applies across the entire selected range.")
def errors_scope_limit(c):
    result = c.scope("errors", "@1:@2", "-n", "1")
    code(result)
    require(len(event_rows(result)) == 1, f"-n 1 printed {len(event_rows(result))} error rows")


@case("LIMIT-errors-notice", "A shortened errors view reports how many records were omitted.")
def errors_limit_notice(c):
    result = c.file("errors", "-n", "1")
    code(result)
    require(
        "more" in result.stdout or "showing" in result.stdout,
        "omitted error row has no truncation notice",
    )


@case("LIMIT-tools", "The advertised tools -n option caps printed tool rows.")
def tools_limit(c):
    result = c.file("tools", "-n", "1")
    code(result)
    rows = [r for r in result.stdout.splitlines() if r and not r.startswith("#")]
    require(len(rows) == 1, f"-n 1 printed {len(rows)} tool rows")


@case("LIMIT-stats", "The advertised stats -n option caps printed field rows.")
def stats_limit(c):
    result = c.file("stats", "-n", "1")
    code(result)
    rows = [r for r in result.stdout.splitlines() if r and not r.startswith("#")]
    require(len(rows) == 1, f"-n 1 printed {len(rows)} stat rows")


@case(
    "LIMIT-path", "The advertised path -n option caps printed paths, including child transcripts."
)
def path_limit(c):
    write_records(c.claude / "aaa-main/subagents/agent-child.jsonl", [user("child")])
    result = c.scope("path", "aaa-main", "-n", "1")
    code(result)
    require(len(result.stdout.splitlines()) == 1, "-n 1 printed both parent and child paths")


@case(
    "LIMIT-secrets-notice",
    "A shortened secret worklist reports omitted findings and the full distinct count.",
)
def secret_limit_notice(c):
    path = c.extra(
        "two-secrets",
        [
            user(f'password = "{SYNTHETIC_PASSWORD}"'),
            user('password = "DifferentSyntheticAuditValue_2026!"'),
        ],
    )
    result = c.file("secrets", "-n", "1", path=path)
    code(result)
    require(
        "more" in result.stdout or "of 2" in result.stdout,
        "two detected values are reported as '1 distinct secrets' with no omitted-count notice",
    )


@case("SHOW-full", "--full prints whole text as promised by the top-level help and primer.")
def show_full(c):
    text = "audit long text " * 4000 + "unique end marker"
    path = c.extra("long", [user(text)])
    result = c.file("show", "--full", path=path)
    code(result)
    require(text in result.stdout, f"--full trimmed the {len(text)}-character text")


@case("SHOW-zoom", "A zoom prints full text despite a small scan budget.")
def show_zoom(c):
    text = "audit text " * 200 + "end marker"
    path = c.extra("zoom", [user(text)])
    result = c.file("show", "--around", "1", "--context", "0", "--budget", "1", path=path)
    code(result)
    require(text in result.stdout, "zoom trimmed text")


@case(
    "SHOW-empty", "A show selection with no matching records exits 1 in both text and JSON modes."
)
def show_empty(c):
    text = c.file("show", "--type", "does-not-exist")
    structured = c.file("show", "--type", "does-not-exist", "--json")
    require(
        text.returncode == structured.returncode == 1,
        f"empty selection exits text={text.returncode}, JSON={structured.returncode}",
    )


@case("SHOW-tail-zero", "Last zero selected events returns an empty result.")
def tail_zero(c):
    result = c.file("show", "--tail", "0", "--json")
    require(
        not json_lines(result) and result.returncode == 1, "--tail 0 returned the entire skeleton"
    )


def negative_limit(c, command):
    result = c.file(command, "-n", "-1")
    code(result, 2)


for name in ("list", "show", "prompts", "errors", "tools", "stats", "cmds"):
    case(
        f"USAGE-negative-limit-{name}",
        "Negative row counts are usage errors, consistent with find and skills.",
    )(lambda c, name=name: negative_limit(c, name))


@case(
    "TIME-fraction", "UTC date filtering compares instants, including fractional-second boundaries."
)
def time_fraction(c):
    path = c.extra("fraction", [user("needle", "2026-08-01T12:00:00.123Z")])
    result = c.file("list", "--before", "2026-08-01T12:00:00.123001Z", "--json", path=path)
    code(result)
    require(len(json_lines(result)) == 1, "a session one microsecond before the bound was excluded")


@case("TIME-offset", "Recorded timestamp offsets are normalized to UTC before filtering.")
def time_offset(c):
    path = c.extra("offset", [user("needle", "2026-08-01T13:00:00+02:00")])
    result = c.file("list", "--before", "2026-08-01T12:00:00Z", "--json", path=path)
    code(result)
    require(len(json_lines(result)) == 1, "11:00 UTC was excluded by --before 12:00 UTC")


@case("TOOLS-skill-count", "Each Skill call increments only its own input's count once.")
def skill_count(c):
    path = c.extra(
        "skill-calls",
        [
            user("two skills"),
            assistant(
                [
                    tool("a", "Skill", skill="notify"),
                    tool("b", "Skill", skill="review"),
                ]
            ),
        ],
    )
    result = c.file("tools", "--json", path=path)
    code(result)
    data = json.loads(result.stdout)
    require(data["calls"] == {"Skill": 2}, "wrong tool call count")
    require(
        data["skill_inputs"] == {"notify": 1, "review": 1},
        f"each Skill input counted more than once: {data['skill_inputs']}",
    )


@case(
    "ERRORS-api-error", "A Claude record counted as an API error is available in the errors view."
)
def api_error(c):
    path = c.extra(
        "api-error",
        [
            user("request"),
            assistant([dict(type="text", text="API Error: synthetic")], isApiErrorMessage=True),
        ],
    )
    summary = json_lines(c.file("list", "--json", path=path))[0]
    require(summary["errors"] == 1, "fixture must count as an API error")
    result = c.file("errors", "--json", path=path)
    code(result)
    require(len(json_lines(result)) == 1, "counted API error missing from errors")


@case(
    "SECRETS-dry-apply",
    "Secret cleaning previews changes, applies them only on request, and is idempotent.",
)
def secrets_apply(c):
    path = c.extra("secret", [user(f'password = "{SYNTHETIC_PASSWORD}"')])
    original = path.read_bytes()
    preview = c.file("secrets", "clean", path=path)
    code(preview)
    require(path.read_bytes() == original, "preview modified file")
    require(
        SYNTHETIC_PASSWORD not in preview.stdout + preview.stderr,
        "preview disclosed fixture password",
    )
    applied = c.file("secrets", "clean", "--apply", path=path)
    code(applied)
    require(SYNTHETIC_PASSWORD.encode() not in path.read_bytes(), "apply retained credential")
    require(b"[sxr:redacted:" in path.read_bytes(), "redaction marker absent")
    code(c.file("secrets", "clean", "--apply", path=path), 1)


@case(
    "SECRETS-write-input",
    "Secret audit detects a password inside the contents of a recorded Write tool call.",
)
def secret_write_input(c):
    path = c.extra(
        "write-content",
        [
            user("write config"),
            assistant(
                [
                    tool(
                        "w",
                        "Write",
                        file_path="/tmp/config.txt",
                        content=f'password = "{SYNTHETIC_PASSWORD}"',
                    )
                ]
            ),
        ],
    )
    result = c.file("secrets", "--json", path=path)
    preview = c.file("secrets", "clean", path=path)
    code(preview)
    require(
        SYNTHETIC_PASSWORD not in result.stdout + result.stderr, "audit disclosed fixture password"
    )
    require(
        result.returncode == 0 and len(json_lines(result)) >= 1,
        f"audit exits {result.returncode} with no finding; clean detects the password",
    )


@case(
    "FORMAT-clean-json",
    "An advertised --json option emits machine-readable JSON, or rejects the unsupported mode.",
)
def clean_json(c):
    path = c.extra("clean-json", [user(f'password = "{SYNTHETIC_PASSWORD}"')])
    result = c.file("secrets", "clean", "--json", path=path)
    if result.returncode == 2 and "--json" in result.stderr:
        return
    code(result)
    try:
        json_lines(result)
    except ValueError:
        raise AssertionError(
            "secrets clean --json accepts the flag but emits TSV and prose"
        ) from None


@case(
    "SKILLS-workflow",
    "Skills group identical contents, expand copies, refresh edits, and clear the map.",
)
def skills_workflow(c):
    root = c.skill.parents[1]
    copy = root / "backup/notify/SKILL.md"
    copy.parent.mkdir(parents=True)
    copy.write_bytes(c.skill.read_bytes())
    result = c.run("skills", "--index", "--root", root, "--json")
    code(result)
    data = json.loads(c.run("skills", "notify", "--json").stdout)
    require(data["total"] == 1 and data["files"] == 2, "copies not grouped")
    paths = c.run("skills", "notify", "--paths", "--copies")
    require(set(paths.stdout.splitlines()) == {str(c.skill), str(copy)}, "copy paths missing")
    copy.write_text("Changed fixture instruction.\n")
    changed = c.run("skills", "notify", "--json")
    code(changed, 2)
    require(json.loads(changed.stdout)["total"] == 2, "edited contents not rehashed")
    code(c.run("skills", "--clear"))
    require(not (c.root / "cache/skills.json").exists(), "default map remains after clear")


@case(
    "INIT-workflow",
    "Explicit-file primer installation preserves surrounding prose and is idempotent.",
)
def init_workflow(c):
    path = c.root / "instructions/AGENTS.md"
    path.parent.mkdir()
    path.write_text("Existing instructions.\n")
    code(c.run("init", "--check", path), 1)
    code(c.run("init", "--write", path))
    first = path.read_bytes()
    require(first.startswith(b"Existing instructions.\n"), "existing content changed")
    code(c.run("init", "--write", path))
    require(path.read_bytes() == first, "second install changed bytes")
    code(c.run("init", "--check", path))


@case("INDEX-clear", "Index preparation creates a cache and --clear removes it.")
def index_clear(c):
    code(c.file("index"))
    require((c.root / "cache/search.sqlite3").exists(), "cache was not created")
    code(c.run("index", "--clear"))
    require(not (c.root / "cache/search.sqlite3").exists(), "cache was not cleared")


@case(
    "USAGE-invalid-json-record",
    "A malformed record shape produces a diagnostic instead of a Python traceback.",
)
def invalid_shape(c):
    path = c.extra("invalid-shape", [user("valid beginning"), 42, user("valid ending")])
    result = c.file("show", "--full", path=path)
    require(
        result.returncode in (0, 2) and "Traceback" not in result.stderr,
        f"non-object JSON record crashes with exit {result.returncode}",
    )


@case(
    "INIT-file-error",
    "An unwritable primer destination reports an error with exit 2 and no traceback.",
)
def init_file_error(c):
    parent = c.root / "not-a-directory"
    parent.write_text("existing file")
    result = c.run("init", "--write", parent / "AGENTS.md")
    require(
        result.returncode == 2 and "Traceback" not in result.stderr,
        f"invalid destination produces exit {result.returncode} and a Python traceback",
    )


@case("FIND-unicode-match", "Latin-diacritic normalization finds the correct source session.")
def unicode_match(c):
    path = c.extra("normalized", [user("padding " * 150 + "café ending")])
    result = c.file("find", "cafe", "--json", path=path)
    code(result)
    require(json.loads(result.stdout)["total"] == 1, "cafe did not match café")


@case("FORMAT-path-json", "path honors --json or rejects an unsupported output mode.")
def path_json(c):
    result = c.file("path", "--json")
    if result.returncode == 2 and "--json" in result.stderr:
        return
    code(result)
    try:
        json_lines(result)
    except ValueError:
        raise AssertionError("path --json accepts the flag but emits a plain pathname") from None


@case("LIMIT-clean", "The advertised clean -n option caps the printed file rows.")
def clean_limit(c):
    records = [user(f'password = "{SYNTHETIC_PASSWORD}"')]
    write_records(c.main, records)
    write_records(c.second, records)
    result = c.scope("secrets", "clean", "-n", "1")
    code(result)
    rows = [r for r in result.stdout.splitlines() if r and not r.startswith("#")]
    require(len(rows) == 1, f"clean -n 1 printed {len(rows)} file rows")
