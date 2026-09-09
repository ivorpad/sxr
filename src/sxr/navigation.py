"""Shell-safe follow-up commands retaining the discovered session scope."""

import shlex

from sxr.model import SessionRef


def scope_command(ref: SessionRef, verb: str, *args: str) -> str:
    """A command over the original provider, project, profiles and date window."""
    environment = ref.extra.get("navigation_env", {})
    prefix = (
        ["env", *(f"{key}={value}" for key, value in environment.items())] if environment else []
    )
    return shlex.join([*prefix, "sxr", *ref.extra.get("navigation", []), verb, *args])


def command(ref: SessionRef, verb: str, *args: str) -> str:
    """A pasteable command; discovered refs carry absolute discovery options."""
    if ref.extra.get("navigation"):
        return shlex.join(["sxr", "--file", str(ref.path), verb, ref.id, *args])
    scope = ref.extra.get("navigation", [])
    session = ref.extra.get("navigation_arg", ref.id if scope else ref.short_id)
    environment = ref.extra.get("navigation_env", {})
    prefix = (
        ["env", *(f"{key}={value}" for key, value in environment.items())] if environment else []
    )
    return shlex.join([*prefix, "sxr", *scope, verb, session, *args])
