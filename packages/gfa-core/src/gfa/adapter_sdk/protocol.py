"""JSON-RPC 2.0 protocol helpers for adapters."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RPCRequest:
    method: str
    params: dict[str, Any] = field(default_factory=dict)
    id: int | str | None = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> dict[str, Any]:
        d = {"jsonrpc": self.jsonrpc, "method": self.method, "params": self.params}
        if self.id is not None:
            d["id"] = self.id
        return d

    def to_line(self) -> str:
        return json.dumps(self.to_dict()) + "\n"


@dataclass
class RPCResponse:
    id: int | str | None
    result: Any = None
    error: dict[str, Any] | None = None
    jsonrpc: str = "2.0"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RPCResponse":
        return cls(id=data.get("id"), result=data.get("result"), error=data.get("error"),
                   jsonrpc=data.get("jsonrpc", "2.0"))

    def to_dict(self) -> dict[str, Any]:
        d = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error is not None:
            d["error"] = self.error
        else:
            d["result"] = self.result
        return d

    def to_line(self) -> str:
        return json.dumps(self.to_dict()) + "\n"


def make_error(code: int, message: str, data: Any = None) -> dict[str, Any]:
    e = {"code": code, "message": message}
    if data is not None:
        e["data"] = data
    return e

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603