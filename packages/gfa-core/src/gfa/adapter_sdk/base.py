"""Base adapter implementation and stdio runner."""

from __future__ import annotations

import json
import sys
from typing import Any

from gfa.adapter_sdk.manifest import AdapterManifest
from gfa.adapter_sdk.protocol import (
    INTERNAL_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, RPCRequest, RPCResponse, make_error,
)


class Adapter:
    """Base class for game adapters."""

    def __init__(self, manifest: AdapterManifest):
        self.manifest = manifest
        self._initialized = False

    def initialize(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        self._initialized = True
        return {"ok": True, "capabilities": list(self.manifest.capabilities)}

    def health(self) -> dict[str, Any]:
        return {"ok": True, "initialized": self._initialized}

    def observe(self) -> dict[str, Any]:
        return {"observations": []}

    def execute(self, command: dict[str, Any]) -> dict[str, Any]:
        return {"status": "failed", "message": "execute not implemented"}

    def shutdown(self) -> dict[str, Any]:
        self._initialized = False
        return {"ok": True}


class AdapterRunner:
    """Runs an adapter over stdio JSON-RPC."""

    def __init__(self, adapter: Adapter):
        self.adapter = adapter
        self._methods = {
            "initialize": adapter.initialize,
            "health": adapter.health,
            "observe": adapter.observe,
            "execute": adapter.execute,
            "shutdown": adapter.shutdown,
        }

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        rid = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}
        if not isinstance(method, str):
            return RPCResponse(id=rid, error=make_error(INVALID_REQUEST, "invalid method")).to_dict()
        fn = self._methods.get(method)
        if fn is None:
            return RPCResponse(id=rid, error=make_error(METHOD_NOT_FOUND, f"unknown method {method}")).to_dict()
        try:
            result = fn(**params) if params else fn()
            # normalize: if fn expects positional? We'll call with params dict expansion; adapters implement **kwargs-friendly? 
        except TypeError:
            try:
                result = fn(params)
            except Exception as exc:  # noqa: BLE001
                return RPCResponse(id=rid, error=make_error(INTERNAL_ERROR, str(exc))).to_dict()
        except Exception as exc:  # noqa: BLE001
            return RPCResponse(id=rid, error=make_error(INTERNAL_ERROR, str(exc))).to_dict()
        return RPCResponse(id=rid, result=result).to_dict()

    def run_stdio(self) -> None:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                resp = RPCResponse(id=None, error=make_error(-32700, "parse error"))
                sys.stdout.write(resp.to_line())
                sys.stdout.flush()
                continue
            resp = self.handle(req)
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()