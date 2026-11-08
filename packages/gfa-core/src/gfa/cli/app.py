"""GFA command-line interface."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

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


# ---- memory ----
memory_app = typer.Typer(help="Memory commands")
app.add_typer(memory_app, name="memory")


def get_memory_manager():
    from gfa.memory.manager import MemoryManager
    return MemoryManager(get_config())


@memory_app.command("list")
def memory_list(game: str | None = typer.Option(None, "--game"), category: str | None = typer.Option(None, "--category"),
               limit: int = typer.Option(50, "--limit"), json_output: bool = typer.Option(False, "--json")):
    mm = get_memory_manager()
    recs = mm.list(game_id=game, category=category, limit=limit)
    rows = [r.to_dict() for r in recs]
    if json_output:
        typer.echo(json.dumps(rows, indent=2, default=str))
    else:
        if not rows:
            console.print("No memories.")
            return
        t = Table("ID", "Game", "Category", "Type", "Conf", "Content")
        for r in recs:
            t.add_row(r.id, r.game_id or "-", r.category, r.memory_type, f"{r.confidence:.2f}", r.content[:60])
        console.print(t)


@memory_app.command("search")
def memory_search(query: str, game: str | None = typer.Option(None, "--game"),
                 limit: int = typer.Option(10, "--limit"), json_output: bool = typer.Option(False, "--json")):
    mm = get_memory_manager()
    recs = mm.retrieve(query, game_id=game, limit=limit)
    rows = [r.to_dict() for r in recs]
    if json_output:
        typer.echo(json.dumps(rows, indent=2, default=str))
    else:
        for r in recs:
            console.print(f"[{r.id}] ({r.category}) {r.content}")


@memory_app.command("stats")
def memory_stats(json_output: bool = typer.Option(False, "--json")):
    mm = get_memory_manager()
    data = mm.stats()
    if json_output:
        typer.echo(json.dumps(data, indent=2))
    else:
        console.print_json(json.dumps(data, indent=2))


@memory_app.command("export")
def memory_export(path: str, game: str | None = typer.Option(None, "--game")):
    mm = get_memory_manager()
    n = mm.export_json(Path(path), game_id=game)
    console.print(f"Exported {n} memories to {path}")


@memory_app.command("import")
def memory_import(path: str, overwrite: bool = typer.Option(False, "--overwrite")):
    mm = get_memory_manager()
    n = mm.import_json(Path(path), overwrite=overwrite)
    console.print(f"Imported {n} memories from {path}")


@memory_app.command("compress")
def memory_compress(game: str | None = typer.Option(None, "--game"), json_output: bool = typer.Option(False, "--json")):
    mm = get_memory_manager()
    data = mm.compress(game_id=game)
    if json_output:
        typer.echo(json.dumps(data, indent=2))
    else:
        console.print(f"Compression: {data}")


@memory_app.command("versions")
def memory_versions(memory_id: str, json_output: bool = typer.Option(False, "--json")):
    mm = get_memory_manager()
    data = mm.versions(memory_id)
    if json_output:
        typer.echo(json.dumps(data, indent=2, default=str))
    else:
        console.print_json(json.dumps(data, indent=2, default=str))


# ---- adapter ----
adapter_app = typer.Typer(help="Adapter commands")
app.add_typer(adapter_app, name="adapter")


@adapter_app.command("validate")
def adapter_validate(path: str, json_output: bool = typer.Option(False, "--json")):
    from gfa.adapter_sdk.manifest import validate_manifest_file
    ok, errors, manifest = validate_manifest_file(Path(path) / "manifest.json" if Path(path).is_dir() else Path(path))
    data = {"ok": ok, "errors": errors, "manifest": manifest.model_dump() if manifest else None}
    if json_output:
        typer.echo(json.dumps(data, indent=2, default=str))
    else:
        if ok:
            console.print(f"[green]Valid[/green] {manifest.id} v{manifest.version}")
        else:
            console.print("[red]Invalid[/red]")
            for e in errors:
                console.print(f"  - {e}")
    if not ok:
        raise typer.Exit(code=1) from None


@adapter_app.command("test")
def adapter_test(path: str):
    from gfa.adapter_sdk.host import AdapterHost
    from gfa.adapter_sdk.manifest import validate_manifest_file
    p = Path(path)
    manifest_path = p / "manifest.json" if p.is_dir() else p
    ok, errors, manifest = validate_manifest_file(manifest_path)
    if not ok:
        console.print("[red]Invalid manifest[/red]")
        for e in errors:
            console.print(f"  - {e}")
        raise typer.Exit(code=1) from None
    adir = manifest_path.parent
    host = AdapterHost(manifest, cwd=adir)
    init = host.start()
    console.print(f"Initialize: {init}")
    h = host.health()
    console.print(f"Health: {h}")
    obs = host.observe()
    console.print(f"Observe: {obs}")
    host.shutdown()
    console.print("[green]Adapter test passed[/green]")


@adapter_app.command("init")
def adapter_init(name: str, directory: str = typer.Option(".", "--dir"), language: str = typer.Option("python", "--language")):
    from gfa.adapter_sdk.manifest import AdapterManifest
    d = Path(directory) / name
    d.mkdir(parents=True, exist_ok=True)
    aid = "community." + name.lower().replace(" ", "-")
    if language == "node":
        manifest = AdapterManifest(id=aid, name=name, version="0.1.0", entrypoint="node adapter.js",
                                  capabilities=["example.observe"])
        manifest.to_file(d / "manifest.json")
        (d / "adapter.js").write_text(
            "const readline=require('readline');\n"
            "let init=false,c=0;\n"
            "function respond(id,r,e){const m={jsonrpc:'2.0',id};if(e)m.error=e;else m.result=r;process.stdout.write(JSON.stringify(m)+'\\n');}\n"
            "const rl=readline.createInterface({input:process.stdin});\n"
            "rl.on('line',l=>{l=l.trim();if(!l)return;let r;try{r=JSON.parse(l);}catch(e){respond(null,null,{code:-32700,message:'parse'});return;}\n"
            "const m=r.method,p=r.params||{},id=r.id;\n"
            "if(m==='initialize'){init=true;respond(id,{ok:true,capabilities:['example.observe']});}\n"
            "else if(m==='health'){respond(id,{ok:true,initialized:init});}\n"
            "else if(m==='observe'){c++;respond(id,{observations:[{type:'example',count:c}]});}\n"
            "else if(m==='execute'){respond(id,{status:'succeeded',echoed:p.command});}\n"
            "else if(m==='shutdown'){init=false;respond(id,{ok:true});process.exit(0);}\n"
            "else{respond(id,null,{code:-32601,message:'not found'});}\n});\n",
            encoding="utf-8",
        )
    else:
        manifest = AdapterManifest(id=aid, name=name, version="0.1.0", entrypoint="python adapter.py",
                                  capabilities=["example.observe"])
        manifest.to_file(d / "manifest.json")
        (d / "adapter.py").write_text(
            "import sys, json\n"
            "from pathlib import Path\n"
            "sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'packages' / 'gfa-core' / 'src'))\n"
            "from gfa.adapter_sdk.base import Adapter, AdapterRunner\n"
            "from gfa.adapter_sdk.manifest import AdapterManifest\n"
            "m = AdapterManifest.from_file(Path(__file__).with_name('manifest.json'))\n"
            "class A(Adapter):\n"
            "    def __init__(self, manifest):\n"
            "        super().__init__(manifest); self.c=0\n"
            "    def observe(self):\n"
            "        self.c+=1; return {'observations':[{'type':'example','count':self.c}]}\n"
            "    def execute(self, command):\n"
            "        return {'status':'succeeded','echoed':command}\n"
            "if __name__=='__main__':\n"
            "    AdapterRunner(A(m)).run_stdio()\n",
            encoding="utf-8",
        )
    console.print(f"Scaffolded adapter in {d}")


# ---- game ----
game_app = typer.Typer(help="Game commands")
app.add_typer(game_app, name="game")


@game_app.command("list")
def game_list(json_output: bool = typer.Option(False, "--json")):
    from gfa.universal.windows import list_windows
    wins = list_windows()
    rows = [{"hwnd": w.hwnd, "title": w.title, "rect": w.rect, "pid": w.pid} for w in wins]
    if json_output:
        typer.echo(json.dumps(rows, indent=2))
    else:
        if not rows:
            console.print("No windows found.")
            return
        t = Table("HWND", "Title", "PID")
        for w in wins[:50]:
            t.add_row(str(w.hwnd), w.title[:60], str(w.pid))
        console.print(t)


@game_app.command("detect")
def game_detect(title: str, json_output: bool = typer.Option(False, "--json")):
    from gfa.universal.windows import find_windows
    wins = find_windows(title)
    rows = [{"hwnd": w.hwnd, "title": w.title, "rect": w.rect} for w in wins]
    if json_output:
        typer.echo(json.dumps(rows, indent=2))
    else:
        if not rows:
            console.print(f"No window matching '{title}'.")
        for w in wins:
            console.print(f"{w.hwnd}: {w.title} {w.rect}")


# ---- registry ----
registry_app = typer.Typer(help="Registry commands")
app.add_typer(registry_app, name="registry")


@registry_app.command("search")
def registry_search(query: str, api: str = typer.Option("http://localhost:8000", "--api"), limit: int = typer.Option(20, "--limit"),
                   json_output: bool = typer.Option(False, "--json")):
    import httpx
    try:
        r = httpx.get(f"{api}/adapters", params={"q": query, "limit": limit}, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:  # noqa: BLE001
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from None
    if json_output:
        typer.echo(json.dumps(data, indent=2))
    else:
        for item in data.get("items", []):
            console.print(f"{item['id']} - {item['name']} ({item.get('status')})")


@registry_app.command("info")
def registry_info(adapter_id: str, api: str = typer.Option("http://localhost:8000", "--api"), json_output: bool = typer.Option(False, "--json")):
    import httpx
    try:
        r = httpx.get(f"{api}/adapters/{adapter_id}", timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:  # noqa: BLE001
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from None
    if json_output:
        typer.echo(json.dumps(data, indent=2, default=str))
    else:
        console.print_json(json.dumps(data, indent=2, default=str))


@registry_app.command("health")
def registry_health(api: str = typer.Option("http://localhost:8000", "--api")):
    import httpx
    try:
        r = httpx.get(f"{api}/health", timeout=5)
        r.raise_for_status()
        console.print(r.json())
    except Exception as exc:  # noqa: BLE001
        err.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from None


@app.command()
def logs(lines: int = typer.Option(50, "--lines", "-n"), json_output: bool = typer.Option(False, "--json")):
    """Show recent log lines."""
    from gfa.core.config import default_data_dir
    log_dir = default_data_dir() / "logs"
    files = sorted(log_dir.glob("*.log")) if log_dir.exists() else []
    if not files:
        console.print("No log files.")
        return
    f = files[-1]
    content = f.read_text(encoding="utf-8", errors="replace").splitlines()
    tail = content[-lines:]
    if json_output:
        typer.echo(json.dumps({"file": str(f), "lines": tail}, indent=2))
    else:
        for ln in tail:
            console.print(ln)


def main():
    app()


if __name__ == "__main__":
    main()