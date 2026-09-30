"""Entry point and argument handling for herdr-mcp."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

from . import transports


def _default_bind() -> str:
    return os.environ.get("HERDR_MCP_BIND", "127.0.0.1:8765")


_LOOPBACK = ("127.0.0.1", "localhost", "::1")
_MIN_TOKEN_LENGTH = 32


def _parse_bind(value: str) -> tuple[str, int]:
    if ":" not in value:
        raise SystemExit(f"invalid bind address {value!r}; expected host:port")
    host, _, port = value.rpartition(":")
    host = host.strip("[]")
    try:
        return host or "127.0.0.1", int(port)
    except ValueError:
        raise SystemExit(f"invalid port in bind address {value!r}") from None


def _transport(args: argparse.Namespace) -> str:
    if args.stdio:
        return "stdio"
    if args.http:
        return "streamable-http"
    env = os.environ.get("HERDR_MCP_TRANSPORT", "")
    if env in ("http", "streamable-http"):
        return "streamable-http"
    return "stdio"


def _token() -> Optional[str]:
    """Bearer token from HERDR_MCP_TOKEN_FILE, HERDR_MCP_TOKEN or MCP_AUTH_TOKEN."""
    path = os.environ.get("HERDR_MCP_TOKEN_FILE")
    if path:
        try:
            with open(path, encoding="utf-8") as handle:
                return handle.read().strip() or None
        except OSError as exc:
            raise SystemExit(f"herdr-mcp: cannot read HERDR_MCP_TOKEN_FILE: {exc}") from None
    return os.environ.get("HERDR_MCP_TOKEN") or os.environ.get("MCP_AUTH_TOKEN") or None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="herdr-mcp",
        description="Model Context Protocol server for Herdr.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--stdio", action="store_true", help="serve over stdio (default)")
    mode.add_argument("--http", action="store_true", help="serve Streamable HTTP")
    parser.add_argument("--bind", default=None, help="host:port for --http")
    parser.add_argument("--host", default=None, help="bind host for --http")
    parser.add_argument("--port", type=int, default=None, help="bind port for --http")
    parser.add_argument(
        "--insecure-no-auth",
        action="store_true",
        help="allow --http without a bearer token (loopback only; any local user can then control Herdr)",
    )
    parser.add_argument("--version", action="store_true", help="print version and exit")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        from . import __version__

        print(f"herdr-mcp {__version__}")
        return 0

    if _transport(args) == "stdio":
        transports.serve_stdio()
        return 0

    if args.bind:
        host, port = _parse_bind(args.bind)
    else:
        host, port = _parse_bind(_default_bind())
    if args.host:
        host = args.host
    if args.port:
        port = args.port

    token = _token()
    if not token:
        if not args.insecure_no_auth:
            sys.stderr.write(
                "herdr-mcp: refusing to serve HTTP without a token. Set HERDR_MCP_TOKEN "
                "(or HERDR_MCP_TOKEN_FILE), e.g. `export HERDR_MCP_TOKEN=$(openssl rand -hex 32)`.\n"
            )
            return 2
        if host not in _LOOPBACK:
            sys.stderr.write("herdr-mcp: --insecure-no-auth is only allowed on a loopback bind\n")
            return 2
        sys.stderr.write(
            "herdr-mcp: WARNING serving without auth; every local user and process can control Herdr\n"
        )
    elif len(token) < _MIN_TOKEN_LENGTH:
        sys.stderr.write(
            f"herdr-mcp: WARNING token is shorter than {_MIN_TOKEN_LENGTH} characters; use a random secret\n"
        )
    transports.serve_http(host, port, token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())