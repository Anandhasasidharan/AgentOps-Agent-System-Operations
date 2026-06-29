"""Tests for fault injection targets."""

import pytest

from chaos_toolkit.targets.llm import (
    FAILURE_MODES as LLM_MODES,
    _simulate_hallucination,
    _simulate_model_downgrade,
    _simulate_refusal,
    inject_llm_fault,
)
from chaos_toolkit.targets.tools import (
    FAILURE_MODES as TOOL_MODES,
    _simulate_bad_output,
    _simulate_tool_crash,
    _simulate_wrong_data,
    inject_tool_fault,
)
from chaos_toolkit.targets.rag import (
    FAILURE_MODES as RAG_MODES,
    _simulate_bad_data,
    _simulate_corrupted_context,
    _simulate_no_results,
    inject_rag_fault,
)
from chaos_toolkit.targets.mcp import (
    FAILURE_MODES as MCP_MODES,
    _simulate_auth_failure,
    _simulate_bad_capabilities,
    _simulate_server_down,
    inject_mcp_fault,
)


class TestLLMTarget:
    def test_modes_defined(self):
        assert "timeout" in LLM_MODES
        assert "hallucination" in LLM_MODES
        assert "model_downgrade" in LLM_MODES
        assert "refusal" in LLM_MODES

    @pytest.mark.asyncio
    async def test_timeout(self):
        result = await inject_llm_fault(
            {"failure_mode": "timeout", "params": {"delay_seconds": 0.001}}
        )
        assert result["fault_injected"]
        assert result["failure_mode"] == "timeout"

    @pytest.mark.asyncio
    async def test_hallucination(self):
        result = await inject_llm_fault({"failure_mode": "hallucination", "params": {}})
        assert result["fault_injected"]
        assert "hallucinated_content" in result

    @pytest.mark.asyncio
    async def test_model_downgrade(self):
        result = await inject_llm_fault(
            {"failure_mode": "model_downgrade", "params": {"downgraded_model": "gpt-3.5-turbo"}}
        )
        assert result["downgraded_model"] == "gpt-3.5-turbo"

    @pytest.mark.asyncio
    async def test_refusal(self):
        result = await inject_llm_fault({"failure_mode": "refusal", "params": {}})
        assert "refusal_message" in result


class TestToolTarget:
    def test_modes_defined(self):
        assert "timeout" in TOOL_MODES
        assert "crash" in TOOL_MODES
        assert "bad_output" in TOOL_MODES
        assert "wrong_data" in TOOL_MODES

    @pytest.mark.asyncio
    async def test_timeout(self):
        result = await inject_tool_fault(
            {"failure_mode": "timeout", "params": {"delay_seconds": 0.001}}
        )
        assert result["failure_mode"] == "timeout"

    @pytest.mark.asyncio
    async def test_crash(self):
        result = await inject_tool_fault({"failure_mode": "crash", "params": {}})
        assert result["failure_mode"] == "crash"
        assert result["status_code"] == 500

    @pytest.mark.asyncio
    async def test_bad_output(self):
        result = await inject_tool_fault({"failure_mode": "bad_output", "params": {}})
        assert result["failure_mode"] == "bad_output"

    @pytest.mark.asyncio
    async def test_wrong_data(self):
        result = await inject_tool_fault({"failure_mode": "wrong_data", "params": {}})
        assert result["failure_mode"] == "wrong_data"


class TestRAGTarget:
    def test_modes_defined(self):
        assert "no_results" in RAG_MODES
        assert "bad_data" in RAG_MODES
        assert "corrupted_context" in RAG_MODES
        assert "slow_response" in RAG_MODES

    @pytest.mark.asyncio
    async def test_no_results(self):
        result = await inject_rag_fault({"failure_mode": "no_results", "params": {}})
        assert result["retrieved_chunks"] == []

    @pytest.mark.asyncio
    async def test_bad_data(self):
        result = await inject_rag_fault({"failure_mode": "bad_data", "params": {}})
        assert len(result["retrieved_chunks"]) == 1

    @pytest.mark.asyncio
    async def test_corrupted_context(self):
        result = await inject_rag_fault({"failure_mode": "corrupted_context", "params": {}})
        assert "corrupted" in result["retrieved_chunks"][0]["id"]

    @pytest.mark.asyncio
    async def test_slow_response(self):
        result = await inject_rag_fault(
            {"failure_mode": "slow_response", "params": {"delay_seconds": 0.001}}
        )
        assert "response_time_s" in result


class TestMCPTarget:
    def test_modes_defined(self):
        assert "server_down" in MCP_MODES
        assert "timeout" in MCP_MODES
        assert "bad_capabilities" in MCP_MODES
        assert "auth_failure" in MCP_MODES

    @pytest.mark.asyncio
    async def test_server_down(self):
        result = await inject_mcp_fault({"failure_mode": "server_down", "params": {}})
        assert result["status_code"] == 502

    @pytest.mark.asyncio
    async def test_bad_capabilities(self):
        result = await inject_mcp_fault({"failure_mode": "bad_capabilities", "params": {}})
        assert "claimed_capabilities" in result

    @pytest.mark.asyncio
    async def test_auth_failure(self):
        result = await inject_mcp_fault({"failure_mode": "auth_failure", "params": {}})
        assert result["status_code"] == 401
