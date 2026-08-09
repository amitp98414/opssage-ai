from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AdCampaign(Base):
    __tablename__ = "ad_campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    sponsor: Mapped[str] = mapped_column(String(160), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    target_url: Mapped[str] = mapped_column(String(500), nullable=False)
    bid_per_1000: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=1.0)
    budget: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0.0)
    spent: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0.0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class AdEvent(Base):
    __tablename__ = "ad_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    campaign_id: Mapped[str] = mapped_column(ForeignKey("ad_campaigns.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    session_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class RevenueLedger(Base):
    __tablename__ = "revenue_ledger"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("ad_campaigns.id"), nullable=False, index=True)
    gross_amount: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0.0)
    platform_amount: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0.0)
    developer_amount: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class DeveloperAccount(Base):
    __tablename__ = "developer_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    revenue_share_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=70)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
