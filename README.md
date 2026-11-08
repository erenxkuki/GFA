# GFA — Gaming For AI

Open-source, model-independent gaming infrastructure for artificial intelligence.

**OBSERVE. THINK. PLAY. LEARN.**

GFA connects AI models to video games through a universal interaction baseline, a controlled command language (GCL), persistent provider-independent memory, and an adapter ecosystem.

## Status

Early development. Current milestone: **Phase 0–2 complete** (core runtime, CLI, model connectors, GCL v1). Gameplay phases (4+) in progress.

See `docs/DEVELOPMENT_STATUS.md`.

## Install (development)

```bash
python -m pip install -e .
gfa --help
gfa doctor
```

## Quick start

```bash
# Add a local Ollama model
gfa model add --id local-llama --provider ollama --model llama3 --set-active
gfa model test local-llama

# Or an OpenAI-compatible endpoint
gfa model add --id openai-gpt --provider openai --model gpt-4o-mini --api-key sk-... --set-active

# Chat
gfa model chat --prompt "Hello"

# Sessions
gfa session create --game "Sandbox"
gfa session list
```

## Repository layout

See `docs/ARCHITECTURE.md`.

## License

MIT.