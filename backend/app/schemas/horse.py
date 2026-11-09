"""Horse-related Pydantic schemas."""

from datetime import date

from pydantic import BaseModel, field_validator


class HorseCreate(BaseModel):
    name: str
    sex: str | None = None
    birth_year: int | None = None
    origin: str | None = None
    hemisphere: str | None = None
    location: str | None = None
    sire: str | None = None
    damsire: str | None = None
    previous_result: str | None = None
    previous_result_date: date | None = None
    previous_result_position: int | None = None
    best_win: str | None = None
    best_win_date: date | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if len(v) < 1 or len(v) > 100:
            raise ValueError("马匹名称长度需在 1-100 个字符之间")
        return v.strip()

    @field_validator("sex")
    @classmethod
    def validate_sex(cls, v: str | None) -> str | None:
        if v is not None and v not in ("牡", "牝", "骟"):
            raise ValueError("性别只能为 牡、牝 或 骟")
        return v

    @field_validator("hemisphere")
    @classmethod
    def validate_hemisphere(cls, v: str | None) -> str | None:
        if v is not None and v not in ("north", "south"):
            raise ValueError("半球只能为 north 或 south")
        return v


class HorseUpdate(BaseModel):
    name: str | None = None
    sex: str | None = None
    birth_year: int | None = None
    origin: str | None = None
    hemisphere: str | None = None
    location: str | None = None
    sire: str | None = None
    damsire: str | None = None
    previous_result: str | None = None
    previous_result_date: date | None = None
    previous_result_position: int | None = None
    best_win: str | None = None
    best_win_date: date | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is not None:
            if len(v) < 1 or len(v) > 100:
                raise ValueError("马匹名称长度需在 1-100 个字符之间")
            return v.strip()
        return v

    @field_validator("sex")
    @classmethod
    def validate_sex(cls, v: str | None) -> str | None:
        if v is not None and v not in ("牡", "牝", "骟"):
            raise ValueError("性别只能为 牡、牝 或 骟")
        return v

    @field_validator("hemisphere")
    @classmethod
    def validate_hemisphere(cls, v: str | None) -> str | None:
        if v is not None and v not in ("north", "south"):
            raise ValueError("半球只能为 north 或 south")
        return v


class HorseResponse(BaseModel):
    id: int
    name: str
    sex: str | None = None
    birth_year: int | None = None
    origin: str | None = None
    hemisphere: str | None = None
    location: str | None = None
    sire: str | None = None
    damsire: str | None = None
    previous_result: str | None = None
    previous_result_date: date | None = None
    previous_result_position: int | None = None
    best_win: str | None = None
    best_win_date: date | None = None

    model_config = {"from_attributes": True}
