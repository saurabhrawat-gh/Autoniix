"""Tests for the test vs production environment system."""
from __future__ import annotations

import pytest

from src.environment import (
    get_mode,
    is_test,
    is_production,
    require_production,
    get_storage_prefix,
    get_content_id_prefix,
    set_db_mode_override,
    clear_db_mode_override,
    EnvironmentModeError,
)


# get_mode / is_test / is_production


class TestEnvironmentHelpers:

    def setup_method(self):
        clear_db_mode_override()

    def teardown_method(self):
        clear_db_mode_override()

    def test_default_mode_is_test(self):
        assert get_mode() == "test"
        assert is_test() is True
        assert is_production() is False

    def test_db_override_production(self):
        set_db_mode_override("production")
        assert get_mode() == "production"
        assert is_test() is False
        assert is_production() is True

    def test_db_override_test(self):
        set_db_mode_override("test")
        assert get_mode() == "test"
        assert is_test() is True

    def test_clear_override(self):
        set_db_mode_override("production")
        assert is_production() is True
        clear_db_mode_override()
        assert is_test() is True


# require_production


class TestRequireProduction:

    def setup_method(self):
        clear_db_mode_override()

    def teardown_method(self):
        clear_db_mode_override()

    def test_raises_in_test_mode(self):
        with pytest.raises(EnvironmentModeError, match="requires production"):
            require_production("youtube_upload")

    def test_passes_in_production(self):
        set_db_mode_override("production")
        require_production("youtube_upload")  # Should not raise


# Storage prefix


class TestStoragePrefix:

    def setup_method(self):
        clear_db_mode_override()

    def teardown_method(self):
        clear_db_mode_override()

    def test_test_prefix(self):
        assert get_storage_prefix() == "test"

    def test_production_prefix(self):
        set_db_mode_override("production")
        assert get_storage_prefix() == "prod"


# Content ID prefix


class TestContentIdPrefix:

    def setup_method(self):
        clear_db_mode_override()

    def teardown_method(self):
        clear_db_mode_override()

    def test_test_content_id(self):
        assert get_content_id_prefix() == "TEST_VID"

    def test_production_content_id(self):
        set_db_mode_override("production")
        assert get_content_id_prefix() == "VID"


# Provider remapping


class TestProviderRemapping:

    def setup_method(self):
        clear_db_mode_override()

    def teardown_method(self):
        clear_db_mode_override()

    def test_test_mode_maps_known_categories(self):
        from src.providers.registry import _TEST_PROVIDER_MAP
        assert _TEST_PROVIDER_MAP["tts"] == "edge_tts"
        assert _TEST_PROVIDER_MAP["llm"] == "mock_llm"
        assert _TEST_PROVIDER_MAP["search"] == "mock_search"
        assert _TEST_PROVIDER_MAP["image"] == "placeholder"

    def test_storage_not_remapped(self):
        from src.providers.registry import _TEST_PROVIDER_MAP
        assert "storage" not in _TEST_PROVIDER_MAP


# MinIO key prefixing


try:
    import minio  # noqa: F401
    _has_minio = True
except ImportError:
    _has_minio = False


@pytest.mark.skipif(not _has_minio, reason="minio package not installed (Docker-only)")
class TestMinIOPrefixing:

    def setup_method(self):
        clear_db_mode_override()

    def teardown_method(self):
        clear_db_mode_override()

    def test_prefixes_key_in_test(self):
        from src.providers.storage.minio_provider import MinIOStorage
        assert MinIOStorage._prefixed_key("audio/test.mp3") == "test/audio/test.mp3"

    def test_prefixes_key_in_production(self):
        from src.providers.storage.minio_provider import MinIOStorage
        set_db_mode_override("production")
        assert MinIOStorage._prefixed_key("audio/test.mp3") == "prod/audio/test.mp3"

    def test_does_not_double_prefix(self):
        from src.providers.storage.minio_provider import MinIOStorage
        assert MinIOStorage._prefixed_key("test/audio/test.mp3") == "test/audio/test.mp3"
        set_db_mode_override("production")
        assert MinIOStorage._prefixed_key("prod/audio/test.mp3") == "prod/audio/test.mp3"
