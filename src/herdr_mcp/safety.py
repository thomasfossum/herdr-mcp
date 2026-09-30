"""Structural validation and policy gates.

Even with full control enabled, every value that reaches ``herdr`` argv is
validated first. The structural gates are not configurable because they are what
stop a value shaped like a flag (``-h``), a path (``../etc``) or shell syntax
from ever entering the argv vector, regardless of how loose an allowlist is.

Policy (allowlists, disabled tools, read-only mode) is read from the environment
on every call so tests and long-running servers see the current value.
"""

from __future__ import annotations

import fnmatch
import math
import os
import re
from typing import Any, Iterable, Optional

# Agent names: herdr requires [a-z][a-z0-9_-]{0,31}
AGENT_NAME_RE = r"^[a-z][a-z0-9_-]{0,31}$"

# Agent kinds share the shape of names; herdr validates the actual kind list.
KIND_RE = r"^[a-z][a-z0-9_-]{0,31}$"

# Opaque IDs: workspace w1, tab w1:t1, pane w1:p1 (plus defensive extras).
ID_RE = r"^[A-Za-z0-9][A-Za-z0-9_:.-]{0,127}$"

# Logical terminal keys accepted by agent/pane send-keys.
_KEY_RE = r"^[A-Za-z0-9+^_-]{1,32}$"

# Conservative subset of git-check-ref-format: no leading dash, no "..",
# no whitespace, control characters or the characters git forbids.
_GIT_REF_RE = (
    r"^(?![-/.])(?!@$)(?!.*\.\.)(?!.*//)(?!.*/\.)(?!.*@\{)(?!.*\.lock(?:/|$))(?!.*/$)(?!.*\.$)"
    r"[A-Za-z0-9._/@+-]{1,200}$"
)

# Labels and titles: printable, single line, bounded.
_LABEL_MAX = 128
_TEXT_MAX = 64 * 1024

_AGENT_NAME = re.compile(AGENT_NAME_RE)
_KIND = re.compile(KIND_RE)
_ID = re.compile(ID_RE)
_KEY = re.compile(_KEY_RE)
_GIT_REF = re.compile(_GIT_REF_RE)
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class SafetyError(ValueError):
    """A request was refused before any command was executed."""


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _globs(name: str, default: str = "") -> list[str]:
    raw = os.environ.get(name, default).strip()
    if raw in ("", "*"):
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def allowlist() -> list[str]:
    """Glob allowlist for agent names (``HERDR_MCP_ALLOW``). Empty = all."""
    return _globs("HERDR_MCP_ALLOW")


def cwd_allowlist() -> list[str]:
    return _globs("HERDR_MCP_CWD_ALLOW")


def kind_allowlist() -> list[str]:
    return _globs("HERDR_MCP_AGENT_KINDS")


def agent_args_allowed() -> bool:
    return _truthy("HERDR_MCP_ALLOW_AGENT_ARGS")


def read_only() -> bool:
    return _truthy("HERDR_MCP_READ_ONLY")


def disabled_tools() -> list[str]:
    return _globs("HERDR_MCP_DISABLE_TOOLS")


def tool_enabled(name: str, *, read_only_tool: bool) -> bool:
    if read_only() and not read_only_tool:
        return False
    return not any(fnmatch.fnmatchcase(name, p) for p in disabled_tools())


def name_permitted(value: str) -> bool:
    patterns = allowlist()
    return not patterns or any(fnmatch.fnmatchcase(value, p) for p in patterns)


def validate_agent_name(value: Any) -> str:
    if not isinstance(value, str) or not _AGENT_NAME.match(value):
        raise SafetyError(f"invalid agent name {value!r}: expected {AGENT_NAME_RE}")
    if not name_permitted(value):
        raise SafetyError(f"agent name {value!r} is not permitted by HERDR_MCP_ALLOW")
    return value


def validate_kind(value: Any) -> str:
    if not isinstance(value, str) or not _KIND.match(value):
        raise SafetyError(f"invalid agent kind {value!r}: expected {KIND_RE}")
    patterns = kind_allowlist()
    if patterns and not any(fnmatch.fnmatchcase(value, p) for p in patterns):
        raise SafetyError(f"agent kind {value!r} is not permitted by HERDR_MCP_AGENT_KINDS")
    return value


def validate_id(value: Any, kind: str = "id") -> str:
    if not isinstance(value, str) or not _ID.match(value):
        raise SafetyError(f"invalid {kind} {value!r}")
    return value


def looks_like_agent_name(value: str) -> bool:
    return bool(_AGENT_NAME.match(value)) and ":" not in value


def validate_target(value: Any) -> str:
    """An agent target accepts either a unique live agent name or a pane id.

    Structural check only. Name allowlisting for pane-id targets needs a lookup
    and is done by the tool layer.
    """
    if isinstance(value, str) and looks_like_agent_name(value):
        return validate_agent_name(value)
    return validate_id(value, "target")


def validate_key(value: Any) -> str:
    if not isinstance(value, str) or not _KEY.match(value):
        raise SafetyError(f"invalid key {value!r}")
    return value


def validate_git_ref(value: Any, kind: str = "ref") -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str) or not _GIT_REF.match(value):
        raise SafetyError(f"invalid git {kind} {value!r}")
    return value


def validate_label(value: Any, kind: str = "label") -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str) or not value or len(value) > _LABEL_MAX:
        raise SafetyError(f"{kind} must be a non-empty string of at most {_LABEL_MAX} characters")
    if _CONTROL.search(value):
        raise SafetyError(f"{kind} must not contain control characters")
    return value


def validate_text(value: Any, kind: str = "text", *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not value and not allow_empty):
        raise SafetyError(f"{kind} must be a non-empty string")
    if len(value) > _TEXT_MAX:
        raise SafetyError(f"{kind} is longer than {_TEXT_MAX} characters")
    if "\x00" in value:
        raise SafetyError(f"{kind} must not contain NUL")
    return value


def bounded_int(value: Any, kind: str, *, default: int, low: int, high: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SafetyError(f"{kind} must be an integer")
    if isinstance(value, float) and not (math.isfinite(value) and value.is_integer()):
        raise SafetyError(f"{kind} must be an integer")
    number = int(value)
    if number < low or number > high:
        raise SafetyError(f"{kind} must be between {low} and {high}")
    return number


def bounded_float(value: Any, kind: str, *, low: float, high: float) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SafetyError(f"{kind} must be a number")
    number = float(value)
    if not math.isfinite(number) or not (low <= number <= high):
        raise SafetyError(f"{kind} must be between {low} and {high}")
    return number


def validate_cwd(path: Any, kind: str = "cwd") -> Optional[str]:
    if path is None:
        return None
    if not isinstance(path, str) or not path:
        raise SafetyError(f"{kind} must be a non-empty string")
    if _CONTROL.search(path):
        raise SafetyError(f"{kind} must not contain control characters")
    resolved = os.path.realpath(os.path.expanduser(path))
    roots = cwd_allowlist()
    if roots and not any(_under(resolved, os.path.realpath(os.path.expanduser(r))) for r in roots):
        raise SafetyError(f"{kind} {resolved!r} is outside HERDR_MCP_CWD_ALLOW")
    return resolved


def _under(path: str, root: str) -> bool:
    path = os.path.normpath(path)
    root = os.path.normpath(root)
    return path == root or path.startswith(root.rstrip("/") + "/")


def validate_enum(value: Any, allowed: Iterable[str], kind: str) -> str:
    allowed = tuple(allowed)
    if value not in allowed:
        raise SafetyError(f"invalid {kind} {value!r}: expected one of {sorted(allowed)}")
    return value


def require_confirm(confirm: Any, what: str) -> None:
    if confirm is not True:
        raise SafetyError(f"{what} is destructive: call again with confirm=true to proceed")
