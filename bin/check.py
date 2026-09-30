#!/usr/bin/env python3
"""Herdr plugin check action: prove the bridge can see the live session.

Runs the server's own code (not a similar-looking shell command) so a green
result cannot come from a code path herdr-mcp does not use.
"""

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "src"))

from herdr_mcp import __version__, herdr, tools  # noqa: E402


def main() -> int:
    report = {
        "plugin": "herdr.mcp",
        "version": __version__,
        "herdr_binary": herdr.binary(),
        "socket": os.environ.get("HERDR_SOCKET_PATH", "(derived from config)"),
        "tools": len(tools.catalog()),
        "ok": False,
    }
    try:
        payload, is_error = tools.invoke("herdr_status", {})
        report["ok"] = not is_error
        if not is_error:
            report["counts"] = payload.get("counts")
    except Exception as exc:  # noqa: BLE001
        report["error"] = str(exc)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())