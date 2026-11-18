from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "蒙牛问道 API"
    deepseek_api_key: SecretStr | None = None
    deepseek_model: str = "deepseek-flash"
    deepseek_base_url: str = "https://api.deepseek.com"
    llm_timeout_seconds: float = 30
    content_blocked_terms: str = "自杀;自残;制毒;制爆;制造炸弹"
    database_url: SecretStr | None = None
    wechat_app_id: str | None = None
    wechat_app_secret: SecretStr | None = None
    wechat_openid_hash_secret: SecretStr | None = None
    auth_token_ttl_days: int = Field(default=30, ge=1, le=90)
    wechat_api_timeout_seconds: float = Field(default=8, gt=0, le=30)

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("deepseek_api_key", mode="before")
    @classmethod
    def normalize_api_key(
        cls,
        value: str | SecretStr | None,
    ) -> str | SecretStr | None:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("wechat_app_id")
    @classmethod
    def normalize_wechat_app_id(cls, value: str | None) -> str | None:
        if value is not None:
            return value.strip() or None
        return value

    @field_validator("database_url")
    @classmethod
    def require_mysql_asyncmy(
        cls,
        value: SecretStr | str | None,
    ) -> SecretStr | str | None:
        if isinstance(value, SecretStr):
            url = value.get_secret_value()
        else:
            url = value
        if url and not url.startswith("mysql+asyncmy://"):
            raise ValueError("DATABASE_URL 必须使用 mysql+asyncmy 驱动")
        return value

    @property
    def blocked_terms(self) -> tuple[str, ...]:
        return tuple(
            term.strip()
            for term in self.content_blocked_terms.split(";")
            if term.strip()
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
