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
        raise NotImplementedError("EnvBackend is read-only")

    def health(self) -> bool:
        return True


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
            res = self._client.secrets.kv.v2.read_secret_version(path=path, mount_point=self._mount)
            return (res or {}).get("data", {}).get("data", {}).get(key)
        except Exception as exc:
            logger.warning("vault.read_failed", path=path, error=str(exc))
            return None

    def put(self, path: str, key: str, value: str) -> None:
        try:
            existing = (
                self._client.secrets.kv.v2.read_secret_version(path=path, mount_point=self._mount)
                .get("data", {})
                .get("data", {})
            )
        except Exception:
            existing = {}
        existing[key] = value
        self._client.secrets.kv.v2.create_or_update_secret(path=path, secret=existing, mount_point=self._mount)

    def health(self) -> bool:
        try:
            return bool(self._client.is_authenticated())
        except Exception:
            return False


class DBBackend:
    """Self-hosted secret store: AES-GCM/Fernet ciphertext in postgres.

    Designed for the zero-external-dep dev/prod path: no Vault, no
    Infisical, just a master key in ``SECRETS_ENCRYPTION_KEY`` and a
    ``provider_secrets`` table created by migration 202605140003.

    If the env var is missing, we generate an ephemeral key and log a
    loud warning — secrets written this way survive only until the
    process restarts. Set the env var in ``.env`` for persistence.
    """

    name = "db"

    _cipher = None  # type: ignore[var-annotated]
    _bootstrapped = False

    def __init__(self) -> None:
        from cryptography.fernet import Fernet  # type: ignore[import-not-found]

        key = os.getenv("SECRETS_ENCRYPTION_KEY", "").strip()
        if not key:
            key = Fernet.generate_key().decode()
            logger.warning(
                "secrets.db.ephemeral_key",
                msg=(
                    "SECRETS_ENCRYPTION_KEY not set — generated an "
                    "ephemeral key. Secrets written now will be "
                    "unreadable after a restart. Add to .env:"
                ),
                example_key=key,
            )
        try:
            self._cipher = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception as exc:
            raise RuntimeError(
                f"SECRETS_ENCRYPTION_KEY is not a valid Fernet key: {exc}. "
                f"Generate one with: python -c "
                f"'from cryptography.fernet import Fernet; "
                f"print(Fernet.generate_key().decode())'"
            ) from exc

    def _run(self, coro):
        """Bridge async DB calls to the sync Protocol surface.

        We can't reuse the shared asyncpg pool (which is bound to the
        main event loop) from another thread/loop — asyncpg pools are
        not thread-safe and raise "another operation is in progress".
        So we always open a fresh short-lived connection in a private
        thread's event loop and close it at the end of the call.
        """
        import asyncio
        import concurrent.futures

        def _runner():
            return asyncio.run(coro)

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return _runner()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(_runner).result()

    @staticmethod
    async def _connect():
        import asyncpg

        from core.config import settings

        return await asyncpg.connect(
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
        )

    async def _fetch(self, path: str, key: str) -> str | None:
        conn = await self._connect()
        try:
            return await conn.fetchval(
                "SELECT ciphertext FROM provider_secrets WHERE path=$1 AND key=$2",
                path,
                key,
            )
        finally:
            await conn.close()

    async def _store(self, path: str, key: str, ciphertext: str) -> None:
        conn = await self._connect()
        try:
            await conn.execute(
                """INSERT INTO provider_secrets (path, key, ciphertext)
                     VALUES ($1, $2, $3)
                   ON CONFLICT (path, key) DO UPDATE
                     SET ciphertext = EXCLUDED.ciphertext,
                         updated_at = NOW()""",
                path,
                key,
                ciphertext,
            )
        finally:
            await conn.close()

    async def _delete_prefix(self, prefix: str) -> int:
        conn = await self._connect()
        try:
            row = await conn.fetchval(
                "WITH deleted AS ("
                "  DELETE FROM provider_secrets WHERE path LIKE $1 RETURNING 1"
                ") SELECT COUNT(*) FROM deleted",
                prefix.rstrip("%") + "%",
            )
            return int(row or 0)
        finally:
            await conn.close()

    def get(self, path: str, key: str) -> str | None:
        try:
            ct = self._run(self._fetch(path, key))
            if not ct:
                return None
            return self._cipher.decrypt(ct.encode()).decode()  # type: ignore[union-attr]
        except Exception as exc:
            logger.warning("secrets.db.get_failed", path=path, error=str(exc))
            return None

    def put(self, path: str, key: str, value: str) -> None:
        ciphertext = self._cipher.encrypt(value.encode()).decode()  # type: ignore[union-attr]
        self._run(self._store(path, key, ciphertext))

    def delete_prefix(self, prefix: str) -> int:
        return self._run(self._delete_prefix(prefix))

    def health(self) -> bool:
        try:
            self._run(self._fetch("__healthcheck__", "ping"))
            return True
        except Exception:
            return False


class InfisicalBackend:
    name = "infisical"

    def __init__(self) -> None:
        try:
            from infisical_client import (
                AuthenticationOptions,
                ClientSettings,
                GetSecretOptions,
                InfisicalClient,
                UniversalAuthMethod,
            )
        except Exception as exc:
            raise RuntimeError(f"infisical_client unavailable: {exc}")
        site_url = os.getenv("INFISICAL_SITE_URL", "http://infisical:8080")
        client_id = os.getenv("INFISICAL_CLIENT_ID", "")
        client_secret = os.getenv("INFISICAL_CLIENT_SECRET", "")
        self._project_id = os.getenv("INFISICAL_PROJECT_ID", "")
        self._env = os.getenv("INFISICAL_ENV", "prod")
        self._client = InfisicalClient(
            ClientSettings(
                auth=AuthenticationOptions(
                    universal_auth=UniversalAuthMethod(client_id=client_id, client_secret=client_secret)
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
        raise NotImplementedError("Use Infisical UI/API for writes")

    def health(self) -> bool:
        return True


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
            elif name == "db":
                out.append(DBBackend())
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
            logger.warning("secrets.backend_failed", backend=backend.name, path=path, error=str(exc))
    return None


def put_secret_at(path: str, key: str, value: str) -> str:
    """Write ``key=value`` at ``path`` on the primary backend. Returns backend name."""
    backend = _backends()[0]
    backend.put(path, key, value)
    return backend.name


def delete_prefix(prefix: str) -> int:
    """Delete every secret whose path starts with ``prefix`` on every
    backend that supports it. Returns the total count deleted.

    Used by the provider clean-slate flow to wipe vault entries when
    the user resets the dashboard. Backends without a ``delete_prefix``
    method (env, vault, infisical) are skipped.
    """
    total = 0
    for backend in _backends():
        fn = getattr(backend, "delete_prefix", None)
        if not callable(fn):
            continue
        try:
            total += int(fn(prefix) or 0)
        except Exception as exc:
            logger.warning("secrets.delete_prefix_failed", backend=backend.name, prefix=prefix, error=str(exc))
    return total


def reset_cache() -> None:
    _backends.cache_clear()
