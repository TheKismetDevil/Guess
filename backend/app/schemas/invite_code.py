"""Invite code Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, field_validator

from app.utils.qq import QQ_ERROR_MESSAGE, is_valid_qq


class InviteCodeCreate(BaseModel):
    qq: str

    @field_validator("qq")
    @classmethod
    def validate_qq(cls, v: str) -> str:
        if not is_valid_qq(v):
            raise ValueError(QQ_ERROR_MESSAGE)
        return v


class InviteCodeResponse(BaseModel):
    code: str
    status: str
    bound_username: str | None = None
    bound_qq: str | None = None
    # Set when the code belongs to a placeholder user created by historical import;
    # such codes (and their placeholder users) cannot be deleted.
    placeholder_username: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class InviteCodeListResponse(BaseModel):
    data: list[InviteCodeResponse]
