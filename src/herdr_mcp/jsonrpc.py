"""Minimal JSON-RPC 2.0 helpers for MCP. Standard library only."""

from __future__ import annotations

from typing import Any, Optional

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
# Reserved by the MCP specification for protocol-version negotiation.
UNSUPPORTED_PROTOCOL_VERSION = -32022


class RPCError(Exception):
    """A JSON-RPC level error with a code and optional data payload."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data

    def to_response(self, request_id: Optional[Any]) -> dict:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            error["data"] = self.data
        return {"jsonrpc": "2.0", "id": request_id, "error": error}


def success(request_id: Optional[Any], result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def error(request_id: Optional[Any], code: int, message: str, data: Any = None) -> dict:
    return RPCError(code, message, data).to_response(request_id)