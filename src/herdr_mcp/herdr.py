"""Thin wrapper around the Herdr CLI.

The CLI is the plugin API: every command is available as ``herdr ...``. Return
conventions (see herdr's own docs):

* rc 0  -> JSON on stdout
* rc 1  -> JSON on stderr (herdr error envelope)
* rc 2  -> plain text on stderr (CLI syntax / usage error)

``HERDR_BIN_PATH`` (set by Herdr for managed plugin commands) points at the
running binary. Outside a plugin it falls back to ``HERDR_MCP_HERDR`` and then
to ``herdr`` on ``PATH``.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
from dataclasses import dataclass
from typing import Any, Optional, Sequence


class HerdrError(Exception):
    """Raised when a herdr command exits non-zero or returns an error payload."""

    def __init__(self, message: str, *, rc: int, argv: Sequence[str], data: Any = None) -> None:
        super().__init__(message)
        self.rc = rc
        self.argv = list(argv)
        self.data = data

    def summary(self) -> str:
        """The error without free-form argv, safe for the audit log."""
        return f"{' '.join(self.argv[1:3])}: {str(self).splitlines()[0][:200]}"

    def to_dict(self) -> dict:
        return {
            "error": str(self),
            "rc": self.rc,
            # Subcommand only: the full argv holds the host binary path and
            # the caller's free text.
            "command": " ".join(self.argv[1:3]),
            "data": self.data,
        }


@dataclass
class HerdrResult:
    rc: int
    stdout: str
    stderr: str
    data: Any

    @property
    def ok(self) -> bool:
        return self.rc == 0


# Server-side secrets never reach herdr or anything it spawns.
_SCRUBBED_ENV = ("MCP_AUTH_TOKEN", "HERDR_MCP_TOKEN", "HERDR_MCP_TOKEN_FILE")


def _child_env() -> dict:
    env = os.environ.copy()
    for key in _SCRUBBED_ENV:
        env.pop(key, None)
    return env


_calls = threading.local()


def reset_calls() -> None:
    _calls.count = 0


def calls() -> int:
    """How many herdr commands this thread has started since reset_calls()."""
    return getattr(_calls, "count", 0)


def binary() -> str:
    return (
        os.environ.get("HERDR_BIN_PATH")
        or os.environ.get("HERDR_MCP_HERDR")
        or "herdr"
    )


def run(
    args: Sequence[str],
    *,
    timeout: Optional[float] = None,
    check: bool = True,
) -> HerdrResult:
    """Run ``herdr <args>`` and normalise the three return conventions."""
    argv = [binary(), *[str(a) for a in args]]
    _calls.count = calls() + 1
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_child_env(),
        )
    except FileNotFoundError as exc:
        raise HerdrError(
            f"herdr binary not found: {binary()!r}", rc=127, argv=argv
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise HerdrError(
            f"herdr {' '.join(argv[1:3])} timed out after {timeout}s",
            rc=124,
            argv=argv,
        ) from exc

    data: Any = None
    if proc.stdout.strip():
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            data = None

    if check and proc.returncode != 0:
        message, payload = _error_message(proc.returncode, proc.stdout, proc.stderr, argv)
        raise HerdrError(message, rc=proc.returncode, argv=argv, data=payload)

    return HerdrResult(rc=proc.returncode, stdout=proc.stdout, stderr=proc.stderr, data=data)


def run_json(args: Sequence[str], *, timeout: Optional[float] = None) -> Any:
    """Run a command expected to return JSON and return the parsed payload."""
    result = run(args, timeout=timeout, check=True)
    if result.data is None:
        raise HerdrError(
            f"herdr {' '.join(str(a) for a in args[:2])} returned no JSON",
            rc=result.rc,
            argv=[binary(), *args],
        )
    return result.data


def error_envelope(rc: int) -> dict:
    """The JSON error payload the MCP tool call returns for a failed command."""
    return {"isError": True, "rc": rc}


def _error_message(rc: int, stdout: str, stderr: str, argv: Sequence[str]) -> tuple[str, Any]:
    payload = _first_json(stderr) or _first_json(stdout)
    if rc == 2:
        text = (stderr or stdout).strip().splitlines()
        detail = text[0] if text else "herdr usage error"
        return f"{detail} (rc=2)", {"rc": 2, "raw": (stderr or stdout).strip()}
    if payload is not None:
        message = payload.get("error") if isinstance(payload, dict) else None
        return (str(message) if message else f"herdr failed (rc={rc})"), payload
    text = (stderr or stdout).strip()
    return (text or f"herdr failed (rc={rc})"), None


def _first_json(text: str) -> Optional[Any]:
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None