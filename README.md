<div align="center">

# 🎮 GFA — Gaming For AI

### Open-source, model-independent gaming infrastructure for artificial intelligence

**OBSERVE · THINK · PLAY · LEARN**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-39%20passing-brightgreen.svg)](#testing)
[![Version](https://img.shields.io/badge/version-0.1.0-orange.svg)](#)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

> Connect any AI model to any video game.  
> Universal interaction baseline · Persistent memory · Community adapters · Bring your own AI.

</div>

---

## ✨ What is GFA?

**GFA (Gaming For AI)** is an open-source framework that lets artificial intelligence models **observe, understand, control, and learn from** video games.

You bring your own AI — local LLMs, OpenAI, Anthropic, LM Studio, or any OpenAI-compatible endpoint. GFA supplies the infrastructure:

- 🖥️ **Universal Baseline** — screen capture + keyboard/mouse/controller input. Works with *any* game, no adapter required.
- 🧠 **Agent Intelligence** — structured observe → reason → plan → act → evaluate → replan loop.
- 📜 **GCL (GFA Command Language)** — a versioned, validated command protocol between AI decisions and game execution.
- 💾 **Persistent Memory** — five memory categories (working, episodic, semantic, procedural, spatial) that survive model switches.
- 🔌 **Adapter SDK** — build deeper game integrations in Python, Node.js, or any language via JSON-RPC.
- 🌐 **Registry & Website** — discover, publish, and verify community adapters.
- 🖥️ **Desktop App + CLI** — full graphical and command-line interfaces.

---

## 🚀 Quick Start

```bash
# 1. Install
git clone https://github.com/erenxkuki/GFA.git
cd GFA
python -m pip install -e ".[dev]"

# 2. Check your setup
gfa doctor

# 3. Connect a model (Ollama example)
gfa model add --id local-llama --provider ollama --model llama3 --set-active
gfa model test local-llama

# 4. Chat with it
gfa model chat --prompt "Hello from GFA"

# 5. Create a gameplay session
gfa session create --game "Sandbox"
gfa session list

# 6. Launch the desktop app
python apps/desktop/main.py
```

---

## 🏗️ Architecture

```
GFA ECOSYSTEM
├── GFA Desktop (Tkinter shell / Tauri planned)
├── GFA CLI (typer)
├── GFA Core
│   ├── Agent Runtime (observe → think → play → learn)
│   ├── Observation Engine · Perception Pipeline
│   ├── Reasoning Coordinator · Planning Engine
│   ├── Command Generator · Validator · Executor
│   └── Session Coordinator
├── Universal Baseline
│   ├── Screen Capture (GDI → PNG) · Window Detection
│   └── Keyboard · Mouse · Controller Input
├── Model Connectors
│   ├── Ollama · OpenAI · LM Studio · Custom (OpenAI-compatible)
│   └── Capability detection · Secure credential storage
├── GFA Command Language (GCL v1)
├── Memory Engine (5 categories, SQLite, retrieval, compression)
├── Adapter SDK (manifest, JSON-RPC, Python/Node examples)
├── Registry API (FastAPI + SQLite)
└── Registry Website (discovery, publish, docs)
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for details.

---

## 🧠 Core Principles

| Principle | Description |
|---|---|
| **Model Independence** | GFA owns the infrastructure. Swap models without losing knowledge. |
| **Universal Baseline** | Play any game via screen + input. No adapter required. |
| **Adapters Enhance** | Dedicated adapters add structured state. Never mandatory. |
| **Persistent Memory** | Memory belongs to GFA, not the LLM. Survives restarts & model switches. |
| **Local-First** | Memories, config, and credentials stay on your machine by default. |
| **Open Ecosystem** | Build and publish adapters independently. |

---

## 📦 Project Structure

```
gfa/
├── apps/
│   ├── desktop/          # Tkinter desktop shell
│   ├── registry-api/     # FastAPI registry backend
│   └── registry-web/     # Discovery website
├── packages/gfa-core/src/gfa/
│   ├── core/             # Config, logging, events, runtime, sessions, diagnostics
│   ├── models/           # Provider abstraction + connectors + credentials
│   ├── universal/        # Universal Baseline (capture, input, windows)
│   ├── gcl/              # GFA Command Language v1
│   ├── agent/            # Perception, world state, reasoning, planning, agent loop
│   ├── memory/           # 5-category memory engine (SQLite)
│   ├── adapter_sdk/      # Manifest, JSON-RPC, host, base adapter
│   ├── arena/            # AI Arena (multi-agent matches)
│   └── cli/              # Typer CLI
├── official-adapters/    # Official reference adapters
├── examples/adapters/    # Example adapters (Python + Node.js)
├── tests/                # Unit + integration tests
├── docs/                 # Architecture, guides, specs
└── dist/                 # Release wheels
```

---

## 🎯 Features

### Real-Time Action System (Shooters, Racing, Fighting)
- **Genre profiles** — shooter, racing, fighting, platformer, story — each tuned for FPS, input rate, smoothing, aim assist
- **Motion tracking & prediction** — tracks entities across frames, predicts future positions (lead targeting)
- **Aim assist** — target selection within FOV, smoothing, prediction compensation
- **Steering controller** — deadzone, speed-sensitive reduction, progressive smoothing for racing
- **High-frequency game loop** — runs at 30-60 FPS with reflex-first, model-at-reduced-rate
- **Reflex layer** — instant reactions bypass model reasoning entirely
- **Synchronous input** — keyboard + mouse sent simultaneously (WASD + mouse look in one SendInput batch)
- **Latency optimization** — adaptive frame skipping, OCR throttling, speculative execution (branch prediction), input coalescing
- **Audio perception** — sound event detection & classification (gunshot, explosion, footsteps, music, voice, alerts, SFX) from PCM frames, cooldown-based event buffer, agent awareness of audio events; live WASAPI loopback capture (PowerShell + inline C# COM interop)
- **Session replay** — record screenshots + model reasoning + GCL commands per step, timeline viewer with frame lookup and scrubbing, CLI (`gfa replay list/show/frames/export`)
- **Human-in-the-loop corrections** — pending correction queue (preference/override/avoid/positive), injection into the agent world state, learning loop that stores corrections as verified procedural memories; CLI (`gfa feedback add/list/clear/delete`)
- **Macro recording & playback** — record executed steps with timing into named macros, timed player with speed scaling, `macro` GCL command, agent-level recording (`start/stop_macro_recording`); CLI (`gfa macro list/show/delete/export/import`)
- **World model / prediction** — track moving objects (velocity estimation), predict next-frame positions, detect incoming threats with time-to-impact and dodge recommendations; feeds `WorldState.incoming_threats` for reflex rules
- **RL integration** — reward extraction (score/health/progress deltas), persistent reward ledger with stats, bandit-style strategy scorer (average reward per action signature) with best-action hints in the world state
- **Semantic memory embeddings** — dependency-free deterministic hash embedder (word tokens + char 3-grams) with cosine retrieval; pluggable scorer (`keyword` default / `semantic` / `hybrid`) with cached embeddings
- **Per-game keybind profiles** — configurable key mappings, mouse sensitivity/inversion, presets for FPS/racing/platformer, save/load, CLI commands
- **Combat combos** — predefined input sequences (dodge, 3-hit, parry counter, dash attack) with precise timing and cooldowns
- **3D spatial awareness** — depth estimation from 2D cues, threat detection, nearest object finding
- **Multi-view reconstruction** — look around to build a spatial map from multiple angles (like human mental mapping)

### Frame Generation (DLSS-style for AI)
- **Perception frame generation** — like DLSS/FSR frame gen: captures at reduced rate, interpolates intermediate perception states using motion prediction + frame diff
- **Keyframe detection** — full perception (OCR, color detection) only runs on keyframes or when significant change detected
- **Velocity prediction** — object positions extrapolated between captures
- **Massive cost reduction** — 5× fewer OCR calls, 5× fewer vision passes, AI stays responsive

### Computer Vision & Token Optimization
- **Windows OCR** — extracts in-game text (dialogue, objectives, menus, HUD) via built-in WinRT OCR, no external deps
- **Compact state mode** — convert frames to short text summaries instead of full screenshots (≈10× fewer tokens)
- **UI region detection** — health bars, minimap, dialogue, menus
- **Object & change tracking** — color-blob detection with movement deltas
- **Hybrid/full modes** — send small thumbnail or full image when needed
- **Multimodal messages** — vision-capable models receive image + text

### Model Connections
- **Ollama** (local)
- **OpenAI** (cloud)
- **LM Studio** (local)
- **Any OpenAI-compatible endpoint** (custom)
- Secure credential storage (encrypted local + optional OS keyring)
- Capability detection (vision, streaming, structured output, context window)

### GCL v1 Commands
`observe` · `move` · `click` · `scroll` · `key` · `type_text` · `wait` · `verify` · `session_*` · `emergency_stop` · `invoke` (extensions)

### Memory Categories
| Category | Purpose |
|---|---|
| **Working** | Current objective, plan, recent observations |
| **Episodic** | What happened in past sessions |
| **Semantic** | Learned facts about the game |
| **Procedural** | Successful strategies and skills |
| **Spatial** | Explored areas and landmarks |

### Adapter Ecosystem
- Language-independent JSON-RPC protocol
- Manifest schema + validation
- Python & Node.js reference adapters
- Registry API with search, pagination, verification, releases
- Trust levels: Official · Verified · Community · Deprecated

---

## 🖥️ CLI Reference

```bash
gfa --help
gfa version
gfa doctor

gfa model list | add | test | remove | set-active | discover | chat
gfa session list | create | show | status
gfa memory list | search | stats | export | import | compress | versions
gfa game list | detect
gfa adapter init | validate | test
gfa registry search | info | health
gfa config show
gfa logs
```

All commands support `--json` for machine-readable output.

---

## 🧪 Testing

```bash
python -m pytest -q          # run all tests
ruff check .                 # lint
```

**39 tests** across unit and integration suites, including:
- Model connection (mocked HTTP)
- GCL parsing/validation/execution
- Universal Baseline (real screen capture + click on Tkinter sandbox)
- Agent completing a real objective in a sandbox game
- Memory persistence across restart + model switch
- Adapter SDK (Python + Node.js end-to-end)
- Registry API (submit, search, releases, checksums)

---

## 📚 Documentation

| Document | Description |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture |
| [docs/INSTALLATION.md](docs/INSTALLATION.md) | Installation guide |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common issues |
| [docs/UNIVERSAL_BASELINE.md](docs/UNIVERSAL_BASELINE.md) | Universal Baseline guide |
| [docs/ADAPTER_SDK.md](docs/ADAPTER_SDK.md) | Adapter SDK reference |
| [docs/DEVELOPMENT_STATUS.md](docs/DEVELOPMENT_STATUS.md) | Phase progress tracker |

---

## 🛣️ Roadmap

- [x] Phase 0–3: Core runtime, model connectors, GCL v1
- [x] Phase 4: Universal Baseline
- [x] Phase 5: Agent intelligence
- [x] Phase 6: Persistent memory engine
- [x] Phase 7: Adapter SDK
- [x] Phase 8: Official adapters (reference)
- [x] Phase 9: Registry backend
- [x] Phase 10: Community website
- [x] Phase 11: Desktop application
- [x] Phase 12: CLI & developer experience
- [x] Phase 13: AI Arena
- [x] Phase 14: Production readiness

**Future:** Tauri desktop client, real game adapters, advanced perception (OCR/CV), vector memory search, mobile support.

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). We welcome:
- New game adapters
- Perception extensions
- Memory improvements
- Documentation
- Bug reports

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
ruff check .
```

---

## 🔒 Security

- API keys stored in encrypted local files (Fernet) + optional OS keyring. Never in config or logs.
- Adapters run as isolated processes with declared permissions.
- Game content treated as untrusted (prompt-injection resistant).
- Emergency stop always available.
- No anti-cheat/DRM bypass. Permitted interfaces only.

See [SECURITY.md](SECURITY.md).

---

## 📄 License

MIT License — see [LICENSE](LICENSE).

---

<div align="center">

**GFA — Gaming For AI**  
*OBSERVE. THINK. PLAY. LEARN.*

Built with ❤️ by the GFA community.

</div>