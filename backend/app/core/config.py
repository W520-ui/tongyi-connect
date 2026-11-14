from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "通译智联 API"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False
    log_level: str = "INFO"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    astrbot_base_url: str = "http://127.0.0.1:6185"
    astrbot_api_key: str | None = None
    astrbot_timeout_seconds: float = 60.0
    # 参赛演示时即使 AstrBot 尚未配置模型，也能跑通完整服务流程；
    # 生产环境可将其关闭，让模型配置问题直接返回错误。
    agent_local_fallback_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
