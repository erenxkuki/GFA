"""Model configuration and credential management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

from gfa.core.config import ConfigManager
from gfa.models.base import ModelCapabilities, ModelConfig
from gfa.models.registry import create_provider
from gfa.shared.errors import ConfigurationError, NotFoundError


class CredentialStore:
    """Encrypted local credential storage with optional OS keyring backend."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self._dir = data_dir / "secrets"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._key_path = self._dir / "master.key"
        self._store_path = self._dir / "secrets.enc"
        self._fernet = Fernet(self._load_or_create_key())
        self._cache: dict[str, str] = self._load()

    def _load_or_create_key(self) -> bytes:
        if self._key_path.exists():
            return self._key_path.read_bytes()
        key = Fernet.generate_key()
        self._key_path.write_bytes(key)
        try:
            if __import__("os").name == "posix":
                self._key_path.chmod(0o600)
        except Exception:  # noqa: BLE001
            pass
        return key

    def _load(self) -> dict[str, str]:
        if not self._store_path.exists():
            return {}
        try:
            raw = self._fernet.decrypt(self._store_path.read_bytes())
            return json.loads(raw.decode("utf-8"))
        except Exception:  # noqa: BLE001
            return {}

    def _persist(self) -> None:
        raw = json.dumps(self._cache).encode("utf-8")
        self._store_path.write_bytes(self._fernet.encrypt(raw))

    def get(self, key: str) -> str | None:
        # Try OS keyring first if available
        try:
            import keyring  # type: ignore

            val = keyring.get_password("gfa", key)
            if val is not None:
                return val
        except Exception:  # noqa: BLE001
            pass
        return self._cache.get(key)

    def set(self, key: str, value: str) -> None:
        try:
            import keyring  # type: ignore

            keyring.set_password("gfa", key, value)
            # also keep local cache as fallback
        except Exception:  # noqa: BLE001
            pass
        self._cache[key] = value
        self._persist()

    def delete(self, key: str) -> bool:
        try:
            import keyring  # type: ignore

            keyring.delete_password("gfa", key)
        except Exception:  # noqa: BLE001
            pass
        if key in self._cache:
            del self._cache[key]
            self._persist()
            return True
        return False


class ModelManager:
    def __init__(self, config: ConfigManager):
        self.config = config
        self.credentials = CredentialStore(config.data_dir)
        self._models: list[ModelConfig] = self._load_models()

    def _load_models(self) -> list[ModelConfig]:
        raw = self.config.get("models", []) or []
        out = []
        for item in raw:
            try:
                out.append(ModelConfig(**{k: v for k, v in item.items() if k != "api_key"}))
            except Exception:  # noqa: BLE001
                continue
        return out

    def _save_models(self) -> None:
        self.config.set("models", [m.model_dump(exclude={"api_key"}) for m in self._models])
        self.config.save()

    def list_models(self) -> list[ModelConfig]:
        return list(self._models)

    def get(self, model_id: str) -> ModelConfig:
        for m in self._models:
            if m.id == model_id:
                return m
        raise NotFoundError(f"Model config not found: {model_id}", code="model_not_found")

    def add(self, config: ModelConfig, api_key: str | None = None) -> ModelConfig:
        if not config.endpoint:
            from gfa.models.registry import DEFAULT_ENDPOINTS, normalize_provider
            key = normalize_provider(config.provider)
            if key in DEFAULT_ENDPOINTS:
                config.endpoint = DEFAULT_ENDPOINTS[key]
        if any(m.id == config.id for m in self._models):
            raise ConfigurationError(f"Model id already exists: {config.id}", code="duplicate_model")
        if api_key:
            self.credentials.set(f"model:{config.id}", api_key)
            config.api_key = None
        self._models.append(config)
        self._save_models()
        return config

    def remove(self, model_id: str) -> bool:
        before = len(self._models)
        self._models = [m for m in self._models if m.id != model_id]
        if len(self._models) == before:
            return False
        self.credentials.delete(f"model:{model_id}")
        self._save_models()
        return True

    def update(self, model_id: str, **fields: Any) -> ModelConfig:
        m = self.get(model_id)
        for k, v in fields.items():
            if k == "api_key":
                if v:
                    self.credentials.set(f"model:{model_id}", v)
                else:
                    self.credentials.delete(f"model:{model_id}")
            elif hasattr(m, k):
                setattr(m, k, v)
        self._save_models()
        return m

    def resolve_secret(self, model_id: str) -> str | None:
        return self.credentials.get(f"model:{model_id}")

    def to_provider_config(self, model_id: str) -> ModelConfig:
        m = self.get(model_id)
        cfg = m.model_copy()
        cfg.api_key = self.resolve_secret(model_id)
        return cfg

    def set_active(self, model_id: str | None) -> None:
        if model_id is not None:
            self.get(model_id)
        self.config.set("active_model", model_id)
        self.config.save()

    def get_active(self) -> str | None:
        return self.config.get("active_model")

    async def test(self, model_id: str) -> dict[str, Any]:
        cfg = self.to_provider_config(model_id)
        provider = create_provider(cfg)
        result = await provider.test_connection()
        # capability detection
        try:
            caps = await provider.detect_capabilities()
            result.setdefault("details", {})["capabilities"] = caps.model_dump()
        except Exception as exc:  # noqa: BLE001
            result.setdefault("details", {})["capability_error"] = str(exc)
        return result

    async def list_remote_models(self, model_id: str) -> list[str]:
        cfg = self.to_provider_config(model_id)
        provider = create_provider(cfg)
        return await provider.list_models()

    def build_provider(self, model_id: str):
        cfg = self.to_provider_config(model_id)
        return create_provider(cfg)

    @staticmethod
    def default_capabilities(provider: str) -> ModelCapabilities:
        return ModelCapabilities()