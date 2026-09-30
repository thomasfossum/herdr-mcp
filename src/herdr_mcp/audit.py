"""Append-only audit log.

One JSON object per tool call under ``HERDR_MCP_STATE_DIR`` (default
``~/.local/state/herdr-mcp``). Free-form text arguments are hashed rather than
stored so prompts and commands are not duplicated into the log verbatim.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from typing import Any

_TEXT_KEYS = (
    "text", "prompt", "body", "command", "args", "agent_args",
    "title", "label", "match", "regex",
)


def state_dir() -> str:
    override = os.environ.get("HERDR_MCP_STATE_DIR")
    if override:
        return override
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        return os.path.join(xdg, "herdr-mcp")
    home = os.path.expanduser("~")
    if sys.platform == "darwin":
        return os.path.join(home, "Library", "Application Support", "herdr-mcp")
    return os.path.join(home, ".local", "state", "herdr-mcp")


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _redact_text(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def _digest(value: str) -> dict:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return {"sha256": digest, "length": len(value)}


def _redact_text(key: str, value: Any) -> Any:
    if key in _TEXT_KEYS:
        if isinstance(value, str):
            return _digest(value)
        if isinstance(value, list):
            return [_digest(v) if isinstance(v, str) else _redact(v) for v in value]
    return _redact(value)


def record(tool: str, arguments: dict, *, ok: bool, detail: str = "") -> None:
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tool": tool,
        "ok": ok,
        "arguments": _redact(arguments),
    }
    if detail:
        entry["detail"] = detail[:500]
    try:
        directory = state_dir()
        os.makedirs(directory, mode=0o700, exist_ok=True)
        path = os.path.join(directory, "audit.jsonl")
        # O_NOFOLLOW: a symlink planted at the log path is refused, not followed.
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass