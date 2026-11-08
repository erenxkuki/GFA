"""GFA Desktop (Tkinter reference shell)."""

from __future__ import annotations

import asyncio
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "gfa-core" / "src"))

from gfa.core.config import ConfigManager
from gfa.core.runtime import Runtime
from gfa.models.manager import ModelManager
from gfa.sessions.manager import SessionManager
from gfa.memory.manager import MemoryManager


class GFADesktop(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GFA — Gaming For AI")
        self.geometry("900x600")
        self.config_manager = ConfigManager()
        self.config_manager.ensure_dirs()
        self.runtime = Runtime(self.config_manager)
        self.runtime.start()
        self.model_manager = ModelManager(self.config_manager)
        self.session_manager = SessionManager(self.config_manager)
        self.memory_manager = MemoryManager(self.config_manager)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self._build_dashboard()
        self._build_models()
        self._build_sessions()
        self._build_memory()
        self._build_settings()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_dashboard(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Dashboard")
        ttk.Label(frame, text="GFA Desktop", font=("Segoe UI", 16, "bold")).pack(pady=10)
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(frame, textvariable=self.status_var).pack()
        h = self.runtime.health()
        ttk.Label(frame, text=f"Runtime state: {h.state}").pack()
        ttk.Label(frame, text=f"Data dir: {self.config_manager.data_dir}").pack()
        ttk.Label(frame, text=f"Models: {len(self.model_manager.list_models())}").pack()
        ttk.Label(frame, text=f"Sessions: {len(self.session_manager.list())}").pack()
        ttk.Label(frame, text=f"Memories: {self.memory_manager.stats()['total']}").pack()

    def _build_models(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="AI Models")
        cols = ("id", "provider", "model", "active")
        tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c)
        tree.pack(fill="both", expand=True)
        for m in self.model_manager.list_models():
            tree.insert("", "end", values=(m.id, m.provider, m.model, m.id == self.model_manager.get_active()))
        ttk.Label(frame, text="Use CLI for add/test: gfa model add ...").pack(pady=5)

    def _build_sessions(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Sessions")
        cols = ("id", "game", "model", "status", "started")
        tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c)
        tree.pack(fill="both", expand=True)
        for s in self.session_manager.list():
            tree.insert("", "end", values=(s.session_id, s.game, f"{s.model_provider}/{s.model_id}", s.status, s.started_at))

    def _build_memory(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Memory")
        cols = ("id", "category", "type", "content")
        tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c)
        tree.pack(fill="both", expand=True)
        for m in self.memory_manager.list(limit=200):
            tree.insert("", "end", values=(m.id, m.category, m.memory_type, m.content[:80]))

    def _build_settings(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Settings")
        ttk.Label(frame, text=f"Config: {self.config_manager.path}").pack(pady=5)
        ttk.Label(frame, text=f"Log level: {self.config_manager.get('log_level')}").pack()

    def _on_close(self):
        self.memory_manager.close()
        self.runtime.stop()
        self.destroy()


def main():
    app = GFADesktop()
    app.mainloop()


if __name__ == "__main__":
    main()