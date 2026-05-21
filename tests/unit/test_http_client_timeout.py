from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from engine.operators.http_client import HTTPAPIClient


@pytest.mark.asyncio
async def test_initialize_client_uses_timeout_from_env(monkeypatch):
    monkeypatch.setenv("SARVAM_HTTP_TIMEOUT", "45")
    client = HTTPAPIClient(
        sarvam_base_url="https://api.example.com/v1",
        sarvam_api_key="key",
        logger=AsyncMock(),
    )
    with patch("engine.operators.http_client.AsyncOpenAI") as mock_openai:
        await client.initialize_client()
        mock_openai.assert_called_once()
        kwargs = mock_openai.call_args.kwargs
        assert kwargs["timeout"] == 45.0


@pytest.mark.asyncio
async def test_usage_accumulates_on_send(monkeypatch):
    client = HTTPAPIClient(
        sarvam_base_url="https://api.example.com/v1",
        sarvam_api_key="key",
        logger=AsyncMock(),
    )
    client.reset_usage_totals()

    mock_message = MagicMock()
    mock_message.content = '{"summary": "ok"}'
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 10
    mock_usage.completion_tokens = 5
    mock_usage.total_tokens = 15
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage

    mock_completions = MagicMock()
    mock_completions.create = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.chat.completions = mock_completions
    client._sarvam_client = mock_client

    from engine.models.http_client_models import SarvamAPIRequest, SarvamMessages

    req = SarvamAPIRequest(
        model="sarvam-m",
        messages=[SarvamMessages(role="user", content="hi")],
        max_tokens=100,
    )
    result = await client.send_request_to_sarvam(req)
    assert "summary" in result.content
    totals = client.get_usage_totals()
    assert totals.prompt_tokens == 10
    assert totals.total_tokens == 15
