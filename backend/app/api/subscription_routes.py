from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.subscriber import Subscriber


router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


class SubscriptionRequest(BaseModel):
    email: EmailStr
    company: str | None = Field(default=None, max_length=160)
    source: str = Field(default="website", min_length=2, max_length=80)
    consent: bool


class SubscriptionResponse(BaseModel):
    status: str
    message: str


@router.post(
    "",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def subscribe(
    payload: SubscriptionRequest,
    db: Session = Depends(get_db),
):
    if not payload.consent:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Consent is required to subscribe.",
        )

    normalized_email = str(payload.email).strip().lower()
    existing = db.scalar(
        select(Subscriber).where(Subscriber.email == normalized_email)
    )

    if existing:
        if not existing.is_active:
            existing.is_active = True
            existing.consent = True
            existing.company = payload.company or existing.company
            db.commit()

        return SubscriptionResponse(
            status="already_subscribed",
            message="This email is already subscribed to OpsSage AI updates.",
        )

    subscriber = Subscriber(
        email=normalized_email,
        company=payload.company.strip() if payload.company else None,
        source=payload.source,
        consent=True,
    )
    db.add(subscriber)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email is already subscribed.",
        ) from exc

    return SubscriptionResponse(
        status="subscribed",
        message="You are subscribed to OpsSage AI product updates.",
    )
