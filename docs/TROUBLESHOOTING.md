# Troubleshooting

- `gfa doctor` reports missing dependencies: install with `pip install -e ".[dev]"`.
- Model connection fails: verify endpoint and run `gfa model test <id>`. For Ollama, ensure server running on port 11434.
- Capture returns empty/black: ensure target window is visible and not protected by anti-cheat/DRM.
- Clicks don't register: window must be foreground; some apps require focus. Check emergency stop state.
- Tests fail on headless machine: integration tests require an interactive desktop session.