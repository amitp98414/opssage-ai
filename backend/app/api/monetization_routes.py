from hashlib import sha256
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.monetization import AdCampaign, AdEvent, DeveloperAccount, RevenueLedger


router = APIRouter(prefix="/monetization", tags=["Monetization POC"])


class CampaignCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    sponsor: str = Field(min_length=2, max_length=160)
    message: str = Field(min_length=2, max_length=500)
    target_url: HttpUrl
    bid_per_1000: float = Field(gt=0, le=1000)
    budget: float = Field(gt=0, le=1_000_000)


class CampaignResponse(BaseModel):
    id: str
    name: str
    sponsor: str
    message: str
    target_url: str
    bid_per_1000: float
    budget: float
    spent: float
    active: bool


class AdResponse(BaseModel):
    event_id: str
    campaign_id: str
    sponsor: str
    message: str
    target_url: str
    disclosure: str = "Sponsored"


class EventRequest(BaseModel):
    event_id: str
    campaign_id: str
    event_type: str = Field(pattern="^(impression|click)$")
    session_id: str = Field(min_length=16, max_length=200)


class EventResponse(BaseModel):
    accepted: bool
    event_id: str
    billed_amount: float = 0.0
    currency: str = "USD"


class EarningsResponse(BaseModel):
    developer_amount: float
    platform_amount: float
    gross_amount: float
    currency: str = "USD"


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _campaign_response(campaign: AdCampaign) -> CampaignResponse:
    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        sponsor=campaign.sponsor,
        message=campaign.message,
        target_url=campaign.target_url,
        bid_per_1000=float(campaign.bid_per_1000),
        budget=float(campaign.budget),
        spent=float(campaign.spent),
        active=campaign.active,
    )


@router.post("/campaigns", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db)):
    parsed = urlparse(str(payload.target_url))
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=422, detail="Only HTTP(S) campaign URLs are allowed.")

    campaign = AdCampaign(
        name=payload.name.strip(),
        sponsor=payload.sponsor.strip(),
        message=payload.message.strip(),
        target_url=str(payload.target_url),
        bid_per_1000=payload.bid_per_1000,
        budget=payload.budget,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return _campaign_response(campaign)


@router.get("/campaigns", response_model=list[CampaignResponse])
def list_campaigns(db: Session = Depends(get_db)):
    campaigns = db.scalars(select(AdCampaign).order_by(AdCampaign.created_at.desc())).all()
    return [_campaign_response(campaign) for campaign in campaigns]


@router.get("/ad", response_model=AdResponse)
def get_ad(
    db: Session = Depends(get_db),
    x_session_id: str | None = Header(default=None),
):
    if not x_session_id or len(x_session_id) < 16:
        raise HTTPException(status_code=400, detail="X-Session-ID header is required.")

    campaign = db.scalar(
        select(AdCampaign)
        .where(AdCampaign.active.is_(True), AdCampaign.spent < AdCampaign.budget)
        .order_by(AdCampaign.bid_per_1000.desc())
        .limit(1)
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="No eligible campaign is available.")

    return AdResponse(
        event_id=str(uuid4()),
        campaign_id=campaign.id,
        sponsor=campaign.sponsor,
        message=campaign.message,
        target_url=campaign.target_url,
    )


@router.post("/events", response_model=EventResponse)
def record_event(
    payload: EventRequest,
    db: Session = Depends(get_db),
    user_agent: str | None = Header(default=None),
):
    campaign = db.get(AdCampaign, payload.campaign_id)
    if not campaign or not campaign.active:
        raise HTTPException(status_code=404, detail="Campaign not found or inactive.")

    if db.scalar(select(AdEvent).where(AdEvent.id == payload.event_id)):
        return EventResponse(accepted=False, event_id=payload.event_id)

    event = AdEvent(
        id=payload.event_id,
        campaign_id=payload.campaign_id,
        event_type=payload.event_type,
        session_hash=_hash(payload.session_id),
        user_agent=user_agent[:500] if user_agent else None,
    )
    db.add(event)

    # POC billing uses CPM. Clicks are tracked but not billed yet.
    billed_amount = 0.0
    if payload.event_type == "impression":
        remaining = max(0.0, float(campaign.budget) - float(campaign.spent))
        billed_amount = min(float(campaign.bid_per_1000) / 1000.0, remaining)
        if billed_amount > 0:
            campaign.spent = float(campaign.spent) + billed_amount
            developer_share = billed_amount * 0.70
            platform_share = billed_amount - developer_share
            db.add(
                RevenueLedger(
                    event_id=payload.event_id,
                    campaign_id=campaign.id,
                    gross_amount=billed_amount,
                    developer_amount=developer_share,
                    platform_amount=platform_share,
                )
            )

    db.commit()
    return EventResponse(accepted=True, event_id=payload.event_id, billed_amount=billed_amount)


@router.get("/earnings", response_model=EarningsResponse)
def earnings(db: Session = Depends(get_db)):
    gross, developer, platform = db.execute(
        select(
            func.coalesce(func.sum(RevenueLedger.gross_amount), 0),
            func.coalesce(func.sum(RevenueLedger.developer_amount), 0),
            func.coalesce(func.sum(RevenueLedger.platform_amount), 0),
        )
    ).one()
    return EarningsResponse(
        gross_amount=float(gross),
        developer_amount=float(developer),
        platform_amount=float(platform),
    )


@router.get("/health")
def monetization_health():
    return {"status": "ok", "mode": "poc", "billing": "simulated-cpm"}
