from fastapi import APIRouter, Query

from app.services.control_center import control_center_status, list_events


router = APIRouter(
    prefix="/control",
    tags=["OpsSage Control Center"],
)


@router.get("/status")
def get_control_center_status():
    """Return non-sensitive control-center health metadata."""
    return control_center_status()


@router.get("/events")
def get_control_center_events(
    limit: int = Query(default=50, ge=1, le=100),
):
    """Return recent non-sensitive agent lifecycle events."""
    return {"events": list_events(limit)}
