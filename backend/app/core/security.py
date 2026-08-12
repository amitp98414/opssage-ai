from collections import defaultdict, deque
from hashlib import sha256
from math import ceil
from secrets import compare_digest
from threading import Lock
from time import monotonic

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import settings


api_key_header = APIKeyHeader(
    name="X-API-Key",
    scheme_name="OrbitOSApiKey",
    description="API key required for AI execution endpoints.",
    auto_error=False,
)


def require_api_key(
    api_key: str | None = Security(api_key_header),
) -> str:
    configured_key = settings.OPSSAGE_API_KEY.strip()

    if not configured_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI execution is disabled on this deployment.",
        )

    if api_key is None or not compare_digest(api_key, configured_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key


_rate_limit_history: dict[str, deque[float]] = defaultdict(deque)
_rate_limit_lock = Lock()


def enforce_rate_limit(
    request: Request,
    api_key: str = Depends(require_api_key),
) -> str:
    request_limit = max(settings.RATE_LIMIT_REQUESTS, 1)
    window_seconds = max(settings.RATE_LIMIT_WINDOW_SECONDS, 1)
    now = monotonic()

    # Store only a hash of the API key in memory; never retain the raw secret.
    bucket_id = sha256(api_key.encode("utf-8")).hexdigest()

    with _rate_limit_lock:
        history = _rate_limit_history[bucket_id]
        cutoff = now - window_seconds

        while history and history[0] <= cutoff:
            history.popleft()

        if len(history) >= request_limit:
            retry_after = max(
                1,
                ceil(window_seconds - (now - history[0])),
            )

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Try again later.",
                headers={"Retry-After": str(retry_after)},
            )

        history.append(now)

    return api_key


def reset_rate_limit_state() -> None:
    """Clear rate-limit history for isolated automated tests."""
    with _rate_limit_lock:
        _rate_limit_history.clear()
