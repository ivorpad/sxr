"""Translate the Go regexp syntax used by the vendored rules to Python re.

Go inline flags affect the rest of their group, including later alternatives.
Scoped Python groups retain that behavior without changing capture numbers or
making a preceding credential prefix case-insensitive.
"""

import re

FLAGS = re.compile(r"\(\?([ims]+(?:-[ims]+)?|-[ims]+)\)")
CLASSES = {"[:alnum:]": "A-Za-z0-9"}


def _character_class(source, start):
    """Copy one class, expanding the POSIX classes present in the ruleset."""
    parts = ["["]
    index = start + 1
    if source[index : index + 1] == "^":
        parts.append("^")
        index += 1
    if source[index : index + 1] == "]":
        parts.append("]")
        index += 1
    while index < len(source):
        if source.startswith("[:", index):
            end = source.find(":]", index) + 2
            name = source[index:end]
            if name not in CLASSES:
                raise ValueError(f"unsupported POSIX character class: {name}")
            parts.append(CLASSES[name])
            index = end
        elif source[index] == "\\":
            parts.append(source[index : index + 2])
            index += 2
        else:
            char = source[index]
            parts.append(char)
            index += 1
            if char == "]":
                return "".join(parts), index
    raise ValueError("unterminated character class")


def compile_rule(source: str) -> re.Pattern:
    """Compile a bundled expression, rejecting unsupported syntax explicitly."""
    parts, scopes = [], [[]]
    index = 0
    while index < len(source):
        char = source[index]
        toggle = FLAGS.match(source, index)
        if char == "\\":
            escaped = source[index : index + 2]
            parts.append(r"\Z" if escaped == r"\z" else escaped)
            index += 2
        elif char == "[":
            value, index = _character_class(source, index)
            parts.append(value)
        elif toggle:
            flag = toggle[1]
            parts.append(f"(?{flag}:")
            scopes[-1].append(flag)
            index = toggle.end()
        else:
            if char == "(":
                scopes.append([])
            elif char == ")":
                if len(scopes) == 1:
                    raise ValueError("unmatched closing parenthesis")
                parts.append(")" * len(scopes.pop()))
            elif char == "|":
                parts.extend((")" * len(scopes[-1]), "|"))
                parts.extend(f"(?{flag}:" for flag in scopes[-1])
                index += 1
                continue
            parts.append(char)
            index += 1
    if len(scopes) != 1:
        raise ValueError("unterminated group")
    parts.append(")" * len(scopes[0]))
    # Go's Perl classes and word boundaries are ASCII, including next to Unicode text.
    return re.compile("".join(parts), re.ASCII)
