# Adapter SDK

Adapters are separate processes communicating over JSON-RPC 2.0 on stdio.

## Manifest
See `gfa.adapter_sdk.manifest.AdapterManifest`. Required: id, name, version, entrypoint.

## Base class
Subclass `gfa.adapter_sdk.base.Adapter` and implement `initialize`, `health`, `observe`, `execute`, `shutdown`.

## Run
```python
from gfa.adapter_sdk.base import AdapterRunner
AdapterRunner(MyAdapter(manifest)).run_stdio()
```

## Host
```python
from gfa.adapter_sdk.host import AdapterHost
host = AdapterHost(manifest, cwd=adapter_dir)
host.start(); host.observe(); host.execute(cmd); host.shutdown()
```

## CLI
- `gfa adapter init <name> [--language python|node]`
- `gfa adapter validate <path>`
- `gfa adapter test <path>`

## Language independence
Any language implementing the JSON-RPC protocol works (see `examples/adapters/echo-adapter-node`).