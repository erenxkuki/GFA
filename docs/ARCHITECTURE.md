# GFA Architecture

## Principles

- Model independence: GFA owns gameplay infrastructure; the model provides reasoning.
- Universal Baseline first: general computer interaction (screen, keyboard, mouse) works without adapters.
- Adapters enhance, never required.
- Memory belongs to GFA, not the LLM.
- Local-first.

## Current module layout

```
gfa/
├── core/          config, logging, events, runtime, diagnostics
├── models/        provider abstraction, connectors, manager, credentials
├── sessions/      session records and manager
├── gcl/           GFA Command Language v1 (schema, parser, validator, executor, capabilities)
├── cli/           Typer CLI
└── (future) memory/, observation/, perception/, universal-baseline/, adapter-sdk/, registry-client/
```

## Key interfaces

- `ModelProvider` (models/base.py): test_connection, list_models, chat, detect_capabilities.
- `Runtime` (core/runtime.py): lifecycle, health, events.
- `SessionManager` (sessions/manager.py).
- `GCLValidator` / `CommandExecutor` (gcl/*).
- `CapabilitySet` (gcl/capabilities.py).

## Data storage

- Config: JSON at OS config dir (`%APPDATA%/GFA/config.json`).
- Secrets: encrypted local file (Fernet) + optional OS keyring.
- Sessions: JSON files under data/sessions.
- Future: SQLite + vector index for memory.