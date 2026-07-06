from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class StorageUpload:
    key: str
    data: bytes
    content_type: str = "application/octet-stream"
    metadata: dict | None = None


@dataclass
class StorageResult:
    url: str = ""
    key: str = ""
    size_bytes: int = 0
    provider: str = ""


class StorageProvider(ABC):
    """Abstract base for all object storage providers."""

    @abstractmethod
    async def upload(self, upload: StorageUpload) -> StorageResult: ...

    @abstractmethod
    async def download(self, key: str) -> bytes: ...

    @abstractmethod
    async def exists(self, key: str) -> bool: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    async def get_signed_url(self, key: str, expires_in: int = 3600) -> str: ...

    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    def provider_name(self) -> str: ...
