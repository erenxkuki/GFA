# Universal Baseline

General-purpose gameplay interaction without a dedicated adapter.

## Capabilities
- Window enumeration and selection (`gfa.universal.windows`).
- Screen capture to PNG (`gfa.universal.capture`), with scaling.
- Keyboard, mouse, scroll input (`gfa.universal.input`).
- Controller state reading (XInput).
- Emergency stop and input release.

## Usage
```python
from gfa.universal.baseline import BaselineConfig, UniversalBaseline

bl = UniversalBaseline(BaselineConfig(target_window_title="My Game", capture_scale=0.5))
bl.select_window("My Game")
frame = bl.observe()  # CapturedFrame with PNG
bl.move("forward", 800)
bl.click("left", 100, 200)
bl.emergency_stop()
```

## GCL integration
`UniversalBaseline.register_gcl_handlers(executor)` wires observe/move/click/scroll/key/type_text/wait/verify/emergency_stop.

## Limitations
- Controller *output* is not supported without a virtual controller driver (ViGEm); only state reading.
- Some games (anti-cheat, protected windows) may be incompatible. GFA does not bypass security.