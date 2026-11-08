"""GFA command-line interface."""

from __future__ import annotations

import asyncio
import json

import typer
from rich.console import Console
from rich.table import Table

from gfa import __version__
from gfa.core.config import ConfigManager
from gfa.core.diagnostics import run_doctor
from gfa.core.runtime import Runtime
from gfa.models.base import ModelConfig
from gfa.models.manager import ModelManager
from gfa.models.registry import list_providers, normalize_provider
from gfa.sessions.manager import SessionManager

app = typer.Typer(name="gfa", help="GFA — Gaming For AI", no_args_is_help=True, add_completion=False)
console = Console()
err = Console(stderr=True)

# Shared state
_config: ConfigManager | None = None
_runtime: Runtime | None = None


def get_config() -> ConfigManager:
    global _config
    if _config is None:
        _config = ConfigManager()
    return _config


def get_runtime() -> Runtime:
    global _runtime
    if _runtime is None:
        _runtime = Runtime(get_config())
        _runtime.start()
    return _runtime


def get_model_manager() -> ModelManager:
    return ModelManager(get_config())


def get_session_manager() -> SessionManager:
    return SessionManager(get_config())


def _json_out(data, json_mode: bool):
    if json_mode:
        typer.echo(json.dumps(data, indent=2, default=str))
    return json_mode


@app.command()
def version(json_output: bool = typer.Option(False, "--json", help="Output JSON")):
    """Print GFA version."""
    data = {"version": __version__}
    if json_output:
        typer.echo(json.dumps(data))
    else:
        console.print(f"GFA version {__version__}")


@app.command()
def doctor(json_output: bool = typer.Option(False, "--json", help="Output JSON")):
    """Run diagnostics."""
    data = run_doctor(get_config(), get_runtime())
    if json_output:
        typer.echo(json.dumps(data, indent=2, default=str))
    else:
        console.print("[bold]GFA Doctor[/bold]")
        for k, v in data.items():
            if isinstance(v, dict):
                console.print(f"  {k}:")
                for kk, vv in v.items():
                    console.print(f"    {kk}: {vv}")
            else:
                console.print(f"  {k}: {v}")


# ---- config ----
config_app = typer.Typer(help="Configuration commands")
app.add_typer(config_app, name="config")


@config_app.command("show")
def config_show(json_output: bool = typer.Option(False, "--json")):
    """Show current configuration."""
    cfg = get_config()
    data = cfg.all()
    # redact nothing here; secrets are not stored in config
    if json_output:
        typer.echo(json.dumps(data, indent=2, default=str))
    else:
        console.print_json(json.dumps(data, indent=2, default=str))


# ---- model ----
model_app = typer.Typer(help="Model commands")
app.add_typer(model_app, name="model")


@model_app.command("providers")
def model_providers(json_output: bool = typer.Option(False, "--json")):
    """List supported providers."""
    data = list_providers()
    if json_output:
        typer.echo(json.dumps(data, indent=2))
    else:
        t = Table("ID", "Name")
        for p in data:
            t.add_row(p["id"], p["name"])
        console.print(t)


@model_app.command("list")
def model_list(json_output: bool = typer.Option(False, "--json")):
    """List configured models."""
    mm = get_model_manager()
    models = mm.list_models()
    active = mm.get_active()
    rows = []
    for m in models:
        rows.append({
            "id": m.id,
            "provider": m.provider,
            "endpoint": m.endpoint,
            "model": m.model,
            "active": m.id == active,
        })
    if json_output:
        typer.echo(json.dumps({"active": active, "models": rows}, indent=2))
    else:
        if not rows:
            console.print("No models configured. Use `gfa model add`.")
            return
        t = Table("ID", "Provider", "Model", "Endpoint", "Active")
        for r in rows:
            t.add_row(r["id"], r["provider"], r["model"], r["endpoint"], "yes" if r["active"] else "")
        console.print(t)


@model_app.command("add")
def model_add(
    model_id: str = typer.Option(..., "--id", help="Unique config id"),
    provider: str = typer.Option(..., "--provider", help="Provider (ollama, openai, lmstudio, openai-compatible)"),
    model: str = typer.Option(..., "--model", help="Model identifier"),
    endpoint: str | None = typer.Option(None, "--endpoint", help="Endpoint URL"),
    api_key: str | None = typer.Option(None, "--api-key", help="API key (stored securely, not in config)"),
    timeout: float = typer.Option(60.0, "--timeout"),
    set_active: bool = typer.Option(False, "--set-active"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Add a model configuration."""
    mm = get_model_manager()
    cfg = ModelConfig(
        id=model_id,
        provider=normalize_provider(provider),
        endpoint=endpoint or "",
        model=model,
        timeout=timeout,
    )
    try:
        mm.add(cfg, api_key=api_key)
    except Exception as exc:  # noqa: BLE001
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from None
    if set_active:
        mm.set_active(model_id)
    data = {"id": model_id, "provider": cfg.provider, "model": cfg.model}
    if json_output:
        typer.echo(json.dumps(data))
    else:
        console.print(f"[green]Added model[/green] {model_id}")


@model_app.command("remove")
def model_remove(model_id: str, json_output: bool = typer.Option(False, "--json")):
    """Remove a model configuration."""
    mm = get_model_manager()
    ok = mm.remove(model_id)
    if not ok:
        err.print(f"[red]Not found:[/red] {model_id}")
        raise typer.Exit(code=1) from None
    if mm.get_active() == model_id:
        mm.set_active(None)
    console.print(f"Removed {model_id}")


@model_app.command("test")
def model_test(model_id: str, json_output: bool = typer.Option(False, "--json")):
    """Test a model connection."""
    mm = get_model_manager()
    try:
        result = asyncio.run(mm.test(model_id))
    except Exception as exc:  # noqa: BLE001
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from None
    if json_output:
        typer.echo(json.dumps(result, indent=2, default=str))
    else:
        ok = result.get("ok")
        console.print(f"Connection: {'[green]OK[/green]' if ok else '[red]FAILED[/red]'}")
        console.print(f"Message: {result.get('message')}")
        details = result.get("details") or {}
        if details:
            console.print_json(json.dumps(details, default=str))


@model_app.command("set-active")
def model_set_active(model_id: str):
    """Set the active model."""
    mm = get_model_manager()
    try:
        mm.set_active(model_id)
    except Exception as exc:  # noqa: BLE001
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from None
    console.print(f"Active model set to {model_id}")


@model_app.command("discover")
def model_discover(model_id: str, json_output: bool = typer.Option(False, "--json")):
    """List models available on a configured provider."""
    mm = get_model_manager()
    try:
        models = asyncio.run(mm.list_remote_models(model_id))
    except Exception as exc:  # noqa: BLE001
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from None
    if json_output:
        typer.echo(json.dumps(models))
    else:
        for m in models:
            console.print(m)


@model_app.command("chat")
def model_chat(
    model_id: str | None = typer.Option(None, "--model", help="Model config id (defaults to active)"),
    prompt: str = typer.Option(..., "--prompt", "-p"),
    system: str | None = typer.Option(None, "--system"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Send a single chat prompt to a model."""
    mm = get_model_manager()
    mid = model_id or mm.get_active()
    if not mid:
        err.print("[red]No active model. Use `gfa model set-active` or --model.[/red]")
        raise typer.Exit(code=1) from None
    from gfa.models.base import ChatMessage, ChatRequest

    messages = []
    if system:
        messages.append(ChatMessage(role="system", content=system))
    messages.append(ChatMessage(role="user", content=prompt))
    provider = mm.build_provider(mid)
    try:
        resp = asyncio.run(provider.chat(ChatRequest(messages=messages)))
    except Exception as exc:  # noqa: BLE001
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from None
    if json_output:
        typer.echo(json.dumps({"text": resp.text, "model": resp.model, "usage": resp.usage}, indent=2))
    else:
        console.print(resp.text)


# ---- session ----
session_app = typer.Typer(help="Session commands")
app.add_typer(session_app, name="session")


@session_app.command("list")
def session_list(status: str | None = typer.Option(None, "--status"), limit: int = typer.Option(50, "--limit"),
                 json_output: bool = typer.Option(False, "--json")):
    """List sessions."""
    sm = get_session_manager()
    sessions = sm.list(status=status, limit=limit)
    rows = [s.to_dict() for s in sessions]
    if json_output:
        typer.echo(json.dumps(rows, indent=2, default=str))
    else:
        if not rows:
            console.print("No sessions.")
            return
        t = Table("ID", "Game", "Model", "Status", "Started")
        for s in sessions:
            t.add_row(s.session_id, s.game or "-", f"{s.model_provider or ''}/{s.model_id or ''}".strip("/"), s.status, s.started_at)
        console.print(t)


@session_app.command("create")
def session_create(
    game: str | None = typer.Option(None, "--game"),
    model: str | None = typer.Option(None, "--model", help="Model config id"),
    json_output: bool = typer.Option(False, "--json"),
):
    """Create a new session."""
    mm = get_model_manager()
    sm = get_session_manager()
    mid = model or mm.get_active()
    model_provider = None
    model_id = None
    if mid:
        cfg = mm.get(mid)
        model_provider = cfg.provider
        model_id = cfg.model
    rec = sm.create(game=game, model_provider=model_provider, model_id=model_id, adapter_id=None)
    if json_output:
        typer.echo(json.dumps(rec.to_dict(), indent=2, default=str))
    else:
        console.print(f"Created session {rec.session_id}")


@session_app.command("show")
def session_show(session_id: str, json_output: bool = typer.Option(False, "--json")):
    """Show a session."""
    sm = get_session_manager()
    try:
        rec = sm.get(session_id)
    except Exception as exc:  # noqa: BLE001
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from None
    data = rec.to_dict()
    if json_output:
        typer.echo(json.dumps(data, indent=2, default=str))
    else:
        console.print_json(json.dumps(data, indent=2, default=str))


@session_app.command("status")
def session_status(session_id: str, status: str, json_output: bool = typer.Option(False, "--json")):
    """Update session status."""
    sm = get_session_manager()
    try:
        rec = sm.update_status(session_id, status)
    except Exception as exc:  # noqa: BLE001
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from None
    console.print(f"{session_id} -> {rec.status}")


def main():
    app()


if __name__ == "__main__":
    main()