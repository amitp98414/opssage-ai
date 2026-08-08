from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4


MAX_EVENTS = 100
_events: deque[dict[str, object]] = deque(maxlen=MAX_EVENTS)
_events_lock = Lock()


def add_event(
    *,
    event_type: str,
    status: str,
    message: str,
    agent: str | None = None,
    task_id: str | None = None,
) -> dict[str, object]:
    event = {
        "id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        "status": status,
        "message": message,
        "agent": agent,
        "task_id": task_id,
    }
    with _events_lock:
        _events.appendleft(event)
    return event


def list_events(limit: int = 50) -> list[dict[str, object]]:
    safe_limit = min(max(limit, 1), MAX_EVENTS)
    with _events_lock:
        return list(_events)[:safe_limit]


def clear_events() -> None:
    with _events_lock:
        _events.clear()


def control_center_status() -> dict[str, object]:
    with _events_lock:
        latest = _events[0] if _events else None
    return {
        "system": "online",
        "service": "OpsSage AI Control Center",
        "active_agent": latest.get("agent") if latest else None,
        "latest_event": latest,
        "event_count": len(_events),
    }
