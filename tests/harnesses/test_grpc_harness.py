"""Tests for gRPC and HTTP service harnesses."""
import pytest

from .grpc_harness import GRPCServiceHarness, MockLLMServicer


@pytest.mark.asyncio
async def test_grpc_harness_starts_and_stops():
    async with GRPCServiceHarness("test_service") as h:
        assert h.bound_port > 0
        assert h.channel is not None


@pytest.mark.asyncio
async def test_grpc_harness_context_manager():
    """Harness cleans up properly on exit."""
    harness = GRPCServiceHarness("cleanup_test")
    async with harness as h:
        port = h.bound_port


def test_mock_llm_servicer_default_response():
    m = MockLLMServicer()
    resp = m._get_response("some random prompt")
    assert "mock_response" in resp
    assert m.call_count == 1


def test_mock_llm_servicer_keyword_routing():
    m = MockLLMServicer()
    resp = m._get_response("please do research on AI")
    assert "selected_topic" in resp


def test_mock_llm_servicer_call_count():
    m = MockLLMServicer()
    m._get_response("a")
    m._get_response("b")
    m._get_response("c")
    assert m.call_count == 3


def test_mock_llm_servicer_custom_response():
    m = MockLLMServicer()
    m.set_response("quantum", '{"quantum": true}')
    resp = m._get_response("explain quantum computing")
    assert resp == '{"quantum": true}'


def test_mock_llm_servicer_reset():
    m = MockLLMServicer()
    m._get_response("x")
    m._get_response("y")
    m.reset()
    assert m.call_count == 0
