from functools import lru_cache

import httpx

from app.core.config import settings


@lru_cache(maxsize=1)
def get_ollama_url() -> str:
    return settings.OLLAMA_BASE_URL.rstrip("/")


def ask_ollama(prompt: str) -> str:
    payload = {
        "model": settings.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }

    try:
        response = httpx.post(
            f"{get_ollama_url()}/api/generate",
            json=payload,
            timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Local AI provider is unavailable: {exc}") from exc

    data = response.json()
    answer = data.get("response")
    if not answer:
        raise RuntimeError("Local AI provider returned an empty response")
    return answer
