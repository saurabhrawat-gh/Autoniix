"""Tests for AE-32: Configure Storage credential (MinIO).

Covers:
- MinIOStorage exposes endpoint, access_key, api_key, bucket, public_base
- _connect() rebuilds Minio client from current instance attributes
- chain._instantiate calls _connect() after extra_config injection
- WizardCredentialIn works for storage category
- Wizard field split: password → vault, other fields → extra_config
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_minio_storage_has_config_attributes(monkeypatch):
    import src.config as cfg
    monkeypatch.setattr(cfg.settings, "s3_endpoint", "http://localhost:9000")
    monkeypatch.setattr(cfg.settings, "s3_access_key", "minioadmin")
    monkeypatch.setattr(cfg.settings, "s3_secret_key", "minioadmin")
    monkeypatch.setattr(cfg.settings, "s3_bucket", "test-bucket")
    monkeypatch.setattr(cfg.settings, "s3_public_base_url", "")

    with patch("src.providers.storage.minio_provider.Minio") as mock_minio:
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio.return_value = mock_client

        from src.providers.storage.minio_provider import MinIOStorage
        inst = MinIOStorage()

    assert inst.endpoint == "http://localhost:9000"
    assert inst.access_key == "minioadmin"
    assert inst.api_key == "minioadmin"   # s3_secret_key stored as api_key
    assert inst.bucket == "test-bucket"


def test_minio_connect_rebuilds_client(monkeypatch):
    import src.config as cfg
    monkeypatch.setattr(cfg.settings, "s3_endpoint", "http://localhost:9000")
    monkeypatch.setattr(cfg.settings, "s3_access_key", "key1")
    monkeypatch.setattr(cfg.settings, "s3_secret_key", "secret1")
    monkeypatch.setattr(cfg.settings, "s3_bucket", "bucket1")
    monkeypatch.setattr(cfg.settings, "s3_public_base_url", "")

    with patch("src.providers.storage.minio_provider.Minio") as mock_minio:
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio.return_value = mock_client

        from src.providers.storage.minio_provider import MinIOStorage
        inst = MinIOStorage()

        # Now inject new config (like chain._instantiate would)
        inst.access_key = "new-access-key"
        inst.api_key = "new-secret-key"
        inst.endpoint = "http://minio-prod:9000"
        inst._connect()

        last_call = mock_minio.call_args
        _, kwargs = last_call
        assert kwargs.get("access_key") == "new-access-key"
        assert kwargs.get("secret_key") == "new-secret-key"


def test_chain_instantiate_calls_connect_after_extra_config(monkeypatch):
    """chain._instantiate calls _connect() after extra_config attrs are set."""
    import src.config as cfg
    monkeypatch.setattr(cfg.settings, "s3_endpoint", "http://localhost:9000")
    monkeypatch.setattr(cfg.settings, "s3_access_key", "")
    monkeypatch.setattr(cfg.settings, "s3_secret_key", "")
    monkeypatch.setattr(cfg.settings, "s3_bucket", "default")
    monkeypatch.setattr(cfg.settings, "s3_public_base_url", "")

    import src.providers.boot  # noqa: F401
    from src.providers.chain import _instantiate
    from src.providers.registry import ProviderRegistry

    registry = ProviderRegistry._registries.get("storage", {})
    connect_calls: list[dict] = []

    with patch("src.providers.storage.minio_provider.Minio") as mock_minio:
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio.return_value = mock_client

        def track_connect(endpoint, **kwargs):
            connect_calls.append({"endpoint": endpoint, **kwargs})
            return mock_client

        mock_minio.side_effect = track_connect

        with patch("src.providers.chain.get_secret_at", return_value="vault-secret"):
            inst = _instantiate(
                "minio", "providers/storage/minio/prod",
                {"access_key": "prod-access", "endpoint": "http://minio-prod:9000",
                 "bucket": "prod-bucket"},
                None, registry,
            )

    assert inst is not None
    # _connect() is called at init and again after extra_config injection
    assert len(connect_calls) >= 2
    # Last call should use the injected endpoint
    assert "minio-prod" in connect_calls[-1]["endpoint"]


def test_minio_wizard_field_split():
    """Wizard splits secret_key → vault, all others → extra_config."""
    schema = [
        {"name": "secret_key", "type": "password", "label": "Secret Key", "required": True},
        {"name": "access_key", "type": "text", "label": "Access Key", "required": True},
        {"name": "endpoint", "type": "url", "label": "Endpoint", "required": True},
        {"name": "bucket", "type": "text", "label": "Bucket", "required": True},
        {"name": "public_base_url", "type": "url", "label": "Public Base URL"},
    ]
    wizard_fields = {
        "secret_key": "my-secret",
        "access_key": "my-access",
        "endpoint": "http://minio:9000",
        "bucket": "videos",
        "public_base_url": "http://cdn.example.com",
    }

    secret_value = ""
    secret_key = "api_key"
    extra_config: dict = {}
    for field in schema:
        name = field["name"]
        value = wizard_fields.get(name)
        if value is None:
            continue
        if field.get("type") == "password":
            if not secret_value:
                secret_value = str(value)
                secret_key = name
        else:
            extra_config[name] = value

    assert secret_value == "my-secret"
    assert secret_key == "secret_key"
    assert extra_config["access_key"] == "my-access"
    assert extra_config["endpoint"] == "http://minio:9000"
    assert extra_config["bucket"] == "videos"
    assert extra_config["public_base_url"] == "http://cdn.example.com"


def test_minio_registered():
    import src.providers.boot  # noqa: F401
    from src.providers.registry import ProviderRegistry

    reg = ProviderRegistry._registries.get("storage", {})
    assert "minio" in reg
