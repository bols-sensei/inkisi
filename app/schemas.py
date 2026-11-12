from pydantic import BaseModel, Field, ConfigDict
from typing import Literal

class TokenRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)

class EntryRequest(BaseModel):
    invitation_id: int = Field(gt=0)
    quantity: int = Field(default=1, ge=1, le=1000)
    method: Literal["qr", "manual", "nfc", "offline"] = "qr"
    note: str = Field(default="", max_length=1000)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=100)

class SyncEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_id: str = Field(min_length=8, max_length=100)
    event_id: int = Field(gt=0)
    token: str = Field(min_length=8, max_length=200)
    quantity: int = Field(default=1, ge=1, le=1000)
    method: Literal["qr", "manual", "nfc"] = "qr"
    occurred_at: str | None = Field(default=None, max_length=60)
    user_id: int | None = Field(default=None, gt=0)  # compte qui a scanné ; un autre compte ne peut pas synchroniser à sa place

class SyncBatch(BaseModel):
    entries: list[SyncEntry] = Field(min_length=1, max_length=500)

class ExceptionDecision(BaseModel):
    invitation_id: int = Field(gt=0)
    reason: str = Field(min_length=8, max_length=1000)
    decision: Literal["approve", "reject", "review"] = "review"

class EventCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    event_date: str = Field(default="", max_length=40)
    start_date: str = Field(default="", max_length=20)
    start_time: str = Field(default="", max_length=10)
    end_date: str = Field(default="", max_length=20)
    end_time: str = Field(default="", max_length=10)
    venue: str = Field(default="", max_length=240)
    organization_id: int | None = Field(default=None, gt=0)
    event_type: Literal["wedding", "conference"] = "wedding"
    capacity: int | None = Field(default=None, ge=1, le=100000)

class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    full_name: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=10, max_length=256)
    role: Literal["agent", "supervisor", "admin"] = "agent"
    email: str | None = Field(default=None, max_length=254)
    organization_id: int | None = Field(default=None, gt=0)  # obligatoire pour un superadmin, ignoré pour un admin

class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=160)
    role: Literal["agent", "supervisor", "admin"] | None = None
    active: bool | None = None
    email: str | None = Field(default=None, max_length=254)
    new_password: str | None = Field(default=None, min_length=10, max_length=256)

class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=10, max_length=256)

class OrganizationStatusUpdate(BaseModel):
    status: Literal["active", "suspended"]
    reason: str = Field(default="", max_length=500)

class InvitationAction(BaseModel):
    reason: str = Field(default="", max_length=500)

class AssignmentCreate(BaseModel):
    user_id: int = Field(gt=0)


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    admin_username: str = Field(min_length=3, max_length=80)
    admin_full_name: str = Field(min_length=2, max_length=160)
    admin_password: str = Field(min_length=10, max_length=256)
    admin_email: str | None = Field(default=None, max_length=254)

class SubscriptionUpdate(BaseModel):
    plan_code: str = Field(min_length=2, max_length=40)
    starts_at: str | None = None
    ends_at: str
    status: Literal["active", "suspended", "expired"] = "active"


class PlanCreate(BaseModel):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=100)
    event_limit: int = Field(ge=-1)
    advanced_features: bool = False

class PlanUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    event_limit: int = Field(ge=-1)
    advanced_features: bool = False
    active: bool = True
