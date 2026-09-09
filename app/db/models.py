from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, Text, BigInteger, Boolean, Integer, DateTime, ForeignKey, Numeric, JSON, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

def now(): return datetime.now(timezone.utc)
class Base(DeclarativeBase): pass
class User(Base):
    __tablename__='users'
    id: Mapped[int]=mapped_column(primary_key=True)
    telegram_id: Mapped[int]=mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str|None]=mapped_column(String(255))
    first_name: Mapped[str|None]=mapped_column(String(255))
    last_name: Mapped[str|None]=mapped_column(String(255))
    accepted_terms: Mapped[bool]=mapped_column(Boolean, default=False)
    accepted_privacy: Mapped[bool]=mapped_column(Boolean, default=False)
    terms_version: Mapped[str|None]=mapped_column(String(32))
    privacy_version: Mapped[str|None]=mapped_column(String(32))
    trial_used: Mapped[bool]=mapped_column(Boolean, default=False)
    blocked: Mapped[bool]=mapped_column(Boolean, default=False)
    personal_discount: Mapped[int]=mapped_column(Integer, default=0)
    referral_code: Mapped[str]=mapped_column(String(64), unique=True, index=True)
    referred_by_id: Mapped[int|None]=mapped_column(ForeignKey('users.id'))
    partner_id: Mapped[int|None]=mapped_column(ForeignKey('partners.id'))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now, onupdate=now)
class Plan(Base):
    __tablename__='plans'
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(255), unique=True)
    description: Mapped[str]=mapped_column(Text, default='')
    active: Mapped[bool]=mapped_column(Boolean, default=True)
    device_limit: Mapped[int]=mapped_column(Integer, default=0)
    traffic_limit_gb: Mapped[int]=mapped_column(Integer, default=0)
    squad_uuids: Mapped[list]=mapped_column(JSON, default=list)
class PlanPeriod(Base):
    __tablename__='plan_periods'
    id: Mapped[int]=mapped_column(primary_key=True)
    plan_id: Mapped[int]=mapped_column(ForeignKey('plans.id', ondelete='CASCADE'), index=True)
    days: Mapped[int]=mapped_column(Integer)
    price: Mapped[Decimal]=mapped_column(Numeric(12,2))
    active: Mapped[bool]=mapped_column(Boolean, default=True)
class Subscription(Base):
    __tablename__='subscriptions'
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    plan_id: Mapped[int|None]=mapped_column(ForeignKey('plans.id'))
    remnawave_user_uuid: Mapped[str|None]=mapped_column(String(64), index=True)
    started_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), index=True)
    active: Mapped[bool]=mapped_column(Boolean, default=True)
    grace_until: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    subscription_url: Mapped[str|None]=mapped_column(Text)
    squad_uuids: Mapped[list]=mapped_column(JSON, default=list)
    device_limit: Mapped[int]=mapped_column(Integer, default=0)
    traffic_limit_gb: Mapped[int]=mapped_column(Integer, default=0)
class Payment(Base):
    __tablename__='payments'
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id'))
    plan_id: Mapped[int]=mapped_column(ForeignKey('plans.id'))
    period_id: Mapped[int]=mapped_column(ForeignKey('plan_periods.id'))
    transaction_id: Mapped[str|None]=mapped_column(String(128), unique=True, index=True)
    original_amount: Mapped[Decimal]=mapped_column(Numeric(12,2))
    amount: Mapped[Decimal]=mapped_column(Numeric(12,2))
    promo_code: Mapped[str|None]=mapped_column(String(64))
    status: Mapped[str]=mapped_column(String(32), default='PENDING', index=True)
    payment_url: Mapped[str|None]=mapped_column(Text)
    metadata_json: Mapped[dict]=mapped_column(JSON, default=dict)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)
    confirmed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
class PromoCode(Base):
    __tablename__='promo_codes'
    id: Mapped[int]=mapped_column(primary_key=True)
    code: Mapped[str]=mapped_column(String(64), unique=True, index=True)
    kind: Mapped[str]=mapped_column(String(32), default='PERCENT')
    value: Mapped[Decimal]=mapped_column(Numeric(12,2), default=0)
    bonus_days: Mapped[int]=mapped_column(Integer, default=0)
    target_plan_id: Mapped[int|None]=mapped_column(ForeignKey('plans.id'))
    max_uses: Mapped[int]=mapped_column(Integer, default=0)
    used_count: Mapped[int]=mapped_column(Integer, default=0)
    per_user_limit: Mapped[int]=mapped_column(Integer, default=1)
    active: Mapped[bool]=mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
class PromoUsage(Base):
    __tablename__='promo_usages'
    id: Mapped[int]=mapped_column(primary_key=True)
    promo_id: Mapped[int]=mapped_column(ForeignKey('promo_codes.id', ondelete='CASCADE'))
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    payment_id: Mapped[int|None]=mapped_column(ForeignKey('payments.id'))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)
class Referral(Base):
    __tablename__='referrals'
    id: Mapped[int]=mapped_column(primary_key=True)
    referrer_id: Mapped[int]=mapped_column(ForeignKey('users.id'))
    invited_id: Mapped[int]=mapped_column(ForeignKey('users.id'), unique=True)
    rewarded: Mapped[bool]=mapped_column(Boolean, default=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)
class Partner(Base):
    __tablename__='partners'
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(255))
    code: Mapped[str]=mapped_column(String(64), unique=True, index=True)
    commission_percent: Mapped[Decimal]=mapped_column(Numeric(5,2), default=20)
    payout_balance: Mapped[Decimal]=mapped_column(Numeric(12,2), default=0)
    active: Mapped[bool]=mapped_column(Boolean, default=True)
    clicks: Mapped[int]=mapped_column(Integer, default=0)
    registrations: Mapped[int]=mapped_column(Integer, default=0)
    purchases: Mapped[int]=mapped_column(Integer, default=0)
class PartnerConversion(Base):
    __tablename__='partner_conversions'
    id: Mapped[int]=mapped_column(primary_key=True)
    partner_id: Mapped[int]=mapped_column(ForeignKey('partners.id', ondelete='CASCADE'))
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    payment_id: Mapped[int]=mapped_column(ForeignKey('payments.id', ondelete='CASCADE'), unique=True)
    amount: Mapped[Decimal]=mapped_column(Numeric(12,2))
    commission: Mapped[Decimal]=mapped_column(Numeric(12,2))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)
class Ticket(Base):
    __tablename__='tickets'
    id: Mapped[int]=mapped_column(primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id'))
    status: Mapped[str]=mapped_column(String(32), default='OPEN')
    subject: Mapped[str]=mapped_column(String(255), default='Поддержка')
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)
class TicketMessage(Base):
    __tablename__='ticket_messages'
    id: Mapped[int]=mapped_column(primary_key=True)
    ticket_id: Mapped[int]=mapped_column(ForeignKey('tickets.id', ondelete='CASCADE'))
    author_telegram_id: Mapped[int]=mapped_column(BigInteger)
    text: Mapped[str]=mapped_column(Text)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)
class Broadcast(Base):
    __tablename__='broadcasts'
    id: Mapped[int]=mapped_column(primary_key=True)
    audience: Mapped[str]=mapped_column(String(64))
    text: Mapped[str]=mapped_column(Text)
    sent: Mapped[int]=mapped_column(Integer, default=0)
    failed: Mapped[int]=mapped_column(Integer, default=0)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)
class Setting(Base):
    __tablename__='settings'
    key: Mapped[str]=mapped_column(String(128), primary_key=True)
    value: Mapped[str]=mapped_column(Text, default='')
class NotificationLog(Base):
    __tablename__='notification_logs'
    id: Mapped[int]=mapped_column(primary_key=True)
    subscription_id: Mapped[int]=mapped_column(ForeignKey('subscriptions.id', ondelete='CASCADE'))
    reminder_day: Mapped[int]=mapped_column(Integer)
    sent_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)
    __table_args__=(UniqueConstraint('subscription_id','reminder_day'),)
class AdminLog(Base):
    __tablename__='admin_logs'
    id: Mapped[int]=mapped_column(primary_key=True)
    admin_telegram_id: Mapped[int]=mapped_column(BigInteger)
    action: Mapped[str]=mapped_column(String(255))
    details: Mapped[dict]=mapped_column(JSON, default=dict)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)
