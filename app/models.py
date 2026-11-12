from datetime import datetime, timezone
import uuid
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

def utcnow(): return datetime.now(timezone.utc)

class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Plan(Base):
    __tablename__ = "plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    event_limit: Mapped[int] = mapped_column(Integer, default=1)
    advanced_features: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    status: Mapped[str] = mapped_column(String(20), default="trial")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    organization: Mapped[Organization] = relationship()
    plan: Mapped[Plan] = relationship()

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="agent") # superadmin, admin, supervisor, agent
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Adresse e-mail (stockée en minuscules). Unique : une adresse = un compte = un seul essai gratuit.
    email: Mapped[str | None] = mapped_column(String(254), nullable=True, unique=True, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    # Incrémenté pour révoquer immédiatement toutes les sessions et jetons JWT du compte.
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    assignments: Mapped[list["EventAssignment"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class UserToken(Base):
    """Jeton à usage unique (vérification d'e-mail, réinitialisation de mot de passe). Seul le hachage est stocké."""
    __tablename__ = "user_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(20))  # verify_email | reset_password
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index('uq_events_registration_token', 'registration_token', unique=True),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180))
    event_date: Mapped[str] = mapped_column(String(40), default="")
    start_date: Mapped[str] = mapped_column(String(20), default="")
    start_time: Mapped[str] = mapped_column(String(10), default="")
    end_date: Mapped[str] = mapped_column(String(20), default="")
    end_time: Mapped[str] = mapped_column(String(10), default="")
    venue: Mapped[str] = mapped_column(String(240), default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    event_type: Mapped[str] = mapped_column(String(20), default="wedding")
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    registration_open: Mapped[bool] = mapped_column(Boolean, default=False)
    registration_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    member_badge_token: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True, index=True)
    member_badge_config: Mapped[str] = mapped_column(Text, default='{}')
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    invitations: Mapped[list["Invitation"]] = relationship(back_populates="event", cascade="all, delete-orphan")
    assignments: Mapped[list["EventAssignment"]] = relationship(back_populates="event", cascade="all, delete-orphan")

class EventAssignment(Base):
    __tablename__ = "event_assignments"
    __table_args__ = (UniqueConstraint("event_id", "user_id", name="uq_event_user"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    event: Mapped[Event] = relationship(back_populates="assignments")
    user: Mapped[User] = relationship(back_populates="assignments")

class Invitation(Base):
    __tablename__ = "invitations"
    __table_args__ = (UniqueConstraint("event_id", "reference", name="uq_event_reference"), UniqueConstraint("token", name="uq_invitation_token"), Index('uq_invitations_badge_reference', 'badge_reference', unique=True))
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    sequence_no: Mapped[int] = mapped_column(Integer)
    reference: Mapped[str] = mapped_column(String(40))
    badge_reference: Mapped[str] = mapped_column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    guest_name: Mapped[str] = mapped_column(String(200))
    invitation_type: Mapped[str] = mapped_column(String(30), default="individuelle")
    quota: Mapped[int] = mapped_column(Integer, default=1)
    table_name: Mapped[str] = mapped_column(String(80), default="")
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # FIX: rétablir la relation inverse attendue par Event.invitations.
    event: Mapped["Event"] = relationship(back_populates="invitations")
    entries: Mapped[list["EntryRecord"]] = relationship(back_populates="invitation", cascade="all, delete-orphan")

class EntryRecord(Base):
    __tablename__ = "entry_records"
    # Clé d'idempotence unique PAR ÉVÉNEMENT (pas à l'échelle de la plateforme : deux clients ne doivent jamais se heurter).
    __table_args__ = (UniqueConstraint("event_id", "idempotency_key", name="uq_entry_idempotency_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    invitation_id: Mapped[int] = mapped_column(ForeignKey("invitations.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(20), default="qr")
    note: Mapped[str] = mapped_column(Text, default="")
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # created_at = instant réel du passage (date du scan hors ligne si fournie) ; synced_at = réception par le serveur.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invitation: Mapped[Invitation] = relationship(back_populates="entries")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    # Organisation concernée (renseignée automatiquement à l'insertion si absente) : permet un journal par client.
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100))
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExceptionReview(Base):
    __tablename__ = "exception_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    invitation_id: Mapped[int] = mapped_column(ForeignKey("invitations.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(20), default="review")
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    invitation: Mapped["Invitation"] = relationship()
    user: Mapped["User"] = relationship()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ConferenceRegistration(Base):
    __tablename__ = "conference_registrations"
    __table_args__ = (UniqueConstraint("event_id", "email", name="uq_conference_event_email"), UniqueConstraint("public_token", name="uq_conference_public_token"), Index('uq_conference_registrations_badge_token', 'badge_token', unique=True), Index('uq_conference_registrations_badge_reference', 'badge_reference', unique=True))
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    full_name: Mapped[str] = mapped_column(String(180))
    first_name: Mapped[str] = mapped_column(String(100), default="")
    last_name: Mapped[str] = mapped_column(String(100), default="")
    email: Mapped[str] = mapped_column(String(254), index=True)
    phone: Mapped[str] = mapped_column(String(40), default="")
    profession: Mapped[str] = mapped_column(String(180), default="")
    organization_name: Mapped[str] = mapped_column(String(180), default="")
    category: Mapped[str] = mapped_column(String(40), default="participant")
    photo_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True) # pending, accepted, rejected, cancelled, waitlist
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    public_token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    badge_token: Mapped[str] = mapped_column(String(128))
    badge_reference: Mapped[str] = mapped_column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    verification_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    verification_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class MemberBadge(Base):
    """Badge remis hors inscription publique ; conservé hors des listes de participants."""
    __tablename__ = "member_badges"
    __table_args__ = (UniqueConstraint('event_id', 'email', name='uq_member_badge_event_email'),
                      UniqueConstraint('public_token', name='uq_member_badge_public_token'),
                      Index('uq_member_badges_reference', 'badge_reference', unique=True))
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey('events.id', ondelete='CASCADE'), index=True)
    full_name: Mapped[str] = mapped_column(String(180))
    email: Mapped[str] = mapped_column(String(254))
    organization_name: Mapped[str] = mapped_column(String(180), default='')
    photo_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(60))
    public_token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    badge_reference: Mapped[str] = mapped_column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SupportTicket(Base):
    """Conversation de support entre une organisation et l'équipe plateforme."""
    __tablename__ = 'support_tickets'
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey('organizations.id', ondelete='CASCADE'), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    subject: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(20), default='open', index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, index=True)


class SupportMessage(Base):
    __tablename__ = 'support_messages'
    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey('support_tickets.id', ondelete='CASCADE'), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EventProgramItem(Base):
    __tablename__ = "event_program_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    location: Mapped[str] = mapped_column(String(180), default="")
    speaker: Mapped[str] = mapped_column(String(180), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TeamTask(Base):
    __tablename__ = "team_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="todo") # todo, in_progress, done, blocked
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TaskHistory(Base):
    __tablename__ = "task_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("team_tasks.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(60))
    old_value: Mapped[str] = mapped_column(Text, default="")
    new_value: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    body: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(40), default="general")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(String(255))
    auth: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PushOutbox(Base):
    __tablename__ = "push_outbox"
    __table_args__ = (Index('ix_push_outbox_status_available_at', 'status', 'available_at'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    notification_id: Mapped[int] = mapped_column(ForeignKey("notifications.id", ondelete="CASCADE"), index=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("push_subscriptions.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(String(40), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    notification: Mapped[Notification] = relationship()
    subscription: Mapped[PushSubscription] = relationship()


class EmailVerification(Base):
    __tablename__ = "email_verifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    registration_id: Mapped[int] = mapped_column(ForeignKey("conference_registrations.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ConferenceCheckin(Base):
    __tablename__ = "conference_checkins"
    __table_args__ = (UniqueConstraint("registration_id", name="uq_conference_single_checkin"), UniqueConstraint("event_id", "idempotency_key", name="uq_conference_event_idempotency"))
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    registration_id: Mapped[int] = mapped_column(ForeignKey("conference_registrations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    checked_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


from sqlalchemy import event as _sa_event, select as _select  # noqa: E402


@_sa_event.listens_for(AuditLog, "before_insert")
def _audit_fill_organization(mapper, connection, target):
    """Déduit l'organisation d'une ligne de journal : celle de l'événement, sinon celle de l'auteur."""
    if target.organization_id is not None:
        return
    if target.event_id is not None:
        target.organization_id = connection.execute(_select(Event.organization_id).where(Event.id == target.event_id)).scalar()
    if target.organization_id is None and target.user_id is not None:
        target.organization_id = connection.execute(_select(User.organization_id).where(User.id == target.user_id)).scalar()
