from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlmodel import Field, SQLModel  # pyright: ignore[reportUnknownVariableType]


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class PasswordReset(SQLModel, table=True):
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    email: str = Field(index=True)
    token: str = Field(unique=True, index=True)
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.now)
    used_at: datetime | None = None
