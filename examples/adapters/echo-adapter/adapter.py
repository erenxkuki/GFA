import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages" / "gfa-core" / "src"))

from gfa.adapter_sdk.base import Adapter, AdapterRunner
from gfa.adapter_sdk.manifest import AdapterManifest

manifest = AdapterManifest.from_file(Path(__file__).with_name("manifest.json"))


class EchoAdapter(Adapter):
    def __init__(self, manifest):
        super().__init__(manifest)
        self._counter = 0

    def observe(self):
        self._counter += 1
        return {"observations": [{"type": "echo", "count": self._counter}]}

    def execute(self, command):
        return {"status": "succeeded", "echoed": command}


if __name__ == "__main__":
    adapter = EchoAdapter(manifest)
    AdapterRunner(adapter).run_stdio()