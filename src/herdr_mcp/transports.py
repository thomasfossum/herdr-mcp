"""Transport layers: newline-delimited stdio and stateless Streamable HTTP."""

from __future__ import annotations

import hmac
import json
import os
import socketserver
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import urlparse

from . import mcp

MCP_PATH = "/mcp"
MAX_BODY_BYTES = 1024 * 1024
REQUEST_TIMEOUT_S = 60
MAX_CONNECTIONS = 32


def allowed_origins() -> list[str]:
    raw = os.environ.get("HERDR_MCP_ALLOWED_ORIGINS", "")
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


def serve_stdio() -> None:
    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer
    while True:
        raw = stdin.readline()
        if not raw:
            break
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="replace")
        text = text.strip()
        if not text:
            continue
        response = mcp.handle_raw(text)
        if response is not None:
            stdout.write(response.encode("utf-8") + b"\n")
            stdout.flush()


class _Handler(BaseHTTPRequestHandler):
    server_version = "herdr-mcp"
    sys_version = ""
    protocol_version = "HTTP/1.1"
    timeout = REQUEST_TIMEOUT_S
    token: Optional[str] = None

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        sys.stderr.write("herdr-mcp: " + (fmt % args) + "\n")

    def _authorised(self) -> bool:
        if not self.token:
            return True
        header = self.headers.get("Authorization", "")
        return hmac.compare_digest(header.encode("utf-8"), f"Bearer {self.token}".encode("utf-8"))

    def _origin_ok(self) -> bool:
        """Reject browser-originated requests unless the origin is allowlisted.

        Browsers attach Origin to cross-site POSTs, so this blocks a web page
        (or a DNS-rebound hostname) from driving a loopback server. Non-browser
        MCP clients do not send Origin and are unaffected.
        """
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        return origin.rstrip("/") in allowed_origins()

    def _send(self, code: int, body: bytes = b"", content_type: str = "application/json") -> None:
        self.send_response(code)
        if body:
            self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if code >= 400:
            # An unread request body must not be parsed as the next request.
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _gate(self) -> bool:
        """Common checks. Returns True when the request may proceed."""
        if urlparse(self.path).path != MCP_PATH:
            self._send(404, b'{"error":"not found"}')
            return False
        if not self._origin_ok():
            self._send(403, b'{"error":"origin not allowed"}')
            return False
        if not self._authorised():
            self._send(401, b'{"error":"unauthorized"}')
            return False
        return True

    def do_POST(self) -> None:  # noqa: N802
        if not self._gate():
            return
        # Modern clients send the protocol version in a header. Reject an
        # unsupported one with the modern error body so the client can retry.
        version = self.headers.get("MCP-Protocol-Version")
        if version and version not in mcp.SUPPORTED_PROTOCOL_VERSIONS:
            self._send(400, json.dumps(mcp.version_error(version)).encode("utf-8"))
            return
        content_type = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if content_type != "application/json":
            self._send(415, b'{"error":"Content-Type must be application/json"}')
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY_BYTES:
            self._send(413, b'{"error":"invalid or oversized body"}')
            return
        body = self.rfile.read(length) if length else b""
        text = body.decode("utf-8", errors="replace").strip()
        if not text:
            self._send(400, b'{"error":"empty body"}')
            return
        response = mcp.handle_raw(text)
        if response is None:
            self._send(202)
            return
        self._send(200, response.encode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        if not self._gate():
            return
        self._send(405, b'{"error":"method not allowed"}')

    def do_DELETE(self) -> None:  # noqa: N802
        if not self._gate():
            return
        self._send(200, b"{}")


class Server(ThreadingHTTPServer):
    """Threaded server with a cap on concurrent connections.

    The per-socket timeout bounds each read, not a whole request, so a client
    trickling bytes can hold a thread; the cap keeps that from growing without
    bound. Connections over the cap are closed immediately.
    """

    daemon_threads = True

    def __init__(self, *args, max_connections: int = MAX_CONNECTIONS, **kwargs) -> None:
        self._slots = threading.BoundedSemaphore(max_connections)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address) -> None:
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

    def server_bind(self) -> None:
        # HTTPServer.server_bind does a reverse-DNS getfqdn() that can stall
        # startup for many seconds; the name is only cosmetic.
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = str(host)
        self.server_port = port


def serve_http(host: str, port: int, token: Optional[str]) -> None:
    handler = type("_BoundHandler", (_Handler,), {"token": token})
    httpd = Server((host, port), handler)
    sys.stderr.write(f"herdr-mcp: streamable HTTP listening on http://{host}:{port}{MCP_PATH}\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
