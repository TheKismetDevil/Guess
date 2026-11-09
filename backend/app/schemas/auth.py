"""Auth-related Pydantic schemas."""

from pydantic import BaseModel, field_validator


class RegisterRequest(BaseModel):
    username: str
    password: str
    qq: str
    invite_code: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if len(v) < 3 or len(v) > 20:
            raise ValueError("用户名长度需在 3-20 个字符之间")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码至少需要 6 个字符")
        if len(v) > 128:
            raise ValueError("密码长度不能超过 128 个字符")
        return v

    @field_validator("qq")
    @classmethod
    def validate_qq(cls, v: str) -> str:
        if len(v) < 5 or len(v) > 20:
            raise ValueError("QQ 号长度需在 5-20 个字符之间")
        return v

    @field_validator("invite_code")
    @classmethod
    def validate_invite_code(cls, v: str) -> str:
        if len(v) != 8:
            raise ValueError("邀请码必须为 8 位字符")
        return v


class UserInfo(BaseModel):
    id: int
    username: str
    qq: str
    is_admin: bool
    avatar_key: str | None = None


class RegisterResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: UserInfo


class LoginRequest(BaseModel):
    username: str | None = None
    password: str | None = None
    qq: str | None = None
    invite_code: str | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str | None) -> str | None:
        if v is not None and (len(v) < 3 or len(v) > 20):
            raise ValueError("用户名长度需在 3-20 个字符之间")
        return v

    @field_validator("invite_code")
    @classmethod
    def validate_invite_code(cls, v: str | None) -> str | None:
        if v is not None and len(v) != 8:
            raise ValueError("邀请码必须为 8 位字符")
        return v

    @field_validator("qq")
    @classmethod
    def validate_qq(cls, v: str | None) -> str | None:
        if v is not None and (len(v) < 5 or len(v) > 20):
            raise ValueError("QQ 号长度需在 5-20 个字符之间")
        return v


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: UserInfo


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class TokenRefreshResponse(BaseModel):
    access_token: str


class ResetPasswordRequest(BaseModel):
    invite_code: str
    new_password: str

    @field_validator("invite_code")
    @classmethod
    def validate_invite_code(cls, v: str) -> str:
        if len(v) != 8:
            raise ValueError("邀请码必须为 8 位字符")
        return v

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码至少需要 6 个字符")
        if len(v) > 128:
            raise ValueError("密码长度不能超过 128 个字符")
        return v


class ResetPasswordResponse(BaseModel):
    user: UserInfo
