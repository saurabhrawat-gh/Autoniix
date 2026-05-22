from __future__ import annotations

from datetime import timedelta
from io import BytesIO

import structlog
from minio import Minio

from src.config import settings
from src.environment import get_storage_prefix
from src.providers.registry import ProviderRegistry
from src.providers.storage.base import StorageProvider, StorageResult, StorageUpload

logger = structlog.get_logger()


class MinIOStorage(StorageProvider):

    def __init__(self) -> None:
        # Configurable via chain extra_config:
        #   endpoint, access_key, api_key (= secret_key), bucket, public_base
        self.endpoint: str = settings.s3_endpoint
        self.access_key: str = settings.s3_access_key
        self.api_key: str = settings.s3_secret_key   # vault stores under 'api_key'
        self.bucket: str = settings.s3_bucket
        self.public_base: str = settings.s3_public_base_url
        self.client: Minio | None = None
        self._connect()

    def _connect(self) -> None:
        """(Re-)build the Minio client from current instance attributes.

        Called at init time and by chain._instantiate after extra_config
        attributes are injected, so credentials can be DB-driven.
        """
        endpoint = self.endpoint.replace("http://", "").replace("https://", "")
        secure = self.endpoint.startswith("https")
        self.client = Minio(
            endpoint,
            access_key=self.access_key,
            secret_key=self.api_key,
            secure=secure,
        )
        # Ensure bucket exists
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info("minio.bucket_created", bucket=self.bucket)
        except Exception as exc:
            logger.warning("minio.bucket_check_failed", error=str(exc))

    async def upload(self, upload: StorageUpload) -> StorageResult:
        prefixed_key = self._prefixed_key(upload.key)
        data = BytesIO(upload.data)
        self.client.put_object(
            self.bucket,
            prefixed_key,
            data,
            len(upload.data),
            content_type=upload.content_type,
            metadata=upload.metadata,
        )
        url = (
            f"{self.public_base}/{prefixed_key}"
            if self.public_base
            else f"s3://{self.bucket}/{prefixed_key}"
        )
        logger.info("minio.uploaded", key=prefixed_key, size=len(upload.data))
        return StorageResult(
            url=url, key=prefixed_key, size_bytes=len(upload.data), provider="minio"
        )

    async def download(self, key: str) -> bytes:
        response = self.client.get_object(self.bucket, self._prefixed_key(key))
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    async def exists(self, key: str) -> bool:
        try:
            self.client.stat_object(self.bucket, self._prefixed_key(key))
            return True
        except Exception:
            return False

    async def delete(self, key: str) -> None:
        prefixed = self._prefixed_key(key)
        self.client.remove_object(self.bucket, prefixed)
        logger.info("minio.deleted", key=prefixed)

    async def get_signed_url(self, key: str, expires_in: int = 3600) -> str:
        return self.client.presigned_get_object(
            self.bucket, self._prefixed_key(key), expires=timedelta(seconds=expires_in)
        )

    async def health_check(self) -> bool:
        try:
            self.client.bucket_exists(self.bucket)
            return True
        except Exception:
            return False

    def provider_name(self) -> str:
        return "minio"

    @staticmethod
    def _prefixed_key(key: str) -> str:
        """Prefix key with environment (test/ or prod/) if not already prefixed."""
        prefix = get_storage_prefix()
        if key.startswith(f"{prefix}/") or key.startswith("test/") or key.startswith("prod/"):
            return key
        return f"{prefix}/{key}"

    def delete_prefix(self, prefix: str) -> int:
        """Delete all objects under a prefix. Used for test data cleanup."""
        count = 0
        objects = self.client.list_objects(self.bucket, prefix=prefix, recursive=True)
        from minio.deleteobjects import DeleteObject
        delete_list = [DeleteObject(obj.object_name) for obj in objects]
        if delete_list:
            errors = list(self.client.remove_objects(self.bucket, delete_list))
            count = len(delete_list) - len(errors)
            logger.info("minio.prefix_deleted", prefix=prefix, deleted=count, errors=len(errors))
        return count


ProviderRegistry.register("storage", "minio", MinIOStorage)
