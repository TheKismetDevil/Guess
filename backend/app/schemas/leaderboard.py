"""Leaderboard-related Pydantic schemas."""

from pydantic import BaseModel, field_serializer


class LeaderboardEntry(BaseModel):
    username: str
    total_points: int
    races_participated: int
    avg_points: float
    avatar_key: str | None = None

    @field_serializer("avg_points")
    def serialize_avg(self, value: float) -> float:
        return round(value, 3)

    model_config = {"from_attributes": True}
