"""Vote-related Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel


class VoteCreate(BaseModel):
    race_horse_id: int


class VoteResponse(BaseModel):
    id: int
    user_id: int
    race_id: int
    race_horse_id: int
    horse_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class VoteListEntry(BaseModel):
    user_id: int
    username: str
    avatar_key: str | None = None
    race_horse_id: int
    horse_name: str
    points: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
