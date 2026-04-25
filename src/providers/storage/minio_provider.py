from __future__ import annotations

from datetime import timedelta
from io import BytesIO

import structlog
from minio import Minio

from src.config import settings
from src.providers.registry import ProviderRegistry
from src.providers.storage.base import StorageProvider, StorageResult, StorageUpload

logger = structlog.get_logger()


class MinIOStorage(StorageProvider):

    def __init__(self) -> None:
        endpoint = settings.s3_endpoint.replace("http://", "").replace("https://", "")
        secure = settings.s3_endpoint.startswith("https")
        self.client = Minio(
            endpoint,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            secure=secure,
        )
        self.bucket = settings.s3_bucket
        self.public_base = settings.s3_public_base_url

        # Ensure bucket exists
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info("minio.bucket_created", bucket=self.bucket)
        except Exception as exc:
            logger.warning("minio.bucket_check_failed", error=str(exc))

    async def upload(self, upload: StorageUpload) -> StorageResult:
        data = BytesIO(upload.data)
        self.client.put_object(
            self.bucket,
            upload.key,
            data,
            len(upload.data),
            content_type=upload.content_type,
            metadata=upload.metadata,
        )
        url = (
            f"{self.public_base}/{upload.key}"
            if self.public_base
            else f"s3://{self.bucket}/{upload.key}"
        )
        logger.info("minio.uploaded", key=upload.key, size=len(upload.data))
        return StorageResult(
            url=url, key=upload.key, size_bytes=len(upload.data), provider="minio"
        )

    async def download(self, key: str) -> bytes:
        response = self.client.get_object(self.bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    async def exists(self, key: str) -> bool:
        try:
            self.client.stat_object(self.bucket, key)
            return True
        except Exception:
            return False

    async def delete(self, key: str) -> None:
        self.client.remove_object(self.bucket, key)
        logger.info("minio.deleted", key=key)

    async def get_signed_url(self, key: str, expires_in: int = 3600) -> str:
        return self.client.presigned_get_object(
            self.bucket, key, expires=timedelta(seconds=expires_in)
        )

    async def health_check(self) -> bool:
        try:
            self.client.bucket_exists(self.bucket)
            return True
        except Exception:
            return False

    def provider_name(self) -> str:
        return "minio"


ProviderRegistry.register("storage", "minio", MinIOStorage)
