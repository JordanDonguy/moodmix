# pyright: reportPrivateUsage=false
"""Unit tests for AiSearchService.parse_query.

The HTTP client is injected via constructor and replaced with httpx.MockTransport
so we test the real parsing/clamping/retry logic without hitting an LLM.
"""

import json
from collections.abc import Callable

import httpx

from app.services.ai_search_service import AiSearchService

LLMHandler = Callable[[httpx.Request], httpx.Response]


def make_llm_response(content: str) -> dict[str, object]:
    """Build a fake OpenRouter-shaped LLM response with the given content string."""
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


def make_mock_client(handler: LLMHandler) -> httpx.AsyncClient:
    """Build an httpx AsyncClient that returns whatever the handler produces."""
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class TestParseQuery:
    async def test_valid_json_response(self):
        # ARRANGE
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=make_llm_response(
                '{"mood": 0.5, "energy": -0.3, "instrumentation": 0.7, '
                '"genres": ["jazz"], "instrumental": true}'
            ))

        service = AiSearchService(client=make_mock_client(handler))

        # ACT
        result = await service.parse_query("happy jazz vibes")

        # ASSERT
        assert result == {
            "mood": 0.5,
            "energy": -0.3,
            "instrumentation": 0.7,
            "genres": ["jazz"],
            "instrumental": True,
        }

    async def test_markdown_wrapped_json(self):
        """LLM sometimes wraps JSON in ```json ... ``` — service must unwrap it."""
        # ARRANGE
        wrapped = '```json\n{"mood": 0.2, "energy": 0.0, "instrumentation": -0.5, "genres": [], "instrumental": false}\n```'

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=make_llm_response(wrapped))

        service = AiSearchService(client=make_mock_client(handler))

        # ACT
        result = await service.parse_query("chill stuff")

        # ASSERT
        assert result["mood"] == 0.2
        assert result["energy"] == 0.0
        assert result["instrumentation"] == -0.5

    async def test_out_of_range_values_clamped(self):
        """Mood/energy/instrumentation must be clamped to [-1, 1]."""
        # ARRANGE
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=make_llm_response(
                '{"mood": 1.5, "energy": -2.0, "instrumentation": 0.3, "genres": [], "instrumental": false}'
            ))

        service = AiSearchService(client=make_mock_client(handler))

        # ACT
        result = await service.parse_query("test")

        # ASSERT
        assert result["mood"] == 1.0
        assert result["energy"] == -1.0
        assert result["instrumentation"] == 0.3

    async def test_missing_optional_fields_default(self):
        """Missing genres/instrumental fall back to safe defaults."""
        # ARRANGE
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=make_llm_response(
                '{"mood": 0.5, "energy": 0.5, "instrumentation": 0.5}'
            ))

        service = AiSearchService(client=make_mock_client(handler))

        # ACT
        result = await service.parse_query("test")

        # ASSERT
        assert result["genres"] == []
        assert result["instrumental"] is False

    async def test_non_numeric_slider_values_become_none(self):
        """If LLM returns a string or null for a slider, it should become None."""
        # ARRANGE
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=make_llm_response(
                '{"mood": "happy", "energy": null, "instrumentation": 0.5, "genres": [], "instrumental": false}'
            ))

        service = AiSearchService(client=make_mock_client(handler))

        # ACT
        result = await service.parse_query("test")

        # ASSERT
        assert result["mood"] is None
        assert result["energy"] is None
        assert result["instrumentation"] == 0.5

    async def test_invalid_json_returns_fallback(self):
        """If the LLM response contains no JSON object, return a safe empty payload."""
        # ARRANGE
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=make_llm_response("I don't know what you want"))

        service = AiSearchService(client=make_mock_client(handler))

        # ACT
        result = await service.parse_query("gibberish")

        # ASSERT
        assert result == {
            "mood": None,
            "energy": None,
            "instrumentation": None,
            "genres": [],
            "instrumental": False,
        }

    async def test_empty_response_triggers_retry(self):
        """An empty content string on attempt 1 should trigger a second attempt."""
        # ARRANGE
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(200, json=make_llm_response(""))
            return httpx.Response(200, json=make_llm_response(
                '{"mood": 0.5, "energy": 0.0, "instrumentation": 0.0, "genres": [], "instrumental": false}'
            ))

        service = AiSearchService(client=make_mock_client(handler))

        # ACT
        result = await service.parse_query("test")

        # ASSERT
        assert call_count == 2
        assert result["mood"] == 0.5

    async def test_request_payload_includes_query(self):
        """The user query must reach the LLM as the user message."""
        # ARRANGE
        captured_messages: list[dict[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            captured_messages.extend(body["messages"])
            return httpx.Response(200, json=make_llm_response(
                '{"mood": 0.0, "energy": 0.0, "instrumentation": 0.0, "genres": [], "instrumental": false}'
            ))

        service = AiSearchService(client=make_mock_client(handler))

        # ACT
        await service.parse_query("rainy day jazz")

        # ASSERT
        user_msg = next(m for m in captured_messages if m["role"] == "user")
        assert user_msg["content"] == "rainy day jazz"
