from pydantic import BaseModel, Field, StrictInt


class HistoricalScoreUpdate(BaseModel):
    points: StrictInt = Field(ge=-2147483648, le=2147483647)
    expected_points: StrictInt = Field(ge=-2147483648, le=2147483647)
