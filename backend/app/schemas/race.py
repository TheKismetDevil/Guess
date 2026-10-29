"""Race-related Pydantic schemas."""

from datetime import date as date_type, datetime

from pydantic import BaseModel, field_validator, field_serializer
from sqlalchemy.orm import InstrumentedAttribute


class HorseSnapshot(BaseModel):
    name: str
    sex: str | None = None
    birth_year: int | None = None
    origin: str | None = None
    hemisphere: str | None = None
    location: str | None = None
    sire: str | None = None
    damsire: str | None = None
    previous_result: str | None = None
    previous_result_date: str | None = None
    previous_result_position: int | None = None
    best_win: str | None = None
    best_win_date: str | None = None


class PenaltyRule(BaseModel):
    position: int  # negative, e.g. -1 for last place
    points: int    # negative, e.g. -5


class CustomScoring(BaseModel):
    positive_scores: list[int]
    penalty_rules: list[PenaltyRule] | None = None


class RaceCreate(BaseModel):
    name: str
    date: date_type
    age_range: str
    sex_restriction: str
    race_grade: str
    country: str
    distance: str
    surface: str
    horse_ids: list[int] | None = None
    horse_weights: dict[int, str] | None = None  # horse_id → weight
    horse_jockeys: dict[int, str] | None = None  # horse_id → jockey
    custom_scoring: CustomScoring | None = None
    is_hidden: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if len(v) < 1 or len(v) > 200:
            raise ValueError("比赛名称长度需在 1-200 个字符之间")
        return v.strip()

    @field_validator("age_range")
    @classmethod
    def validate_age_range(cls, v: str) -> str:
        allowed = {"2岁", "2+岁", "3岁", "3+岁", "4+岁", "其他"}
        if v not in allowed:
            raise ValueError(f"无效的年龄范围，允许的值: {', '.join(allowed)}")
        return v

    @field_validator("sex_restriction")
    @classmethod
    def validate_sex_restriction(cls, v: str) -> str:
        allowed = {"无", "牝限", "牡牝限", "牡限"}
        if v not in allowed:
            raise ValueError(f"无效的性别限定，允许的值: {', '.join(allowed)}")
        return v

    @field_validator("race_grade")
    @classmethod
    def validate_race_grade(cls, v: str) -> str:
        allowed = {"G1", "G2", "G3", "JPN1", "JPN2", "其他", "自定义"}
        if v not in allowed:
            raise ValueError(f"无效的比赛等级，允许的值: {', '.join(allowed)}")
        return v

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str) -> str:
        allowed = {"日本", "英国", "美国", "澳大利亚", "中国香港", "法国", "阿联酋", "爱尔兰", "沙特", "卡塔尔", "南非", "德国", "加拿大", "新西兰", "韩国", "阿根廷", "乌拉圭", "巴西", "智利", "秘鲁", "其他"}
        if v not in allowed:
            raise ValueError(f"无效的国家或地区，允许的值: {', '.join(allowed)}")
        return v

    @field_validator("distance")
    @classmethod
    def validate_distance(cls, v: str) -> str:
        if len(v) < 1 or len(v) > 50:
            raise ValueError("长度需在 1-50 个字符之间")
        return v.strip()

    @field_validator("surface")
    @classmethod
    def validate_surface(cls, v: str) -> str:
        allowed = {"草地", "泥地", "全天候", "障碍", "其他"}
        if v not in allowed:
            raise ValueError(f"无效的场地类型，允许的值: {', '.join(allowed)}")
        return v

    @field_validator("horse_ids")
    @classmethod
    def validate_horse_ids(cls, v: list[int] | None) -> list[int] | None:
        if v is not None:
            if len(v) > 0 and len(v) < 2:
                raise ValueError("至少需要 2 匹参赛马")
            if len(v) != len(set(v)):
                raise ValueError("参赛马匹不能重复")
        return v


class RaceUpdate(BaseModel):
    name: str | None = None
    date: date_type | None = None
    age_range: str | None = None
    sex_restriction: str | None = None
    race_grade: str | None = None
    country: str | None = None
    distance: str | None = None
    surface: str | None = None
    horse_ids: list[int] | None = None
    horse_weights: dict[int, str] | None = None  # race_horse_id → weight
    horse_jockeys: dict[int, str] | None = None  # race_horse_id → jockey
    custom_scoring: CustomScoring | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is not None:
            if len(v) < 1 or len(v) > 200:
                raise ValueError("比赛名称长度需在 1-200 个字符之间")
            return v.strip()
        return v

    @field_validator("age_range")
    @classmethod
    def validate_age_range(cls, v: str | None) -> str | None:
        if v is not None:
            allowed = {"2岁", "2+岁", "3岁", "3+岁", "4+岁", "其他"}
            if v not in allowed:
                raise ValueError(f"无效的年龄范围，允许的值: {', '.join(allowed)}")
        return v

    @field_validator("sex_restriction")
    @classmethod
    def validate_sex_restriction(cls, v: str | None) -> str | None:
        if v is not None:
            allowed = {"无", "牝限", "牡牝限", "牡限"}
            if v not in allowed:
                raise ValueError(f"无效的性别限定，允许的值: {', '.join(allowed)}")
        return v

    @field_validator("race_grade")
    @classmethod
    def validate_race_grade(cls, v: str | None) -> str | None:
        if v is not None:
            allowed = {"G1", "G2", "G3", "JPN1", "JPN2", "其他", "自定义"}
            if v not in allowed:
                raise ValueError(f"无效的比赛等级，允许的值: {', '.join(allowed)}")
        return v

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str | None) -> str | None:
        if v is not None:
            allowed = {"日本", "英国", "美国", "澳大利亚", "中国香港", "法国", "阿联酋", "爱尔兰", "沙特", "卡塔尔", "南非", "德国", "加拿大", "新西兰", "韩国", "阿根廷", "乌拉圭", "巴西", "智利", "秘鲁", "其他"}
            if v not in allowed:
                raise ValueError(f"无效的国家或地区，允许的值: {', '.join(allowed)}")
        return v

    @field_validator("distance")
    @classmethod
    def validate_distance(cls, v: str | None) -> str | None:
        if v is not None:
            if len(v) < 1 or len(v) > 50:
                raise ValueError("长度需在 1-50 个字符之间")
            return v.strip()
        return v

    @field_validator("surface")
    @classmethod
    def validate_surface(cls, v: str | None) -> str | None:
        if v is not None:
            allowed = {"草地", "泥地", "全天候", "障碍", "其他"}
            if v not in allowed:
                raise ValueError(f"无效的场地类型，允许的值: {', '.join(allowed)}")
        return v

    @field_validator("horse_ids")
    @classmethod
    def validate_horse_ids(cls, v: list[int] | None) -> list[int] | None:
        if v is not None:
            if len(v) < 2:
                raise ValueError("至少需要 2 匹参赛马")
            if len(v) != len(set(v)):
                raise ValueError("参赛马匹不能重复")
        return v


class RaceHorseUpdate(BaseModel):
    weight: str | None = None
    jockey: str | None = None


class AddRaceHorseRequest(BaseModel):
    horse_id: int
    weight: str | None = None
    jockey: str | None = None


class GateOrderUpdate(BaseModel):
    order: list[int]

    @field_validator("order")
    @classmethod
    def validate_order(cls, v: list[int]) -> list[int]:
        if len(v) != len(set(v)):
            raise ValueError("闸位排序不能包含重复马匹")
        return v


class RaceHorseResponse(BaseModel):
    race_horse_id: int
    horse_id: int
    snapshot_data: HorseSnapshot
    position: int | None = None
    gate: int | None = None
    weight: str | None = None
    jockey: str | None = None

    model_config = {"from_attributes": True}


class RaceListResponse(BaseModel):
    id: int
    name: str
    date: date_type
    age_range: str
    sex_restriction: str
    race_grade: str
    country: str
    distance: str
    surface: str
    status: str
    custom_scoring: CustomScoring | None = None
    is_hidden: bool = False
    horse_count: int
    vote_count: int
    has_voted: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class RaceDetailResponse(BaseModel):
    id: int
    name: str
    date: date_type
    age_range: str
    sex_restriction: str
    race_grade: str
    country: str
    distance: str
    surface: str
    status: str
    custom_scoring: CustomScoring | None = None
    is_hidden: bool = False
    horses: list[RaceHorseResponse]
    horse_votes: dict | None = None  # populated for settled races
    vote_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
