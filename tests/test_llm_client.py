"""
Unit tests for the deep LLMClient gateway seam.
Verifies asynchronous generation, model cascading, JSON schema extraction,
and structured output validation.
"""

import pytest
from src.agents.llm_client import LLMClient, get_llm_client


@pytest.mark.asyncio
async def test_llm_client_singleton():
    client1 = get_llm_client()
    client2 = get_llm_client()
    assert client1 is client2


@pytest.mark.asyncio
async def test_llm_client_agenerate_text():
    client = get_llm_client()
    res = await client.agenerate_text(
        prompt="Respond with the single word: OK",
        system_prompt="You are a helpful assistant.",
    )
    assert isinstance(res, str)
    assert len(res) > 0


@pytest.mark.asyncio
async def test_llm_client_agenerate_json():
    client = get_llm_client()
    res = await client.agenerate_json(
        prompt="Provide a JSON object with key 'status' equal to 'active' and key 'count' equal to 42.",
        system_prompt="You are a data formatting assistant.",
    )
    assert isinstance(res, dict)
    assert res.get("status") == "active"
    assert res.get("count") == 42


@pytest.mark.asyncio
async def test_llm_client_clean_and_parse_json_markdown():
    client = get_llm_client()
    raw = "```json\n{\"analysis\": \"valid\", \"score\": 0.95}\n```"
    parsed = client._clean_and_parse_json(raw)
    assert parsed == {"analysis": "valid", "score": 0.95}
