"""Pytest configuration for contract tests."""
import pytest


@pytest.fixture(scope="session")
def rust_base_url():
    """Rust gateway base URL."""
    return "http://localhost:8080"


@pytest.fixture(scope="session")
def python_base_url():
    """Python dashboard base URL."""
    return "http://localhost:8000"
