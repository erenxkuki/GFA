# Contributing to GFA

## Development setup

```bash
python -m pip install -e ".[dev]"
```

## Running tests

```bash
python -m pytest -q
```

## Linting

```bash
ruff check .
ruff format --check .
```

## Guidelines

- Keep modules focused and small.
- Add tests for new behavior.
- Do not fake working features; mark pending phases honestly.
- Never commit secrets or API keys.
- Update docs/DEVELOPMENT_STATUS.md as phases progress.