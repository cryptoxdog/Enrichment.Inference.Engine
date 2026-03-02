"""
Async Perplexity Sonar client.

Audit fixes applied:
  - M12: Strips markdown code fences before json.loads()
  - M13: Catches specific exceptions, not bare except
  - LOW: Extracts and returns token usage for cost tracking
"""

from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass

import httpx
import structlog

from .circuit_breaker import CircuitBreaker

logger = structlog.get_logger("perplexity_client")

BASE_URL = "https://api.perplexity.ai/chat/completions"


@dataclass
class SonarResponse:
    """Parsed response from Perplexity."""
    data: dict
    tokens_used: int


def _strip_fences(text: str) -> str:
    """Remove markdown code fences that Perplexity wraps around JSON."""
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.split("\n")
    # Remove first line (```json or ```) and last line (```)
    start = 1
    end = len(lines)
    if lines[-1].strip() == "```":
        end = -1
    return "\n".join(lines[start:end]).strip()


async def query_perplexity(
    payload: dict,
    api_key: str,
    breaker: CircuitBreaker,
    timeout: int = 120,
) -> SonarResponse:
    """
    Fire one Sonar request with 3 retries + exponential backoff.
    Returns parsed JSON + token count.
    Raises RuntimeError on exhausted retries or open circuit.
    """
    if not breaker.allow():
        raise RuntimeError("circuit_open")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    last_error: str = ""

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(BASE_URL, headers=headers, json=payload)
                response.raise_for_status()

                data = response.json()
                content = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("total_tokens", 0)

                breaker.record_success()

                cleaned = _strip_fences(content)
                parsed = json.loads(cleaned)

                return SonarResponse(data=parsed, tokens_used=tokens)

        except httpx.HTTPStatusError as e:
            last_error = f"HTTP {e.response.status_code}"
            breaker.record_failure()
            logger.warning("sonar_http_error", status=e.response.status_code, attempt=attempt)
            wait = (2 ** attempt) + random.random()
            if e.response.status_code == 429:
                wait += random.random() * 3
            await asyncio.sleep(wait)

        except json.JSONDecodeError as e:
            last_error = f"json_parse: {e.msg}"
            breaker.record_failure()
            logger.warning("sonar_json_error", attempt=attempt, error=str(e))
            await asyncio.sleep(1 + random.random())

        except httpx.TimeoutException:
            last_error = "timeout"
            breaker.record_failure()
            logger.warning("sonar_timeout", attempt=attempt)
            await asyncio.sleep((2 ** attempt) + random.random())

        except (httpx.ConnectError, httpx.RemoteProtocolError) as e:
            last_error = f"network: {type(e).__name__}"
            breaker.record_failure()
            logger.warning("sonar_network_error", error=str(e), attempt=attempt)
            await asyncio.sleep((2 ** attempt) + random.random())

    raise RuntimeError(f"sonar_failure_after_3_retries: {last_error}")
