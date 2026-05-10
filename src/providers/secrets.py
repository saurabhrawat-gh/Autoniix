"""Pluggable secret backend for provider credentials.

Lookup order driven by ``SECRETS_BACKEND``:
    - ``infisical``: Infisical universal-auth client (recommended).
    - ``vault``:     HashiCorp Vault KV v2.
    - ``env``:       Plain process environment (legacy, default).

The public surface is intentionally tiny:

    >>> get_secret("openai", "api_key")        # by canonical provider/key
    >>> get_secret_at("kv/data/llm/openai/x")   # by absolute backend path

Failures fall through to the next backend in ``SECRETS_FALLBACK`` (default:
``env``), so a Vault outage cannot block a worker that already has its
key in env. This is intentional — keys are typically static during a
deploy, and resilience matters more than enforcing a single source of
truth at runtime.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Protocol

import structlog

logger = structlog.get_logger()


class SecretBackend(Protocol):
    name: str

    def get(self, path: str, key: str) -> str | None: ...
    def put(self, path: str, key: str, value: str) -> None: ...
    def health(self) -> bool: ...


# ── Env backend ─────────────────────────────────────────────
class EnvBackend:
    """Reads ``{PROVIDER}_{KEY}`` from process env (uppercased).

    e.g. ``EnvBackend().get("openai", "api_key")`` reads ``OPENAI_API_KEY``.
    Path-style lookups translate ``a/b/c`` -> ``A_B_C``.
    """
    name = "env"

    def get(self, path: str, key: str) -> str | None:
        path_part = path.replace("/", "_").replace("-", "_").replace(".", "_").upper()
        candidates = [f"{path_part}_{key.upper()}", key.upper()]
        for name in candidates:
            v = os.getenv(name)
            if v:
                return v
        return None

    def put(self, path: str, key: str, value: str) -> None:
        # Env is read-only for our purposes.
        raise NotImplementedError("EnvBackend is read-only")

    def health(self) -> bool:
        return True


# ── Vault backend (KV v2) ───────────────────────────────────
class VaultBackend:
    name = "vault"

    def __init__(self) -> None:
        try:
            import hvac  # type: ignore
        except Exception as exc:
            raise RuntimeError(f"hvac unavailable: {exc}")
        addr = os.getenv("VAULT_ADDR", "http://vault:8200")
        token = os.getenv("VAULT_TOKEN", "")
        self._client = hvac.Client(url=addr, token=token)
        self._mount = os.getenv("VAULT_KV_MOUNT", "kv")

    def get(self, path: str, key: str) -> str | None:
        try:
            res = self._client.secrets.kv.v2.read_secret_version(
                path=path, mount_point=self._mount
            )
            return (res or {}).get("data", {}).get("data", {}).get(key)
        except Exception as exc:
            logger.warning("vault.read_failed", path=path, error=str(exc))
            return None

    def put(self, path: str, key: str, value: str) -> None:
        try:
            existing = (
                self._client.secrets.kv.v2.read_secret_version(
                    path=path, mount_point=self._mount
                )
                .get("data", {})
                .get("data", {})
            )
        except Exception:
            existing = {}
        existing[key] = value
        self._client.secrets.kv.v2.create_or_update_secret(
            path=path, secret=existing, mount_point=self._mount
        )

    def health(self) -> bool:
        try:
            return bool(self._client.is_authenticated())
        except Exception:
            return False


# ── Infisical backend ───────────────────────────────────────
class InfisicalBackend:
    name = "infisical"

    def __init__(self) -> None:
        try:
            from infisical_client import (
                ClientSettings,
                InfisicalClient,
                AuthenticationOptions,
                UniversalAuthMethod,
                GetSecretOptions,
            )
        except Exception as exc:
            raise RuntimeError(f"infisical_client unavailable: {exc}")
        site_url = os.getenv("INFISICAL_SITE_URL", "http://infisical:8080")
        client_id = os.getenv("INFISICAL_CLIENT_ID", "")
        client_secret = os.getenv("INFISICAL_CLIENT_SECRET", "")
        self._project_id = os.getenv("INFISICAL_PROJECT_ID", "")
        self._env = os.getenv("INFISICAL_ENV", os.getenv("ENVIRONMENT_MODE", "dev"))
        self._client = InfisicalClient(
            ClientSettings(
                auth=AuthenticationOptions(
                    universal_auth=UniversalAuthMethod(
                        client_id=client_id, client_secret=client_secret
                    )
                ),
                site_url=site_url,
            )
        )
        self._GetSecretOptions = GetSecretOptions

    def get(self, path: str, key: str) -> str | None:
        try:
            res = self._client.getSecret(
                self._GetSecretOptions(
                    secret_name=key,
                    project_id=self._project_id,
                    environment=self._env,
                    path="/" + path.strip("/"),
                )
            )
            return res.secret_value
        except Exception as exc:
            logger.warning("infisical.read_failed", path=path, key=key, error=str(exc))
            return None

    def put(self, path: str, key: str, value: str) -> None:
        # Implementation kept thin; UI-driven writes typically go through
        # Infisical's own API or admin scripts. Left as a no-op placeholder.
        raise NotImplementedError("Use Infisical UI/API for writes")

    def health(self) -> bool:
        # The SDK doesn't expose a ping — trust the client init.
        return True


# ── Resolver ────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _backends() -> list[SecretBackend]:
    primary = os.getenv("SECRETS_BACKEND", "env").strip().lower()
    fallback_csv = os.getenv("SECRETS_FALLBACK", "env").strip().lower()
    fallback = [b.strip() for b in fallback_csv.split(",") if b.strip()]

    order: list[str] = []
    for name in [primary] + fallback:
        if name and name not in order:
            order.append(name)

    out: list[SecretBackend] = []
    for name in order:
        try:
            if name == "infisical":
                out.append(InfisicalBackend())
            elif name == "vault":
                out.append(VaultBackend())
            elif name == "env":
                out.append(EnvBackend())
            else:
                logger.warning("secrets.unknown_backend", name=name)
        except Exception as exc:
            logger.warning("secrets.backend_init_failed", name=name, error=str(exc))
    if not out:
        out.append(EnvBackend())
    logger.info("secrets.backends_ready", order=[b.name for b in out])
    return out


def get_secret(provider_name: str, key: str = "api_key") -> str | None:
    """Resolve ``key`` for a known provider name (e.g. 'openai')."""
    return get_secret_at(f"providers/{provider_name}", key)


def get_secret_at(path: str, key: str) -> str | None:
    """Resolve ``key`` at an absolute backend path (e.g. ``llm/openai/abc``)."""
    for backend in _backends():
        try:
            v = backend.get(path, key)
            if v:
                return v
        except Exception as exc:
            logger.warning("secrets.backend_failed",
                           backend=backend.name, path=path, error=str(exc))
    return None


def put_secret_at(path: str, key: str, value: str) -> str:
    """Write ``key=value`` at ``path`` on the primary backend. Returns backend name."""
    backend = _backends()[0]
    backend.put(path, key, value)
    return backend.name


def reset_cache() -> None:
    _backends.cache_clear()
