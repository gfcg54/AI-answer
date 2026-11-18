from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class WechatLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=128)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("微信登录凭证不能为空")
        return normalized


class UserProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nickname: str | None = Field(default=None, min_length=1, max_length=40)
    avatar_url: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def require_profile_field(self) -> "UserProfileUpdateRequest":
        if self.nickname is None and self.avatar_url is None:
            raise ValueError("请至少提供一个资料字段")
        return self

    @field_validator("nickname")
    @classmethod
    def normalize_nickname(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("昵称不能为空")
        return normalized

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, value: str | None) -> str | None:
        if value is not None and value and not value.startswith("https://"):
            raise ValueError("头像地址必须使用 HTTPS")
        return value


class UserProfile(BaseModel):
    id: str
    nickname: str
    avatar_url: str
    created_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: UserProfile


class LearningSummary(BaseModel):
    total_xp: int
    completed_quizzes: int
    average_accuracy: int
    study_minutes: int
    weak_points: list[str]


class LearningHistoryItem(BaseModel):
    quiz_id: str
    topic: str
    title: str
    accuracy: int
    correct_count: int
    total_count: int
    xp_earned: int
    completed_at: datetime


class LearningHistory(BaseModel):
    items: list[LearningHistoryItem]


class DailyLearningStat(BaseModel):
    date: str
    question_count: int
    correct_count: int
    completed_quizzes: int
    study_minutes: int
    accuracy: int


class LearningAnalytics(BaseModel):
    days: int
    daily: list[DailyLearningStat]
    weak_points: list[str]
