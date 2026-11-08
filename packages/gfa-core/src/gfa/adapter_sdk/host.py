"""Host-side adapter process manager."""

from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path
from typing import Any

from gfa.adapter_sdk.manifest import AdapterManifest
from gfa.adapter_sdk.protocol import RPCRequest


class AdapterHost:
    def __init__(self, manifest: AdapterManifest, cwd: Path | None = None):
        self.manifest = manifest
        self.cwd = cwd
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._req_id = 0

    def start(self, timeout: float = 10.0) -> dict[str, Any]:
        cmd = self.manifest.entrypoint.split()
        self._proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, cwd=str(self.cwd) if self.cwd else None, bufsize=1,
        )
        # initialize
        return self.call("initialize", {}, timeout=timeout)

    def call(self, method: str, params: dict[str, Any] | None = None, timeout: float = 10.0) -> dict[str, Any]:
        if self._proc is None or self._proc.poll() is not None:
            raise RuntimeError("Adapter process not running")
        with self._lock:
            self._req_id += 1
            rid = self._req_id
            req = RPCRequest(method=method, params=params or {}, id=rid)
            assert self._proc.stdin is not None
            self._proc.stdin.write(req.to_line())
            self._proc.stdin.flush()
            # read response
            assert self._proc.stdout is not None
            line = self._proc.stdout.readline()
            if not line:
                raise RuntimeError("No response from adapter")
            resp = json.loads(line)
            if resp.get("error"):
                raise RuntimeError(str(resp["error"]))
            return resp.get("result", {})

    def health(self, timeout: float = 5.0) -> dict[str, Any]:
        return self.call("health", {}, timeout=timeout)

    def observe(self, timeout: float = 10.0) -> dict[str, Any]:
        return self.call("observe", {}, timeout=timeout)

    def execute(self, command: dict[str, Any], timeout: float = 10.0) -> dict[str, Any]:
        return self.call("execute", {"command": command}, timeout=timeout)

    def shutdown(self, timeout: float = 5.0) -> dict[str, Any]:
        try:
            return self.call("shutdown", {}, timeout=timeout)
        finally:
            if self._proc is not None:
                self._proc.terminate()
                self._proc.wait(timeout=5)
                self._proc = None

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None