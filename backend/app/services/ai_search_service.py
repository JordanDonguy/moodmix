import json
import logging
import time

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

AI_MODEL = "openai/gpt-oss-120b"

SYSTEM_PROMPT = """You convert natural language music queries into structured search parameters for a background music app.

Given a user query, return a JSON object with:
- "mood": float (-1 to 1) — Dark/night (-1) to Bright/day (+1). null if not inferable.
- "energy": float (-1 to 1) — Chill (-1) to Dynamic (+1). null if not inferable.
- "instrumentation": float (-1 to 1) — Organic/acoustic (-1) to Electronic (+1). null if not inferable.
- "genres": list of genre slugs. ONLY include if the user explicitly mentions a genre or instrument. Empty list otherwise.
- "instrumental": boolean — true if the user wants instrumental only, false otherwise. Default false.

Allowed genres (use ONLY when user mentions one): lo-fi, hip-hop, synthwave, chill-electronic, deep-house, drum-and-bass, neo-soul-r-and-b, jazz, ambient, acoustic-and-piano

IMPORTANT: Most queries describe a mood or vibe, not a genre. Use the slider values (mood, energy, instrumentation) to capture the vibe. Only set genres when the user explicitly names one (e.g., "jazz", "lo-fi", "piano", "drum and bass").

Examples:
- "rainy day coffee shop vibes" → {"mood": 0.3, "energy": -0.5, "instrumentation": -0.4, "genres": [], "instrumental": false}
- "dark electronic for late night coding" → {"mood": -0.7, "energy": -0.3, "instrumentation": 0.7, "genres": [], "instrumental": true}
- "something with jazz" → {"mood": 0.1, "energy": -0.3, "instrumentation": -0.5, "genres": ["jazz"], "instrumental": false}
- "chill piano music" → {"mood": 0.2, "energy": -0.6, "instrumentation": -0.8, "genres": ["acoustic-and-piano"], "instrumental": true}
- "electronic music for sunset" → {"mood": -0.3, "energy": -0.2, "instrumentation": 0.7, "genres": [], "instrumental": false}
- "upbeat lo-fi hip hop" → {"mood": 0.2, "energy": 0.3, "instrumentation": 0.1, "genres": ["lo-fi", "hip-hop"], "instrumental": false}

Respond ONLY with the JSON object, no markdown, no explanation."""


class AiSearchService:
    """Converts natural language queries into search parameters using an LLM."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=15)
        self._api_key = settings.LLM_API_KEY
        self._api_url = settings.LLM_API_URL

    async def parse_query(self, query: str) -> dict[str, object]:
        """Send a natural language query to the LLM and parse the response into search params."""
        content = ""
        for attempt in range(2):
            start = time.monotonic()
            response = await self._client.post(
                self._api_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": AI_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": query},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 500,
                },
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)

            logger.info(
                "AI search [attempt %d]: query='%s' | %dms | %d+%d tokens | response='%s'",
                attempt + 1, query[:50], elapsed_ms,
                prompt_tokens, completion_tokens, content[:100],
            )

            if content:
                break
            logger.warning("Empty LLM response for query '%s', retrying...", query)

        # Parse JSON from response (handle potential markdown wrapping)
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        # Find JSON object in response (LLM may add text around it)
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start == -1 or json_end == 0:
            logger.warning("No JSON found in LLM response: %s", content[:200])
            return {"mood": None, "energy": None, "instrumentation": None, "genres": [], "instrumental": False}

        result: dict[str, object] = json.loads(content[json_start:json_end])

        # Validate and clamp values
        for key in ("mood", "energy", "instrumentation"):
            val = result.get(key)
            if val is not None and isinstance(val, (int, float)):
                result[key] = max(-1.0, min(1.0, float(val)))
            else:
                result[key] = None

        if "genres" not in result or not isinstance(result["genres"], list):
            result["genres"] = []

        if "instrumental" not in result:
            result["instrumental"] = False

        return result

    async def close(self) -> None:
        await self._client.aclose()
